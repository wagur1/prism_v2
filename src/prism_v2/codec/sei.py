"""A5 wire format: prefix SEI user_data_unregistered with fixed UUID.

Network byte order; version:u8, kind:u8, fractional bits:u8, reserved:u8;
original W/H, coded W/H, visible x/y/W/H, crop x/y/W/H:12*u32;
x/y knot counts:2*u16; destination knots:u32 Q16.16. Source knots are
implicit QG16 boundaries over the crop extent (full frame for R/U).
HEVC payloadType=5, nal_unit_type=39, layer=0, temporal_id_plus1=1.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import struct
from prism_v2.retarget.geometry import QuantizedMap, FRACTION_BITS, dimension

UUID = bytes.fromhex('7b6fda7638cf4dbb944a839f0d5d70c2')
HEADER = struct.Struct('>4B12I2H')
KINDS = {'retarget': 0, 'resize': 1, 'crop': 2}


@dataclass(frozen=True)
class GeometrySignal:
    geometry: QuantizedMap
    original_width: int
    original_height: int
    coded_width: int
    coded_height: int
    visible_x: int = 0
    visible_y: int = 0
    crop_x: int = 0
    crop_y: int = 0
    kind: str = 'retarget'

    def __post_init__(self):
        if not isinstance(self.geometry, QuantizedMap):
            raise ValueError("Encoder and evaluator require the same quantized map")
        for value in (self.original_width, self.original_height, self.coded_width, self.coded_height):
            dimension(value)
        g = self.geometry
        if any(type(v) is not int or v < 0 for v in (self.visible_x,self.visible_y,self.crop_x,self.crop_y)):
            raise ValueError("Invalid rectangle origin")
        if self.coded_width % 16 or self.coded_height % 16:
            raise ValueError("Coded dimensions must be padded to multiples of 16")
        if (self.visible_x+g.visible_width > self.coded_width or self.visible_y+g.visible_height > self.coded_height or
                self.crop_x+g.source_width > self.original_width or self.crop_y+g.source_height > self.original_height):
            raise ValueError("Visible/crop rectangle exceeds frame")
        if self.kind not in KINDS:
            raise ValueError("Unknown geometry kind")
        if self.kind != 'crop' and (self.crop_x or self.crop_y or g.source_width != self.original_width or g.source_height != self.original_height):
            raise ValueError("Retarget/resize must cover the complete source frame")


def serialize(signal: GeometrySignal) -> bytes:
    g = signal.geometry
    header = HEADER.pack(1, KINDS[signal.kind], FRACTION_BITS, 0,
        signal.original_width,signal.original_height,signal.coded_width,signal.coded_height,
        signal.visible_x,signal.visible_y,g.visible_width,g.visible_height,
        signal.crop_x,signal.crop_y,g.source_width,g.source_height,len(g.x_ticks),len(g.y_ticks))
    ticks = g.x_ticks + g.y_ticks
    return UUID + header + struct.pack(f'>{len(ticks)}I', *ticks)


def parse(payload: bytes) -> GeometrySignal:
    if not payload.startswith(UUID) or len(payload) < len(UUID)+HEADER.size:
        raise ValueError("Truncated payload or unknown geometry UUID")
    version,kind,frac,reserved,*values = HEADER.unpack_from(payload,16)
    if version != 1 or kind not in KINDS.values() or frac != FRACTION_BITS or reserved:
        raise ValueError("Unsupported geometry payload version/flags")
    ow,oh,cw,ch,vx,vy,vw,vh,cx,cy,sw,sh,nx,ny = values
    if len(payload) != 16+HEADER.size+4*(nx+ny):
        raise ValueError("Invalid payload length")
    ticks = struct.unpack_from(f'>{nx+ny}I',payload,16+HEADER.size)
    g=QuantizedMap(sw,sh,vw,vh,ticks[:nx],ticks[nx:])
    return GeometrySignal(g,ow,oh,cw,ch,vx,vy,cx,cy,next(k for k,v in KINDS.items() if v==kind))


def _escape(rbsp: bytes) -> bytes:
    result=bytearray(); zeros=0
    for b in rbsp:
        if zeros == 2 and b <= 3:
            result.append(3); zeros=0
        result.append(b); zeros = zeros+1 if b==0 else 0
    return bytes(result)


def _unescape(ebsp: bytes) -> bytes:
    result=bytearray(); zeros=0; i=0
    while i < len(ebsp):
        b=ebsp[i]
        if zeros == 2 and b==3:
            if i+1 == len(ebsp) or ebsp[i+1]>3:
                raise ValueError("Invalid emulation prevention byte")
            zeros=0; i+=1; continue
        result.append(b); zeros=zeros+1 if b==0 else 0; i+=1
    return bytes(result)


def nal_unit(signal: GeometrySignal) -> bytes:
    payload=serialize(signal)
    size=b'\xff'*(len(payload)//255)+bytes([len(payload)%255])
    return b'\x00\x00\x00\x01\x4e\x01'+_escape(b'\x05'+size+payload+b'\x80')


def _nals(stream: bytes):
    starts=list(re.finditer(b'\x00\x00(?:\x00)?\x01',stream))
    if not starts or starts[0].start()!=0:
        raise ValueError("Expected Annex B access unit")
    for i,m in enumerate(starts):
        end=starts[i+1].start() if i+1<len(starts) else len(stream)
        data=stream[m.end():end]
        if len(data)<2 or data[0]&128 or not data[1]&7:
            raise ValueError("Invalid HEVC NAL header")
        yield m.start(), (data[0]>>1)&63, data[2:]


def extract(stream: bytes) -> list[GeometrySignal]:
    signals=[]
    for _,kind,data in _nals(stream):
        if kind not in (39,40):
            continue
        rbsp=_unescape(data).rstrip(b'\x00'); pos=0
        while pos<len(rbsp) and rbsp[pos:] != b'\x80':
            fields=[]
            for _ in range(2):
                value=0
                while pos<len(rbsp) and rbsp[pos]==255:
                    value+=255; pos+=1
                if pos>=len(rbsp):
                    raise ValueError("Truncated SEI header")
                value+=rbsp[pos];pos+=1;fields.append(value)
            typ,size=fields
            if pos+size>=len(rbsp):
                raise ValueError("Truncated SEI payload/trailing bits")
            payload=rbsp[pos:pos+size];pos+=size
            if typ==5 and payload.startswith(UUID):
                signals.append(parse(payload))
        if rbsp[pos:]!=b'\x80':
            raise ValueError("Invalid SEI trailing bits")
    return signals


def has_sei(stream: bytes) -> bool:
    return any(kind in (39,40) for _,kind,_ in _nals(stream))


def attach(access_unit: bytes, signal: GeometrySignal | None, *, arm: str) -> bytes:
    """Insert before first VCL; input must be one access unit. Count returned bytes."""
    if extract(access_unit):
        raise ValueError("Duplicate geometry signaling")
    if arm in ('M1','M2'):
        if signal is not None or has_sei(access_unit):
            raise ValueError("Stock/M2 must not write PRISM geometry SEI")
        return access_unit
    if arm not in ('R','QR','U','QU','C','QC') or signal is None:
        raise ValueError("Spatial arms require in-band geometry")
    expected='crop' if arm in ('C','QC') else 'resize' if arm in ('U','QU') else 'retarget'
    if signal.kind!=expected:
        raise ValueError("Arm and geometry kind differ")
    for start,kind,_ in _nals(access_unit):
        if kind<=31:
            return access_unit[:start]+nal_unit(signal)+access_unit[start:]
    raise ValueError("Access unit has no VCL NAL")
