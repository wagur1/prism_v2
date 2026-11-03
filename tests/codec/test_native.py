import json
import os
import tempfile
import unittest
from pathlib import Path
from prism_v2.codec.gate0 import run_gate
from prism_v2.codec.x265_bridge import X265Library, BuildPin
from prism_v2.codec.encoder import encode_intra
from prism_v2.codec.decoders import DecoderPin, verify_decoders
from prism_v2.codec.fixtures import synthetic_frames
from prism_v2.codec.sei import GeometrySignal, extract
from prism_v2.retarget.geometry import from_saliency

STACK=os.environ.get('PRISM_CODEC_STACK')


@unittest.skipUnless(STACK and Path(STACK).is_file(),'[NEEDS VERIFY] No pinned local encoder/decoder stack (PRISM_CODEC_STACK)')
class NativeTests(unittest.TestCase):
    def test_sign_controls_identity_and_two_decoders(self):
        stack=json.loads(Path(STACK).read_text())
        with tempfile.TemporaryDirectory() as tmp:
            result=run_gate(Path(tmp),stack,width=128,height=80,crfs=(20,))
            self.assertEqual(result['status'],'CODEC_CONTROLS_PASS')
            self.assertFalse(result['gate0_complete'])

    def test_native_geometry_sei_decoder_match_and_baseline_absence(self):
        stack=json.loads(Path(STACK).read_text());build=stack['builds']['patched']
        codec=X265Library(shim=build['shim'],library=build['library'],pin=BuildPin(**build['pin']))
        signal=GeometrySignal(from_saliency(None,98,66,49,33).quantize(),98,66,64,48)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);frame=synthetic_frames(64,48)[0]
            for arm in ('M1','M2','R'):
                au=encode_intra(codec,frame,64,48,root/f'{arm}.csv',arm=arm,signal=signal if arm=='R' else None)
                path=root/f'{arm}.hevc';path.write_bytes(au)
                self.assertEqual(extract(au),[signal] if arm=='R' else [])
                verify_decoders(path,DecoderPin(**stack['decoders']['ffmpeg']),DecoderPin(**stack['decoders']['hm']),64,48,1)

    @unittest.skip('[NEEDS VERIFY] Native warped-QG signed acceptance fixture has not been calibrated/recovered')
    def test_native_warped_qg_acceptance(self):
        pass
