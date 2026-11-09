from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from majesty_cam.event_review import analyze, apply
from majesty_cam.gpl import parse_gpl, SemanticMergeResult
from majesty_cam.script_review import ScriptCandidate, ScriptReviewSession, group_conflicts
from majesty_cam.shared_composition import SharedBinding
from majesty_cam.shared_features import StockGameplayEventObserver

class EventPreferenceTests(TestCase):
    def test_native_rewrite_or_observer_wins_without_unconditional_reapplication(self):
        standard='11111111-1111-1111-1111-111111111111'
        observer='22222222-2222-2222-2222-222222222222'
        stock=parse_gpl('function attack_end(agent ThisAgent) declare begin ThisAgent\'s "value" = 1; end').items[0]
        native=parse_gpl(stock.text.replace('= 1','= 2')).items[0]
        callback=parse_gpl('function Observe(agent ThisAgent, integer Amount) declare begin end').items[0]
        binding=SharedBinding(observer.replace('-',''),StockGameplayEventObserver('reward','combat-experience-awarded','Observe'))
        provider=SimpleNamespace(native_candidate=lambda key:ScriptCandidate('Standard',native,standard),functions=lambda _: {})
        initial=SemanticMergeResult((native,callback),())
        def instrument(result, subscribers, references, **kwargs):
            root=next(i for i in result.items if i.key==stock.key)
            if '= 2' in root.text:raise ValueError('no safe award boundary')
            generated=parse_gpl(root.text.replace('= 1','= 3')).items[0]
            return SemanticMergeResult((generated,callback),())
        for winner in (standard,observer):
            with self.subTest(winner=winner), patch('majesty_cam.event_review.add_gameplay_event_observers',side_effect=instrument):
                review=ScriptReviewSession()
                records=analyze('majesty',initial,(binding,),{'attack_end':stock},provider,{observer:'Observer'},review)
                self.assertEqual(len(records),1)
                review.apply({p.identity:winner for p in group_conflicts(review.conflicts)})
                output,bindings=apply(initial,(binding,),records,review)
                root=next(i for i in output.items if i.key==stock.key)
                self.assertEqual(root.text,native.text if winner==standard else stock.text)
                self.assertEqual(bindings,() if winner==standard else (binding,))
