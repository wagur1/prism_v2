"""Single-intra-frame AU interface: geometry is supplied in its wire precision."""
from pathlib import Path
from .x265_bridge import X265Encoder, EncoderConfig
from .sei import GeometrySignal, attach, extract


def encode_intra(codec, yuv: bytes, width: int, height: int, csv_path: Path, *,
                 offsets=None, arm='M1', signal: GeometrySignal | None=None, crf=28):
    if signal is not None and (width,height)!=(signal.coded_width,signal.coded_height):
        raise ValueError("Geometry dimensions differ from encoder input")
    with X265Encoder(codec,width,height,EncoderConfig(crf=crf),csv_path) as encoder:
        au=encoder.encode(yuv,offsets)+encoder.flush()
    result=attach(au,signal,arm=arm)
    if signal is not None and extract(result)!=[signal]:
        raise ValueError("Encoder geometry failed serialization round-trip")
    return result  # len(result), including headers and SEI, is the only AU rate.
