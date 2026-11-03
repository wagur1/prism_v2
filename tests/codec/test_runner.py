import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prism_v2.codec.gate0 import encode_condition, run_gate


class RunnerTests(unittest.TestCase):
    def test_worker_has_source_import_path_and_isolated_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix=Path(tmp)/'plus'
            build={'shim':'shim','library':'library','pin':{}}
            with patch('prism_v2.codec.gate0.subprocess.run') as run:
                encode_condition(prefix,'plus6',build,20,128,80)
            environment=run.call_args.kwargs['env']
            self.assertTrue((Path(environment['PYTHONPATH'].split(os.pathsep)[0])/'prism_v2').is_dir())
            self.assertEqual(environment['PRISM_X265_RC_TELEMETRY'],str(prefix.with_suffix('.telemetry.csv').resolve()))
            self.assertEqual(json.loads(prefix.with_suffix('.job.json').read_text())['crf'],20)
            config=json.loads(prefix.with_suffix('.job.json').read_text())['config']
            self.assertEqual((config['crf'],config['gop'],config['bframes'],config['rc_mode']), (20,1,0,'CRF'))
            with self.assertRaisesRegex(ValueError,'fresh'):
                encode_condition(prefix,'plus6',build,20,128,80)

    def test_full_crf_identity_grid_uses_bands_only_in_ratified_domain(self):
        stack={'enable_assembly':True, 'builds':{name:{'pin':{'enable_assembly':True}}
               for name in ('stock','patched')}, 'decoders':{'ffmpeg':{}, 'hm':{}}}
        def encode(prefix, *args):
            prefix.with_suffix('.hevc').write_bytes(b'\x00\x00\x01\x26\x01\x80')
        with tempfile.TemporaryDirectory() as tmp:
            with patch('prism_v2.codec.gate0.encode_condition', side_effect=encode) as enc, \
                 patch('prism_v2.codec.gate0.DecoderPin'), \
                 patch('prism_v2.codec.gate0.verify_decoders', return_value={}) as dec, \
                 patch('prism_v2.codec.gate0.verify_condition', return_value={}) as verify:
                result=run_gate(tmp, stack)
            self.assertEqual(enc.call_count,30)
            self.assertEqual(dec.call_count,30)
            self.assertEqual(verify.call_count,3)
            self.assertEqual({c.kwargs['name'] for c in verify.call_args_list}, {'plus6','minus6','checkerboard'})
            self.assertTrue(all(c.args[0].name == 'crf20_zero.telemetry.csv' for c in verify.call_args_list))
            self.assertTrue(all((c.kwargs['width'],c.kwargs['height']) == (1920,1080) for c in verify.call_args_list))
            self.assertEqual(result['control_fixture']['frame_classes'], ['first_frame']+['compensated']*9)
            self.assertEqual(result['net_effect_crfs'],[20])
            self.assertEqual(result['status'],'CODEC_CONTROLS_PASS')
