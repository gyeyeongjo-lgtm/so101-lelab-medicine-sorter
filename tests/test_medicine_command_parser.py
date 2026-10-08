import unittest

from scripts.medicine_command_parser import parse_pick_place_command


class MedicineCommandParserTests(unittest.TestCase):
    def test_all_nine_object_destination_combinations(self):
        color_words = {"RED": "빨강", "GREEN": "초록", "BLUE": "파랑"}
        cases = []
        for object_name in ("A", "B", "C"):
            for destination, word in color_words.items():
                cases.append((f"{object_name}를 {word} 바구니에 넣어", {
                    "object": object_name,
                    "destination": destination,
                }))
        self.assertEqual(len(cases), 9)
        for command, expected in cases:
            with self.subTest(command=command):
                self.assertEqual(parse_pick_place_command(command), expected)

    def test_requested_examples_and_adjective_colors(self):
        self.assertEqual(parse_pick_place_command("A를 파란 바구니에 넣어"),
                         {"object": "A", "destination": "BLUE"})
        self.assertEqual(parse_pick_place_command("C를 빨강 바구니에 옮겨"),
                         {"object": "C", "destination": "RED"})
        self.assertEqual(parse_pick_place_command("b를 초록색 박스로 옮겨줘."),
                         {"object": "B", "destination": "GREEN"})

    def test_rejects_multiple_unknown_or_incomplete_commands(self):
        for command in (
            "", "D를 빨강 바구니에 넣어", "A와 B를 파랑 바구니에 넣어",
            "A를 보라 바구니에 넣어", "C를 빨강 바구니", "C를 빨강에 옮겨",
        ):
            with self.subTest(command=command):
                with self.assertRaises(ValueError):
                    parse_pick_place_command(command)


if __name__ == "__main__":
    unittest.main()
