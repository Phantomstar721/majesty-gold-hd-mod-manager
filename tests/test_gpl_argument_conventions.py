"""Prevent explicit-output translation spreading to return-value APIs."""
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]


class ArgumentConventionTests(unittest.TestCase):
    def test_return_value_family_keeps_raw_slots(self):
        source = (ROOT / 'runtime/MapQueryRuntime.cpp').read_text()
        accessor = source.split('void* Argument(', 1)[1].split('\nint* Integer(', 1)[0]
        self.assertIn('MajestyGplCall::FrameSlot', accessor)
        self.assertNotIn('ExplicitSlot', accessor)
        self.assertIn('int* result = Integer(arguments, 0)', source)

    def test_procedures_and_scheduled_frames_remain_separate(self):
        source = (ROOT / 'runtime/AttackObservationRuntime.cpp').read_text()
        frame = source.split('void* FrameArgument(', 1)[1].split('\nvoid* Argument(', 1)[0]
        procedure = source.split('void* Argument(', 1)[1].split('\nvoid __cdecl Settled(', 1)[0]
        self.assertNotIn('ExplicitSlot', frame)
        self.assertIn('MajestyGplCall::ExplicitSlot', procedure)
        binding = (ROOT / 'runtime/CheckedPlacementRuntime.cpp').read_text()
        self.assertIn('&SharedFrameArgument,&SharedFrameAgent', binding)


if __name__ == '__main__': unittest.main()
