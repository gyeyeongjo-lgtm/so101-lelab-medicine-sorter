import unittest

from scripts.check_aruco_x_still import parse_expected


class SavedFrameCheckerTests(unittest.TestCase):
    def test_expected_point_parser(self):
        self.assertEqual(parse_expected("P1,290.5,219.25"), ("P1", (290.5, 219.25)))

    def test_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            parse_expected(",290,219")


if __name__ == "__main__":
    unittest.main()
