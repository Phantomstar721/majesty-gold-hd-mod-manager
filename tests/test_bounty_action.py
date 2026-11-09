import unittest
import os
import struct
import tempfile
from pathlib import Path
from dataclasses import replace

from majesty_cam.bounty_action import (
    BountyRequest, BountyType, FlagIdentity, allocate_payment, continuation_allowed,
)


class BountyActionPolicyTests(unittest.TestCase):
    def test_ordinary_paid_action_does_not_enable_bounty_service(self):
        from types import SimpleNamespace
        from majesty_cam.bounty_action import selected, compose_service, validate_service
        from majesty_cam.stock_controller_features import StockAp69PaidSourceTargetAction
        from majesty_cam.gpl import SemanticMergeResult
        # Selection is type-based; a paid spell is not a bounty adapter merely
        # because its price is 500 or because a player flag exists in game.
        feature = object.__new__(StockAp69PaidSourceTargetAction)
        inventory = SimpleNamespace(selected=SimpleNamespace(package=SimpleNamespace(
            definition=SimpleNamespace(runtime_features=(feature,)))))
        enabled = selected((inventory,))
        self.assertFalse(enabled)
        empty = SemanticMergeResult((), ())
        self.assertEqual(compose_service(empty, enabled), empty)
        validate_service({}, {}, enabled)

    def test_existing_flag_path_is_query_only(self):
        """Do not let future lifetime options adopt or alter a player's flag.

        This checks the generated production helper, not the offline payment
        model. Native lifetime/visibility implementation needs separate proof.
        """
        import re
        from majesty_cam.bounty_action import ATTACK_SOURCE
        prefix, separator, remainder = ATTACK_SOURCE.partition(
            'if (Matches == 1) return TotalPrice;')
        self.assertTrue(separator)
        calls = set(re.findall(r'\$([A-Za-z_][A-Za-z_0-9]*)\s*\(', prefix))
        self.assertEqual(calls, {
            'IsValidGamePiece', 'GetUnitPlayerNumber', 'GetPlayerData',
            'ListObjects', 'AgentNumber', 'GetAttribute',
        })
        self.assertNotRegex(prefix, r"(?:Flag|Target|Source)'s\s+\"[^\"]+\"\s*=(?!=)")
        self.assertIn('$PlaceRewardFlag(Target, Player, BountyAmount);', remainder)
        self.assertIn('if (Matches > 1) return -1;', remainder)

    def test_stock_compiler_returns_never_escape_a_foreach(self):
        from majesty_cam.bounty_action import ATTACK_SOURCE
        from majesty_cam.compose import compile_gpl
        from majesty_cam.gpl import GplProjectSourceSet
        compiler = Path(os.environ.get('MAJESTY_STOCK_ROOT',
            'C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')) / 'SDK/Gplbcc.exe'
        self.assertTrue(compiler.is_file(), 'Bounty compiler regression requires installed SDK')
        with tempfile.TemporaryDirectory() as directory:
            output = compile_gpl(GplProjectSourceSet('source="Bounty.gpl"\n', 'Bounty.gpl', ATTACK_SOURCE, None, ''), compiler, Path(directory)/'compiler', stem='Bounty')
            data = output.target.read_bytes()
        pos = 24
        def uint():
            nonlocal pos
            value = struct.unpack_from('<I', data, pos)[0]
            pos += 4
            return value
        def string():
            nonlocal pos
            end = data.index(0, pos)
            value = data[pos:end].decode('ascii')
            pos = end + 1
            return value
        self.assertEqual(uint(), 1)
        self.assertEqual(string(), 'MMM_PrepareAttackBounty')
        returns = []
        for index in range(uint()):
            for operand in range(3):
                uint(); uint(); string()
                pos += 2
            uint(); string()
            line, count = struct.unpack_from('<HB', data, pos)
            pos += 3 + 2 * count
            opcode = data[pos]
            pos += 1
            if opcode == 37:
                returns.append(line)
        lines = ATTACK_SOURCE.splitlines()
        self.assertTrue(returns)
        for line in returns:
            # A return inside foreach is hoisted to the loop-header line by
            # Gplbcc, even on the path that never evaluated its expression.
            self.assertIn('return ', lines[line - 1], (line, lines[line - 1]))

    def test_service_is_explicit_and_reserved(self):
        from majesty_cam.bounty_action import compose_service, validate_service
        from majesty_cam.gpl import SemanticMergeResult
        empty = SemanticMergeResult((), ())
        self.assertEqual(compose_service(empty, False), empty)
        result = compose_service(empty, True)
        functions = {item.normalized_name: item.text for item in result.items}
        counts = {key: 1 for key in functions}
        validate_service(functions, counts, True)
        with self.assertRaises(ValueError):
            compose_service(result, True)
        with self.assertRaises(ValueError):
            validate_service(functions, counts, False)
        with self.assertRaises(ValueError):
            validate_service({}, {}, True)

    def test_one_total_price_for_each_requested_type(self):
        for kind in BountyType:
            request = BountyRequest(kind, 500, 500)
            for exists in (False, True):
                plan = allocate_payment(request, matching_bounty_exists=exists)
                self.assertEqual(plan.bounty_funding + plan.remaining_action_fee, 500)
                self.assertEqual(plan.bounty_funding, 0 if exists else 500)
            plan = allocate_payment(BountyRequest(kind, 300, 500), matching_bounty_exists=False)
            self.assertEqual((plan.bounty_funding, plan.remaining_action_fee), (300, 200))

    def test_invalid_amounts_and_unknown_state(self):
        for amount, total in ((0, 500), (-1, 500), (501, 500), (True, 500), (500, 2**31)):
            with self.assertRaises(ValueError):
                BountyRequest(BountyType.ATTACK, amount, total)
        with self.assertRaises(ValueError):
            BountyRequest("invented", 500, 500)
        with self.assertRaises(ValueError):
            allocate_payment(BountyRequest(BountyType.ATTACK, 500, 500), matching_bounty_exists=None)

    def test_preserve_exact_existing_bounty_and_new_flag(self):
        request = BountyRequest(BountyType.ATTACK, 500, 500)
        for amount in (100, 500, 1000):
            original = FlagIdentity(65, 0, BountyType.ATTACK, 6, amount)
            args = dict(native_success=True, actual_total_debit=500, original=original,
                        matching_count=1, requested_owner=0, requested_target=6)
            self.assertTrue(continuation_allowed(request, final=original, **args))
            for altered in (replace(original, amount=amount+1), replace(original, identity=66),
                            replace(original, owner=1), replace(original, target=7), None):
                self.assertFalse(continuation_allowed(request, final=altered, **args))
        final = FlagIdentity(61, 0, BountyType.ATTACK, 6, 500)
        args = dict(native_success=True, actual_total_debit=500, original=None, final=final,
                    matching_count=1, requested_owner=0, requested_target=6)
        self.assertTrue(continuation_allowed(request, **args))
        for key, value in (("actual_total_debit", 1000), ("actual_total_debit", 0),
                           ("native_success", False), ("matching_count", 2), ("final", None)):
            self.assertFalse(continuation_allowed(request, **dict(args, **{key: value})))


if __name__ == "__main__":
    unittest.main()
