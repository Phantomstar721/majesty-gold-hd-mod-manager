import unittest
from majesty_cam.gpl_function_merge import _tokens


class MergeLiteralTests(unittest.TestCase):
    def test_decimal_without_leading_zero_is_one_token(self):
        self.assertEqual(_tokens('value = .5;'), ('value', '=', '.5', ';'))
        self.assertEqual(_tokens('value = 0.5;'), ('value', '=', '0.5', ';'))
