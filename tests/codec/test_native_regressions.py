"""Offline regressions for the J0 native-fixture failures; no native PASS claim."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from prism_v2.codec.fixtures import (CONTROL_WIDTH, CONTROL_HEIGHT, CONTROL_CRF,
    CONTROL_GOP, CONTROL_BFRAMES, FixtureNeedsVerify, synthetic_content_sha256)
from prism_v2.codec.gate0 import run_gate
from prism_v2.codec.x265_bridge import EncoderConfig, X265Encoder, _open_with_stderr
from tests.codec.test_sei import AU


class NativeFixtureRegressions(unittest.TestCase):
    def test_native_open_failure_surfaces_c_stderr_and_restores_fd(self):
        message = b'x265 [error]: Picture size must be at least one CTU\n'
        def reject(*args):
            os.write(2, message)
            return None
        codec = SimpleNamespace(api=SimpleNamespace(prism_open=reject))
        with self.assertRaisesRegex(RuntimeError, '64x48.*') as exc:
            X265Encoder(codec, 64, 48, EncoderConfig(), Path('unused.csv'))
        self.assertIn(message.decode().strip(), str(exc.exception))
        self.assertNotIn('rejected pinned parameters/header ABI', str(exc.exception))
        before = os.fstat(2)
        with self.assertRaisesRegex(RuntimeError, 'open exception'):
            _open_with_stderr(SimpleNamespace(prism_open=Mock(side_effect=RuntimeError('open exception'))),
                              64, 64, b'medium', b'')
        self.assertEqual(os.fstat(2), before)

    def test_recovered_generator_hash_and_intra_conditions(self):
        self.assertEqual((CONTROL_WIDTH, CONTROL_HEIGHT, CONTROL_CRF, CONTROL_GOP, CONTROL_BFRAMES),
                         (1920, 1080, 20, 1, 0))
        self.assertEqual(synthetic_content_sha256(CONTROL_WIDTH, CONTROL_HEIGHT),
                         '938e0f62f5477ce5581dd4630b3e2f4c5965413c6edfd7b0bb4f681d66e84a01')

    def test_tiny_and_unratified_control_domains_skip_closed(self):
        stack = {'enable_assembly':True, 'builds':{}}
        for args in ({'width':128, 'height':80}, {'crfs':(24,)}):
            with self.subTest(args=args), tempfile.TemporaryDirectory() as tmp:
                with patch('prism_v2.codec.gate0.encode_condition') as encode:
                    with self.assertRaisesRegex(FixtureNeedsVerify, r'\[NEEDS VERIFY\]'):
                        run_gate(tmp, stack, **args)
                    encode.assert_not_called()
                receipt = json.loads((Path(tmp) / 'gate0.json').read_text())
                self.assertEqual(receipt['status'], 'SKIP')
                self.assertFalse(receipt['gate0_complete'])

    def test_native_methods_use_full_domain_and_ctu_sized_baselines(self):
        # Invoke the test bodies under encoder mocks, bypassing only their
        # stack-availability decorator, to catch dimensions in every baseline.
        from tests.codec import test_native as native
        with tempfile.TemporaryDirectory() as tmp:
            stack = Path(tmp) / 'stack.json'
            stack.write_text(json.dumps({'builds':{'patched':{'shim':'s','library':'l','pin':{}}},
                                         'decoders':{'ffmpeg':{}, 'hm':{}}}))
            case = native.NativeTests()
            with patch.object(native, 'STACK', str(stack)), \
                 patch.object(native, 'run_gate', return_value={'status':'CODEC_CONTROLS_PASS','gate0_complete':False}) as gate:
                case.test_sign_controls_identity_and_two_decoders()
                self.assertEqual(gate.call_args.kwargs, {'crfs':(20,)})
            seen = []
            def encoder(_codec, width, height, _config, _csv):
                self.assertGreaterEqual(min(width,height), 64)
                seen.append((width,height))
                instance = Mock()
                instance.encode.return_value = AU
                instance.flush.return_value = b''
                context = Mock()
                context.__enter__ = Mock(return_value=instance)
                context.__exit__ = Mock(return_value=False)
                return context
            with patch.object(native, 'STACK', str(stack)), patch.object(native, 'BuildPin'), \
                 patch.object(native, 'DecoderPin'), patch.object(native, 'X265Library'), \
                 patch.object(native, 'verify_decoders') as decode, \
                 patch('prism_v2.codec.encoder.X265Encoder', side_effect=encoder):
                case.test_native_geometry_sei_decoder_match_and_baseline_absence()
                self.assertEqual(seen, [(64,64)] * 3)
                self.assertEqual(decode.call_count, 3)
                self.assertTrue(all(c.args[-3:] == (64,64,1) for c in decode.call_args_list))

    def test_native_acceptance_never_converts_failures_to_skips(self):
        from tests.codec import test_native as native
        with tempfile.TemporaryDirectory() as tmp:
            stack = Path(tmp) / 'stack.json'
            stack.write_text('{}')
            case = native.NativeTests()
            for method, function in ((case.test_sign_controls_identity_and_two_decoders, 'run_gate'),
                                     (case.test_native_warped_qg_acceptance, 'run_retarget_fixture')):
                with patch.object(native, 'STACK', str(stack)), \
                     patch.object(native, function, side_effect=FixtureNeedsVerify('native evidence failure')):
                    with self.assertRaises(FixtureNeedsVerify):
                        method()
