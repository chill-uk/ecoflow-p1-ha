"""Tests for DSMR integrity and required-field validation."""

from __future__ import annotations

import unittest

from .helpers import load_module

validation = load_module("custom_components.ecoflow_p1.validation")


FRAME_1 = """/ISK5\\2M550E-1011\r
\r
1-3:0.2.8(50)\r
0-0:1.0.0(260909230749S)\r
0-0:96.1.1(4530303333303036383234313531333137)\r
1-0:1.8.1(014594.213*kWh)\r
1-0:1.8.2(015966.058*kWh)\r
1-0:2.8.1(000117.923*kWh)\r
1-0:2.8.2(000352.530*kWh)\r
0-0:96.14.0(0001)\r
1-0:1.7.0(00.000*kW)\r
1-0:2.7.0(00.000*kW)\r
0-0:96.7.21(00016)\r
0-0:96.7.9(00007)\r
1-0:99.97.0(2)(0-0:96.7.19)(170112141836W)(0000001793*s)(221224033537W)(0000016055*s)\r
1-0:32.32.0(00014)\r
1-0:32.36.0(00002)\r
0-0:96.13.0()\r
1-0:32.7.0(242.9*V)\r
1-0:31.7.0(003*A)\r
1-0:21.7.0(00.000*kW)\r
1-0:22.7.0(00.000*kW)\r
0-1:24.1.0(003)\r
0-1:96.1.0(4730303339303031363530333936303136)\r
0-1:24.2.1(260909230458S)(11118.617*m3)\r
!BDB4\r
"""

FRAME_2 = (
    FRAME_1.replace("260909230749S", "260909230800S")
    .replace("242.9*V", "242.7*V")
    .replace("!BDB4", "!BC8A")
)

FRAME_3 = (
    FRAME_1.replace("260909230749S", "260909230811S")
    .replace("1-0:1.7.0(00.000*kW)", "1-0:1.7.0(00.010*kW)")
    .replace("242.9*V", "242.8*V")
    .replace("1-0:22.7.0(00.000*kW)", "1-0:22.7.0(00.001*kW)")
    .replace("!BDB4", "!6767")
)


class CrcTests(unittest.TestCase):
    """Verify exact DSMR CRC handling."""

    def test_user_captured_frames_have_valid_crc(self) -> None:
        """Use all three captured EcoFlow frames as positive test vectors."""
        for telegram, expected in (
            (FRAME_1, "BDB4"),
            (FRAME_2, "BC8A"),
            (FRAME_3, "6767"),
        ):
            with self.subTest(expected=expected):
                result = validation.validate_crc(telegram)
                self.assertTrue(result.valid)
                self.assertEqual(result.reported, expected)
                self.assertEqual(result.calculated, expected)

    def test_changed_payload_fails_crc(self) -> None:
        """Detect a changed byte while retaining the original reported checksum."""
        result = validation.validate_crc(FRAME_1.replace("242.9*V", "242.8*V"))
        self.assertFalse(result.valid)
        self.assertEqual(result.error, "CRC mismatch")


class RequiredObisTests(unittest.TestCase):
    """Verify phase-aware validation against the unmerged frame."""

    def test_complete_single_phase_frame_is_valid(self) -> None:
        result = validation.validate_required_obis(FRAME_1, "single")
        self.assertTrue(result.valid)

    def test_distinguishes_missing_empty_and_wrong_unit(self) -> None:
        telegram = (
            FRAME_1.replace("0-0:96.14.0(0001)\r\n", "")
            .replace("1-0:1.7.0(00.000*kW)", "1-0:1.7.0()")
            .replace("1-0:32.7.0(242.9*V)", "1-0:32.7.0(242.9*A)")
        )
        result = validation.validate_required_obis(telegram, "single")

        self.assertIn("0-0:96.14.0", result.missing)
        self.assertEqual(result.invalid["1-0:1.7.0"], "empty value")
        self.assertEqual(result.invalid["1-0:32.7.0"], "expected unit V, received A")

    def test_three_phase_mode_requires_l2_and_l3(self) -> None:
        result = validation.validate_required_obis(FRAME_1, "three")

        self.assertIn("1-0:52.7.0", result.missing)
        self.assertIn("1-0:72.7.0", result.missing)
        self.assertEqual(len(result.missing), 8)

    def test_redacts_electricity_and_mbus_equipment_ids(self) -> None:
        redacted = validation.redact_equipment_ids(FRAME_1)

        self.assertNotIn("4530303333303036383234313531333137", redacted)
        self.assertNotIn("4730303339303031363530333936303136", redacted)
        self.assertIn("0-0:96.1.1(<redacted>)", redacted)
        self.assertIn("0-1:96.1.0(<redacted>)", redacted)


if __name__ == "__main__":
    unittest.main()
