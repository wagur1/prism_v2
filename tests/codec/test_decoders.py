from pathlib import Path
import hashlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from prism_v2.codec.decoders import DecoderPin,verify_decoders


class DecoderTests(unittest.TestCase):
    def test_samples_must_match_and_have_expected_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);stream=root/'test.hevc';stream.write_bytes(b'synthetic')
            ff=root/'ffmpeg';hm=root/'hm';ff.write_bytes(b'ffmpeg');hm.write_bytes(b'hm')
            pins=[DecoderPin(str(p),hashlib.sha256(p.read_bytes()).hexdigest()) for p in (ff,hm)]
            decoded=b'\x01'*384
            def run(args,**kwargs):
                if args[0]==str(hm):
                    Path(args[args.index('-o')+1]).write_bytes(decoded)
                return subprocess.CompletedProcess(args,0,stdout=decoded,stderr=b'')
            with patch('prism_v2.codec.decoders.subprocess.run',side_effect=run):
                result=verify_decoders(stream,*pins,16,16,1)
                self.assertEqual(result['sample_bytes'],384)
                with self.assertRaisesRegex(ValueError,'dimensions'):
                    verify_decoders(stream,*pins,16,16,2)
            def mismatch(args,**kwargs):
                result=run(args,**kwargs)
                if args[0]==str(hm):
                    Path(args[args.index('-o')+1]).write_bytes(b'\x02'*384)
                return result
            with patch('prism_v2.codec.decoders.subprocess.run',side_effect=mismatch),self.assertRaisesRegex(ValueError,'mismatch'):
                verify_decoders(stream,*pins,16,16,1)
            ff.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'pin mismatch'):
                verify_decoders(stream,*pins,16,16,1)
