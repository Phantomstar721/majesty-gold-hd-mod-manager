from pathlib import Path
import sys,struct,json,copy,unittest
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from majesty_cam.delivery_intake import canonical_voice,validate_manifest,intake,digest,voice_implementation
from majesty_cam.cam import CamArchive,CamSection,CamEntry,pad_name


def wav(metadata=False, rate=22050):
    fmt=struct.pack('<HHIIHH',1,1,rate,rate*2,2,16)
    body=b'WAVEfmt '+struct.pack('<I',16)+fmt
    if metadata:body+=b'JUNK'+struct.pack('<I',3)+b'abc\0'
    body+=b'data'+struct.pack('<I',4)+b'\x01\0\xff\xff'
    return b'RIFF'+struct.pack('<I',len(body))+body


def binding():return dict(xml='Data/sounds.xml',cam='Data/voices.cam',descriptor_id='VO01',phase='Death',wave_id='VT01')
def manifest():return dict(schema_version=1,checkpoint='review',approval_reference='explicit test fixture',items=[
    dict(id='death',kind='voice',file='death.wav',approved_sha256=None,placeholder_sha256=[],bindings=[binding()])])


class DeliveryTests(unittest.TestCase):
    def test_canonical_and_metadata_conversion_preserve_samples(self):
        self.assertEqual(canonical_voice(wav())[0],wav())
        with self.assertRaisesRegex(ValueError,'normalize'):canonical_voice(wav(True))
        prepared,result=canonical_voice(wav(True),True)
        self.assertEqual(prepared,wav());self.assertTrue(result['metadata_normalized'])
        for payload in (wav()[:-1],wav(rate=44100),wav()+b'x'):
            with self.assertRaises(ValueError):canonical_voice(payload,True)

    def test_duplicate_event_frames_and_placeholder_approval_rejected(self):
        a=manifest();duplicate=copy.deepcopy(a['items'][0]);duplicate.update(id='other',file='other.wav');a['items'].append(duplicate)
        with self.assertRaisesRegex(ValueError,'same voice event'):validate_manifest(a)
        a=manifest();a['items'][0].update(approved_sha256='a'*64,placeholder_sha256=['a'*64])
        with self.assertRaisesRegex(ValueError,'placeholder'):validate_manifest(a)
        a=manifest();duplicate=copy.deepcopy(a['items'][0]);duplicate.update(id='DEATH',file='other.wav');a['items'].append(duplicate)
        with self.assertRaisesRegex(ValueError,'unique'):validate_manifest(a)

    def test_staging_missing_unapproved_and_placeholder_are_distinct(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);incoming=root/'incoming';incoming.mkdir();m=root/'manifest.json';spec=manifest()
            m.write_text(json.dumps(spec));r=intake(m,incoming,root/'missing')
            self.assertEqual(r['summary']['externally_missing'],['death']);self.assertFalse(r['ready_for_native_acceptance'])
            original=wav(True);(incoming/'death.wav').write_bytes(original)
            r=intake(m,incoming,root/'review',normalize_wav=True)
            self.assertEqual((incoming/'death.wav').read_bytes(),original)
            self.assertEqual((root/'review/originals/death.wav').read_bytes(),original)
            self.assertEqual((root/'review/review/death.wav').read_bytes(),wav())
            self.assertEqual(r['awaiting_asset_approval'],['death']);self.assertEqual(r['summary']['implemented'],[])
            spec['items'][0]['placeholder_sha256']=[digest(original)];m.write_text(json.dumps(spec))
            r=intake(m,incoming,root/'placeholder',normalize_wav=True)
            self.assertEqual(r['invalid'],['death']);self.assertFalse((root/'placeholder/review').exists())
            with self.assertRaisesRegex(ValueError,'already exists'):intake(m,incoming,root/'review')

    def test_paths_and_overlapping_roots_rejected_before_write(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);incoming=root/'incoming';incoming.mkdir();m=root/'manifest.json'
            for name in ('../escape.wav','C:/escape.wav','/escape.wav','\\server\\file.wav'):
                spec=manifest();spec['items'][0]['file']=name;m.write_text(json.dumps(spec))
                with self.assertRaises(ValueError):intake(m,incoming,root/'out')
                self.assertFalse((root/'out').exists())
            m.write_text(json.dumps(manifest()))
            with self.assertRaisesRegex(ValueError,'separate'):intake(m,incoming,incoming/'review')

    def test_actual_xml_event_to_wave_bytes_required_for_implemented(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);(root/'Data').mkdir()
            (root/'Data/sounds.xml').write_text('<Majesty><Description type="Sound" ID="VO01"><Engine><Phase ID="Death"><Wave value="VT01"/></Phase></Engine></Description></Majesty>')
            cam=CamArchive((CamSection(b'WAVE',(CamEntry(pad_name(b'VT01'),wav()),)),))
            (root/'Data/voices.cam').write_bytes(cam.to_bytes())
            self.assertTrue(voice_implementation(root,binding(),wav()))
            other=binding();other['phase']='Attack'
            self.assertFalse(voice_implementation(root,other,wav()))
            self.assertFalse(voice_implementation(root,binding(),wav(True)))

    def test_frame_registration_and_missing_required_frame(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);incoming=root/'incoming';incoming.mkdir();m=root/'manifest.json'
            tile=bytearray(26);struct.pack_into('<HHH',tile,0,3,1,2);struct.pack_into('<hh',tile,10,-1,1)
            tile+=struct.pack('<IHH',4,2,0x8002)+b'\x02\x03'
            (incoming/'frame.tile').write_bytes(tile)
            item=dict(id='walk0',kind='tile-frame',file='frame.tile',approved_sha256=digest(tile),placeholder_sha256=[],
                      frame=[1,0,0],size=[2,1],anchor=[-1,1],palette_index=0)
            spec=manifest();spec['items']=[item];m.write_text(json.dumps(spec))
            r=intake(m,incoming,root/'valid');self.assertTrue(r['items'][0]['structurally_valid']);self.assertFalse(r['items'][0]['implemented'])
            spec['items'][0]['anchor']=[0,1];m.write_text(json.dumps(spec))
            self.assertEqual(intake(m,incoming,root/'bad')['invalid'],['walk0'])
            spec['items'][0]['anchor']=[-1,1];spec['items'][0]['approved_sha256']=None
            (incoming/'frame.tile').write_bytes(tile[:-1]);m.write_text(json.dumps(spec))
            self.assertEqual(intake(m,incoming,root/'truncated')['invalid'],['walk0'])

    def test_pending_mapping_and_normalized_placeholder_cannot_claim_readiness(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);incoming=root/'incoming';incoming.mkdir();m=root/'manifest.json'
            (incoming/'death.wav').write_bytes(wav(True));spec=manifest();spec['items'][0]['bindings']=[]
            m.write_text(json.dumps(spec));r=intake(m,incoming,root/'pending',normalize_wav=True)
            self.assertFalse(r['items'][0]['implemented']);self.assertTrue(r['specification_pending'])
            spec['items'][0]['placeholder_sha256']=[digest(wav())];m.write_text(json.dumps(spec))
            r=intake(m,incoming,root/'blocked',normalize_wav=True)
            self.assertEqual(r['invalid'],['death']);self.assertFalse((root/'blocked/review').exists())

    def test_cli_reports_missing_without_promoting_approval(self):
        import io
        from contextlib import redirect_stdout
        from majesty_cam.cli import main
        with TemporaryDirectory() as folder:
            root=Path(folder);incoming=root/'incoming';incoming.mkdir();m=root/'manifest.json';m.write_text(json.dumps(manifest()))
            stream=io.StringIO()
            with redirect_stdout(stream):
                self.assertEqual(main(['delivery-intake',str(m),str(incoming),'--output',str(root/'out')]),0)
            result=json.loads(stream.getvalue());self.assertEqual(result['externally_missing'],1)
            self.assertEqual(result['approved'],0)


if __name__=='__main__':unittest.main()
