import os,re,struct,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import replace
from majesty_cam.hero_info import parse_hero_info,hero_info_mapping,validate_hero_info_evidence,SAVED_ATTRIBUTE_ROW_TYPE
from majesty_cam.runtime_features import encode_runtime_feature_registry,decode_runtime_feature_registry,normalize_runtime_features,derive_feature_runtime_capabilities
from majesty_cam.package import parse_mod_definition,mod_definition_mapping
from test_hero_info import inventory,ROW
from test_occupant_runtime_profiles import PeImage

SOURCE=dict(type=SAVED_ATTRIBUTE_ROW_TYPE,feature_key='owned-fitting',attribute_symbol='WHP_Salts',
            display_text='Silver Salts',tooltip_text='Carried dose',image_id='ZI01',image_set=1019)
class SavedAttributeTests(unittest.TestCase):
    def test_explicit_lower_list_roundtrip_and_guards(self):
        source=dict(SOURCE,list_category='enchantments')
        row=parse_hero_info(source)
        self.assertEqual(hero_info_mapping(row),source)
        registry=normalize_runtime_features((row,replace(parse_hero_info(SOURCE),feature_key='legacy-row'),ROW))
        data=encode_runtime_feature_registry(registry)
        self.assertEqual(struct.unpack_from('<I',data,4)[0],11)
        self.assertEqual(decode_runtime_feature_registry(data),registry)
        old=encode_runtime_feature_registry((parse_hero_info(SOURCE),ROW))
        self.assertEqual(encode_runtime_feature_registry((row,ROW)),old[:4]+struct.pack('<I',11)+old[8:]+struct.pack('<I',1))
        for end in range(len(data)):
            with self.assertRaises(ValueError):decode_runtime_feature_registry(data[:end])
        for category in ('items','enhancements','',1,None):
            with self.assertRaises(ValueError):parse_hero_info(dict(SOURCE,list_category=category))
        with self.assertRaisesRegex(ValueError,'legacy'):
            hero_info_mapping(replace(ROW,list_category='enchantments'))
        with self.assertRaises(ValueError):decode_runtime_feature_registry(data[:4]+struct.pack('<I',10)+data[8:])
        with self.assertRaisesRegex(ValueError,'category'):
            payload=encode_runtime_feature_registry((row,))
            decode_runtime_feature_registry(payload[:-4]+struct.pack('<I',2))

    def test_recipe_and_wire_roundtrip_with_legacy_rows(self):
        row=parse_hero_info(SOURCE)
        self.assertEqual(hero_info_mapping(row),SOURCE)
        registry=normalize_runtime_features((row,ROW))
        data=encode_runtime_feature_registry(registry)
        self.assertEqual(struct.unpack_from('<I',data,4)[0],10)
        self.assertEqual(decode_runtime_feature_registry(data),registry)
        fixture=(Path(__file__).parent/'SavedAttributeFixture.h').read_text()
        self.assertEqual(data,bytes(int(v,16) for v in re.findall(r'0x([0-9A-F]{2})',fixture)))
        for end in range(len(data)):
            with self.assertRaises(ValueError):decode_runtime_feature_registry(data[:end])
        old=encode_runtime_feature_registry((ROW,))
        self.assertEqual(struct.unpack_from('<I',old,4)[0],7)
        self.assertEqual(derive_feature_runtime_capabilities((),registry),('stock.ap78-info-row.v1',))
        for changed in [data[:4]+struct.pack('<I',9)+data[8:],old[:4]+struct.pack('<I',10)+old[8:]]:
            with self.assertRaises(ValueError):decode_runtime_feature_registry(changed)
    def test_package_roundtrip_and_composed_owner_validation(self):
        from majesty_cam.compose import resolve_runtime_feature_registry
        definition=dict(schema_version=3,mod_id='39ee2697-33c8-42e2-a575-c26c00640f24',
                        internal_name='Example',display_name='Example',custom_buildings=[],runtime_features=[SOURCE])
        self.assertEqual(mod_definition_mapping(parse_mod_definition(definition)),definition)
        with TemporaryDirectory() as tmp:
            inv=inventory(Path(tmp));inv.descriptions=()
            inv.selected.package.definition.runtime_features=(parse_hero_info(SOURCE),)
            result=resolve_runtime_feature_registry((inv,))
            self.assertEqual(result.hero_info_rows[0].attribute_symbol,'WHP_Salts')

    def test_private_image_without_fake_character_ownership(self):
        with TemporaryDirectory() as tmp:
            inv=inventory(Path(tmp))
            inv.descriptions=() # Any actual selected hero, including stock heroes.
            validate_hero_info_evidence(inv,parse_hero_info(SOURCE))
            with self.assertRaisesRegex(ValueError,'owned'):
                validate_hero_info_evidence(inv,replace(parse_hero_info(SOURCE),image_id='ZZ99'))
        for key,value in [('subject_id','Solarus'),('unlock_level',1),('attribute_symbol','WHP_Salts()'),
                          ('attribute_symbol',''),('image_id','INTn')]:
            with self.subTest(key=key),self.assertRaises(ValueError):parse_hero_info(dict(SOURCE,**{key:value}))
    def test_lower_list_uses_stock_effect_icon_geometry(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            row=parse_hero_info(dict(SOURCE,list_category='enchantments'))
            inv=inventory(root);inv.descriptions=()
            with self.assertRaisesRegex(ValueError,'25x25'):validate_hero_info_evidence(inv,row)
            inv=inventory(root,replace(ROW,kind='enchantment',unlock_level=0));inv.descriptions=()
            validate_hero_info_evidence(inv,row)

    def test_effective_stock_gate_preserves_subject_and_image_guards(self):
        from majesty_cam.compose import validate_controller_stock_evidence,resolve_controller_registry,ComposeError
        exe=os.environ.get('MAJESTY_BETA2_EXE')
        if not exe:self.skipTest('local stock resources unavailable')
        def validate(row):
            validate_controller_stock_evidence(Path(exe).parent,(),resolve_controller_registry(()).registry,
                runtime_feature_registry=normalize_runtime_features((row,)))
        validate(parse_hero_info(SOURCE))
        for kind in ('spell','enchantment','passive'):
            with self.subTest(kind=kind),self.assertRaisesRegex(ComposeError,'package-added Description'):
                validate(replace(ROW,kind=kind,unlock_level=2 if kind=='passive' else 0))
        from majesty_cam.stock_cam import stock_image_ids
        stock=next(k for k in stock_image_ids(Path(exe).parent) if len(k)==4 and k not in (b'INTn',b'IX93') and all(32<=v<127 for v in k))
        with self.assertRaisesRegex(ComposeError,'cannot override a stock IMAG'):
            validate(replace(parse_hero_info(SOURCE),image_id=stock.decode('ascii')))

    def test_all_fixed_native_windows_and_existence_abi(self):
        root=Path(__file__).parents[1]
        header=(root/'runtime/SavedAttributeProfiles.h').read_text()
        windows=re.findall(r'\{0x([0-9A-F]+)u,0x([0-9A-F]+)u,0x([0-9A-F]+)u\}',header.split('constexpr Window')[1])
        self.assertEqual(len(windows),42)
        fixtures=root.parent/'majesty-gold-hd-mod-manager-gog-support/local/fixtures'
        profiles=[(i,name,fixtures/name/'MajestyHD.exe') for i,name in enumerate(('public','beta2','gog-pristine'))]
        if os.environ.get('MAJESTY_BETA2_EXE'):profiles.append((1,'modified-beta2',Path(os.environ['MAJESTY_BETA2_EXE'])))
        for index,name,path in profiles:
            if not path.is_file():self.skipTest('local native profile fixture unavailable')
            pe=PeImage(path)
            for address,size,expected in windows[index*14:(index+1)*14]:
                h=2166136261
                for b in pe.read(int(address,16),int(size,16)):h=((h^b)*16777619)&0xffffffff
                self.assertEqual(h,int(expected,16),(name,address))
            exists=int(windows[index*14+4][0],16)
            self.assertEqual(pe.read(exists+0x37,10),bytes.fromhex('0f95c05b83c408c20400'))
