from types import SimpleNamespace
from unittest import TestCase
from majesty_cam.gpl import parse_gpl,SemanticMergeResult
from majesty_cam.scoped_output import ScriptBundle,source_items,complete_observer_patches

def result(text):
    # GplComposeResult is a dataclass; retain its actual shape via a tiny
    # dataclass fixture because this operation must only replace source_set.
    from dataclasses import make_dataclass
    return make_dataclass('Result',['source_set'])(SemanticMergeResult(parse_gpl(text).items,()).emit_project_source_set())

class ObserverScopedOutputTests(TestCase):
    def test_xml_only_scope_uses_existing_callback_for_real_completion_outputs(self):
        common = result('function Released(agent a,agent b)\nbegin\nend\nfunction Shared()\nbegin\nend\n')
        before = ScriptBundle(common)
        after = complete_observer_patches(before, ('Released',), required_scopes=('MajestyExpansion',))
        expected = {i.key: i.text for i in source_items(common.source_set)}
        self.assertEqual(tuple(scope for scope, _ in after.outputs), ('Any', 'Majesty', 'MajestyExpansion'))
        for scope, output in after.patches:
            actual = {i.key: i.text for source in (after.common, output) for i in source_items(source.source_set)}
            self.assertEqual(actual, expected)
            self.assertTrue(output.source_set.files)

    def test_single_patch_preserves_both_effective_views_without_empty_output(self):
        common=result('function Released(agent a,agent b)\nbegin\nend\nfunction Shared()\nbegin\nend\n')
        patch=result('function ExpansionOnly()\nbegin\nend\n')
        before=ScriptBundle(common, (('MajestyExpansion',patch),))
        after=complete_observer_patches(before,('Released',))
        self.assertEqual(tuple(scope for scope,_ in after.outputs),('Any','Majesty','MajestyExpansion'))
        for scope,new in after.patches:
            old={item.key:item.text for item in source_items(common.source_set)}
            if scope=='MajestyExpansion':old.update((i.key,i.text) for i in source_items(patch.source_set))
            current={item.key:item.text for _,r in (('Any',after.common),(scope,new)) for item in source_items(r.source_set)}
            self.assertEqual(current,old)
            self.assertTrue(new.source_set.files)
        self.assertNotIn('Released',after.common.source_set.gpl_text)
