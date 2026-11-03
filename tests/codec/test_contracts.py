import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from prism_v2.codec.x265_bridge import EncoderConfig, qg_shape
from prism_v2.codec.encoder import encode_intra
from prism_v2.codec.fixtures import synthetic_frames, offset_maps
from prism_v2.codec.criteria import load_criteria, SOURCE_SHA256

ROOT=Path(__file__).resolve().parents[2]


class ContractTests(unittest.TestCase):
    def test_modified_criteria_cannot_report_frozen_source_hash(self):
        with patch('prism_v2.codec.criteria.Path.read_bytes',return_value=b'{}'),self.assertRaisesRegex(ValueError,'hash mismatch'):
            load_criteria()

    def test_only_frozen_crf_intra_configuration(self):
        options=EncoderConfig().options(Path('csv.csv'))
        for line in ('aq-mode=1','aq-strength=1.0','hevc-aq=0','cutree=0','keyint=1','bframes=0','qg-size=16'):
            self.assertIn(line,options.splitlines())
        for config in (EncoderConfig(rc_mode='CQP'),EncoderConfig(gop=10),EncoderConfig(bframes=1),EncoderConfig(aq_mode=0),EncoderConfig(cutree=True),EncoderConfig(qg_size=64)):
            with self.assertRaises(ValueError):
                config.options(Path('csv.csv'))

    def test_qg64_override_is_explicit_and_limited_to_acceptance(self):
        path = Path('csv.csv')
        config = EncoderConfig(crf=20)
        self.assertIn('qg-size=64', config.options(path, qg_size_override=64).splitlines())
        self.assertIn('qg-size=16', config.options(path).splitlines())
        for size, crf in ((32,20),(16,20),(64,24),(0,20)):
            with self.assertRaisesRegex(ValueError, 'acceptance'):
                EncoderConfig(crf=crf).options(path, qg_size_override=size)
        for arm, crf, offsets in (('M1',20,[[0]]),('R',20,[[0]]),('M2',24,[[0]]),('QR',20,None)):
            with self.subTest(arm=arm,crf=crf), patch('prism_v2.codec.encoder.X265Encoder') as encoder:
                with self.assertRaisesRegex(ValueError, 'acceptance'):
                    encode_intra(None,b'',128,80,path,arm=arm,crf=crf,offsets=offsets,qg_size_override=64)
                encoder.assert_not_called()

    def test_exact_recovered_criteria_artifact_and_envelope(self):
        raw=json.loads((ROOT/'tests/fixtures/criteria_v3.original.json').read_text())['source_utf8'].encode('utf-8')
        self.assertEqual(hashlib.sha256(raw).hexdigest(),SOURCE_SHA256)
        obj=load_criteria();obj.pop('_comment')
        self.assertEqual(obj,json.loads(raw))
        self.assertEqual(obj['fidelity'],dict.fromkeys(('plus6','minus6','checkerboard'),1.0))
        self.assertEqual(obj['bands']['minus6']['compensated']['-1'],[5.0,6.0])

    def test_stimulus_reproducibility_and_ctu_checkerboard(self):
        a=synthetic_frames(128,80);b=synthetic_frames(128,80)
        self.assertEqual(a,b);self.assertEqual(len(set(a)),10)
        self.assertEqual(len(a[0]),128*80*3//2)
        maps=offset_maps(128,80)
        self.assertEqual(maps['zero'].shape,qg_shape(128,80))
        self.assertEqual(float(maps['checkerboard'][0,0]),-6)
        self.assertEqual(float(maps['checkerboard'][0,4]),6)
        self.assertEqual(float(maps['checkerboard'][4,0]),6)
