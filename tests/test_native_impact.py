from dataclasses import replace
import unittest
from unittest.mock import patch
from pathlib import Path
from majesty_cam.native_impact import (ProjectileInterception, ImpactBinding, parse_feature,
    feature_mapping, resolve, encode, decode, require_exact_profile, AUDITED_IMAGES)
from majesty_cam.descriptions import parse_descriptions
from majesty_cam.gpl import parse_gpl, DefinitionKind
from majesty_cam.attack_observation_proof import build_proof, encode as encode_proof, decode as decode_proof
from test_bcd import compiled

FEATURE = ProjectileInterception('deflect', 'Deflect', ('Fire_Ball_Hit',), ('make_attack',), ('Splash',), ('Return_Hit',))
GPL = '''function Deflect(agent Source, agent Target) is boolean
declare
begin
return True;
end
function Fire_Ball_Hit(agent Source, agent Target)
declare
begin
$CreateUnit("fire_ball", Source);
end
'''
XML = '''<Majesty><Description type="Unit" subType="Projectile" ID="WPe1" Name="fireball_missile"><Engine><Script type="0" cProc="0" GPLFunction="Fire_Ball_Hit"/></Engine></Description>
<Description type="Unit" subType="Projectile" ID="ZZ01" Name="unknown"><Engine><Script type="0" cProc="0" GPLFunction="Unclassified"/></Engine></Description>
<Description type="Unit" subType="Projectile" ID="ZZ02" Name="physical"><Engine><Script type="0" cProc="0" GPLFunction="make_attack"/></Engine></Description>
<Description type="Unit" subType="Unit" ID="ZZ03" Name="splash"><Engine><Script type="0" cProc="0" GPLFunction="Fire_Ball_Hit"/></Engine></Description></Majesty>'''

class NativeImpactTests(unittest.TestCase):
    def test_preflight_matches_runtime_exact_images_and_read_failures(self):
        with patch.object(Path, 'read_bytes', return_value=b'unknown'):
            with self.assertRaisesRegex(ValueError,'supported Majesty'):
                require_exact_profile(Path('game.exe'))
        with patch.object(Path, 'read_bytes', side_effect=OSError('unreadable')):
            with self.assertRaises(ValueError):require_exact_profile(Path('game.exe'))
        with self.assertRaises(ValueError):require_exact_profile(None)

    def test_stock_callback_lookup_is_batched_and_preserves_selected_override(self):
        source=parse_gpl(GPL)
        provider=next(i for i in source.items if i.normalized_name=='deflect')
        impact=next(i for i in source.items if i.normalized_name=='fire_ball_hit')
        calls=[]
        def stock(names):
            calls.append(names)
            return {impact.key:impact}
        descriptions=parse_descriptions(XML).records
        self.assertTrue(resolve((FEATURE,),descriptions,(provider,),stock_functions=stock))
        self.assertEqual(calls,[('Fire_Ball_Hit',)])
        calls.clear()
        self.assertTrue(resolve((FEATURE,),descriptions,source.items,stock_functions=stock))
        self.assertEqual(calls,[])

    def test_source_round_trip_and_actual_conflicting_classification(self):
        self.assertEqual(parse_feature(feature_mapping(FEATURE)), FEATURE)
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            feature_mapping(replace(FEATURE, other_exempt_projectile_callbacks=('Fire_Ball_Hit',)))

    def test_targeted_fireball_admitted_without_modifying_any_payload(self):
        source = parse_gpl(GPL)
        rows = resolve((FEATURE,), parse_descriptions(XML).records, source.items)
        self.assertEqual(rows, (ImpactBinding('Deflect','fireball_missile',int.from_bytes(b'WPe1','little'),'Fire_Ball_Hit'),))
        self.assertEqual(source.text, parse_gpl(GPL).text)
        # A shared callback used by an effector is not a reason to rewrite that
        # effector: admission is by actual projectile/terminal route instead.
        self.assertEqual(len(rows),1)

    def test_abi_and_native_shape(self):
        with self.assertRaises(ValueError):
            resolve((FEATURE,),parse_descriptions(XML).records,parse_gpl(GPL.replace('is boolean','is integer')).items)
        for attr in ('type="1"','cProc="1"'):
            changed=XML.replace('type="0"' if attr.startswith('type') else 'cProc="0"',attr)
            self.assertFalse(resolve((FEATURE,),parse_descriptions(changed).records,parse_gpl(GPL).items))

    def test_registry_is_bounded_and_tied_to_actual_proof(self):
        rows=resolve((FEATURE,),parse_descriptions(XML).records,parse_gpl(GPL).items)
        data=encode(rows,b'proof')
        self.assertEqual(decode(data,b'proof'),rows)
        for n in range(len(data)):
            with self.assertRaises(ValueError):decode(data[:n],b'proof')
        with self.assertRaises(ValueError):decode(data,b'changed')
        with self.assertRaises(ValueError):decode(data+b'X',b'proof')
        named=replace(rows[0],projectile='A projectile with spaces and punctuation!')
        self.assertEqual(decode(encode((named,),b'proof'),b'proof'),(named,))
        with self.assertRaises(ValueError):encode((replace(named,projectile='bad\x00name'),),b'proof')

    def test_shared_proof_needs_no_private_hero_or_dummy_binding(self):
        baseline=tuple(compiled((DefinitionKind.FUNCTION,'stock_'+str(i))) for i in range(6))
        output=compiled((DefinitionKind.FUNCTION,'Deflect'))
        proof=build_proof((),baseline,output,shared_only=True,required_functions=('Deflect',))
        self.assertIsNone(proof.feature)
        self.assertEqual(decode_proof(encode_proof(proof)),proof)
        with self.assertRaises(ValueError):build_proof((),baseline,output)
        with self.assertRaises(ValueError):build_proof((),baseline,output,shared_only=True,required_functions=('Missing',))
        with self.assertRaisesRegex(ValueError,'protected'):
            build_proof((),baseline,output,(compiled((DefinitionKind.FUNCTION,'Fire_Ball_Hit')),),
                        shared_only=True,protected_functions=('Fire_Ball_Hit',))

if __name__ == '__main__':unittest.main()
