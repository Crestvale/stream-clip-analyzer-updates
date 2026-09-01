import unittest

from stream_clip_analyzer.timecode import format_timecode, parse_timecode


class TimecodeTests(unittest.TestCase):
    def test_round_trip(self):
        self.assertAlmostEqual(parse_timecode(format_timecode(3723.456)), 3723.456, places=3)

    def test_supported_formats(self):
        self.assertEqual(parse_timecode("12.5"), 12.5)
        self.assertEqual(parse_timecode("01:02.5"), 62.5)
        self.assertEqual(parse_timecode("01:02:03,500"), 3723.5)

    def test_rejects_invalid(self):
        for value in ("", "a:b", "1:2:3:4", "-1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_timecode(value)


if __name__ == "__main__":
    unittest.main()

