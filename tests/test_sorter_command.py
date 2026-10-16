import unittest

from medicine_sorter.command import parse_sort_command
from medicine_sorter.errors import SorterError
from medicine_sorter.models import BasketColor, BottleSize


class SorterCommandTests(unittest.TestCase):
    def test_required_examples(self):
        cases = [
            ("큰 약통 하나를 빨간 바구니에 넣어", BottleSize.LARGE, BasketColor.RED),
            ("작은 약통 하나를 파란 바구니에 넣어", BottleSize.SMALL, BasketColor.BLUE),
            ("중간 약통 하나를 초록 바구니에 넣어", BottleSize.MEDIUM, BasketColor.GREEN),
        ]
        for text, size, color in cases:
            with self.subTest(text=text):
                command = parse_sort_command(text)
                self.assertEqual((command.size, command.destination_color, command.quantity),
                                 (size, color, 1))

    def test_synonyms(self):
        self.assertEqual(parse_sort_command("대형 약통을 빨간색 바구니로 옮겨").size,
                         BottleSize.LARGE)
        self.assertEqual(parse_sort_command("중형 약통을 녹색 바구니에 분류해").destination_color,
                         BasketColor.GREEN)
        self.assertEqual(parse_sort_command("소형 약통을 파랑 박스에 넣어").size,
                         BottleSize.SMALL)

    def test_explicit_destination_overrides_default(self):
        command = parse_sort_command(
            "큰 약통을 빨간 바구니에 넣어",
            default_destinations={BottleSize.LARGE: BasketColor.BLUE},
        )
        self.assertEqual(command.destination_color, BasketColor.RED)

    def test_default_is_only_used_when_explicitly_supplied(self):
        command = parse_sort_command(
            "A 약통을 넣어",
            default_destinations={BottleSize.LARGE: BasketColor.BLUE},
        )
        self.assertEqual(command.destination_color, BasketColor.BLUE)

    def assert_code(self, text, code):
        with self.assertRaises(SorterError) as caught:
            parse_sort_command(text)
        self.assertEqual(caught.exception.code, code)
        self.assertTrue(caught.exception.next_action)

    def test_missing_and_unsupported_inputs(self):
        for text, code in [
            ("", "empty_command"),
            ("그거 저기에 넣어", "ambiguous_reference"),
            ("약통을 빨간 바구니에 넣어", "missing_size"),
            ("큰 약통을 넣어", "missing_destination"),
            ("큰 약통 두 개를 빨간 바구니에 넣어", "unsupported_quantity"),
            ("큰 약통 전부 빨간 바구니에 넣어", "unsupported_quantity"),
            ("큰 약통을 빨간 파란 바구니에 넣어", "ambiguous_destination"),
            ("큰 상자를 빨간 바구니에 버려", "unsupported_action"),
        ]:
            with self.subTest(text=text):
                self.assert_code(text, code)
