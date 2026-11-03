# Ported from C:/Users/Wagur1/prism-vcm/scripts/spike_gate0.py:run_spike and gate0/build_gate0_stack.sh; v1 commit a34d943; port date 2026-11-04.
"""Independent FFmpeg/HM adapters, extended to compare decoded YUV samples."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import subprocess
import tempfile
from .ffmpeg_stream import frame_bytes
from .x265_bridge import file_sha256


@dataclass(frozen=True)
class DecoderPin:
    executable: str
    sha256: str

    def verify(self):
        if file_sha256(self.executable)!=self.sha256:
            raise ValueError("Decoder binary pin mismatch")


def verify_decoders(bitstream: Path, ffmpeg: DecoderPin, hm: DecoderPin,
                    width: int, height: int, frames: int):
    ffmpeg.verify();hm.verify()
    if Path(ffmpeg.executable).resolve()==Path(hm.executable).resolve() or ffmpeg.sha256==hm.sha256:
        raise ValueError("Two independent decoders are required")
    if type(frames) is not int or frames<=0:
        raise ValueError("Positive expected frame count required")
    expected=frame_bytes(width,height)*frames
    # Small gate-only streams; temporary decoded output is never treated as evidence.
    with tempfile.TemporaryDirectory(prefix='prism-decode-') as directory:
        output=Path(directory)/'hm.yuv'
        decoded=subprocess.run([ffmpeg.executable,'-v','error','-xerror','-c:v','hevc',
            '-i',str(bitstream.resolve()),'-pix_fmt','yuv420p','-f','rawvideo','-'],check=True,capture_output=True).stdout
        subprocess.run([hm.executable,'-b',str(bitstream.resolve()),'-o',str(output),
                        '--OutputBitDepth=8'],check=True,capture_output=True)
        reference=output.read_bytes()
    if len(decoded)!=expected or len(reference)!=expected:
        raise ValueError("Unexpected decoded dimensions/frame count/sample format")
    if decoded!=reference:
        raise ValueError("FFmpeg/HM decoded sample mismatch")
    return {'decoded_sha256':hashlib.sha256(decoded).hexdigest(),'sample_bytes':expected,
            'ffmpeg_sha256':ffmpeg.sha256,'hm_sha256':hm.sha256,'format':'yuv420p8'}
