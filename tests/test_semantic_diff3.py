import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.semantic_diff3 import merge_text


class SemanticDiff3Tests(unittest.TestCase):
    def test_disjoint_stock_relative_edits_are_combined(self):
        base = "function F()\nbegin\n\tA = 1;\n\tB = 2;\nend\n"
        left = "function F()\nbegin\n\tA = 10;\n\tB = 2;\nend\n"
        right = "function F()\nbegin\n\tA = 1;\n\tB = 20;\nend\n"

        text, result = merge_text(base, left, right)

        self.assertTrue(result.clean)
        self.assertIn("A = 10", text)
        self.assertIn("B = 20", text)

    def test_same_stock_line_edits_are_a_real_conflict(self):
        base = "function F()\nbegin\n\tA = 1;\nend\n"
        left = base.replace("A = 1", "A = 10")
        right = base.replace("A = 1", "A = 20")

        _text, result = merge_text(base, left, right)

        self.assertFalse(result.clean)
        self.assertEqual(len(result.conflicts), 1)


if __name__ == "__main__":
    unittest.main()
