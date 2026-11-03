"""A3: edge-coordinate maps, with exact full-frame endpoints and QG knots."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import numpy as np

FRACTION_BITS = 16
SCALE = 1 << FRACTION_BITS
MAX_DIMENSION = 65535


def dimension(value: int) -> int:
    if type(value) is not int or not 0 < value <= MAX_DIMENSION:
        raise ValueError("Dimension must be an integer in [1, 65535]")
    return value


def boundaries(length: int) -> tuple[int, ...]:
    dimension(length)
    return (*range(0, length, 16), length)


@dataclass(frozen=True)
class AxisMap:
    source: tuple[float, ...]
    destination: tuple[float, ...]

    def __post_init__(self):
        for name in ('source', 'destination'):
            values = tuple(getattr(self, name))
            object.__setattr__(self, name, values)
            if (len(values) < 2 or values[0] != 0 or
                    not all(math.isfinite(v) for v in values) or
                    any(b <= a for a, b in zip(values, values[1:]))):
                raise ValueError("Map must start at zero and be strictly monotone; no zero widths")
        if len(self.source) != len(self.destination):
            raise ValueError("Knot counts differ")
        if self.source != boundaries(dimension(int(self.source[-1]))):
            raise ValueError("Source knots must be QG16 boundaries including the partial edge")

    def forward(self, coordinates):
        return _interpolate(coordinates, self.source, self.destination)

    def inverse(self, coordinates):
        return _interpolate(coordinates, self.destination, self.source)


def _interpolate(coordinates, source, destination):
    values = np.asarray(coordinates, dtype=np.float64)
    if not np.isfinite(values).all() or np.any(values < source[0]) or np.any(values > source[-1]):
        raise ValueError("Coordinates outside the declared map domain")
    result = np.interp(values, source, destination)
    return float(result) if values.ndim == 0 else result


def axis_from_marginal(length: int, output: int, marginal) -> AxisMap:
    knots = boundaries(length)
    dimension(output)
    r = np.asarray(marginal, dtype=np.float64)
    if r.shape != (len(knots) - 1,) or not np.isfinite(r).all() or np.any((r < 0) | (r > 1)):
        raise ValueError("One bounded saliency marginal in [0,1] per source interval is required")
    weights = np.diff(knots) * (1 + r)
    target = np.r_[0., np.cumsum(weights) * output / weights.sum()]
    target[-1] = output
    return AxisMap(knots, tuple(target))


@dataclass(frozen=True)
class Geometry:
    x: AxisMap
    y: AxisMap

    def quantize(self) -> QuantizedMap:
        if any(axis.destination[-1] != int(axis.destination[-1]) for axis in (self.x,self.y)):
            raise ValueError("Visible endpoints must be integer pixel dimensions")
        return QuantizedMap(
            int(self.x.source[-1]), int(self.y.source[-1]),
            dimension(int(self.x.destination[-1])), dimension(int(self.y.destination[-1])),
            tuple(int(math.floor(v * SCALE + .5)) for v in self.x.destination),
            tuple(int(math.floor(v * SCALE + .5)) for v in self.y.destination))


def from_saliency(saliency, width: int, height: int, output_width: int, output_height: int) -> Geometry:
    """Saliency is a bounded per-QG cell mean. Marginals use valid pixel areas.

    None/empty ROI is uniform. No data-dependent min/max normalization: maximum
    saliency doubles an interval's unnormalized width weight.
    """
    xs, ys = boundaries(width), boundaries(height)
    shape = (len(ys)-1, len(xs)-1)
    values = np.zeros(shape) if saliency is None else np.asarray(saliency, dtype=np.float64)
    if values.shape != shape or not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
        raise ValueError("Expected finite bounded saliency on the visible QG16 grid")
    return Geometry(axis_from_marginal(width, output_width, np.average(values, axis=0, weights=np.diff(ys))),
                    axis_from_marginal(height, output_height, np.average(values, axis=1, weights=np.diff(xs))))


@dataclass(frozen=True)
class QuantizedMap:
    source_width: int
    source_height: int
    visible_width: int
    visible_height: int
    x_ticks: tuple[int, ...]
    y_ticks: tuple[int, ...]

    def __post_init__(self):
        for v in (self.source_width, self.source_height, self.visible_width, self.visible_height):
            dimension(v)
        for name, source, visible in (('x_ticks', self.source_width, self.visible_width),
                                       ('y_ticks', self.source_height, self.visible_height)):
            ticks = tuple(getattr(self, name))
            object.__setattr__(self, name, ticks)
            if (len(ticks) != len(boundaries(source)) or ticks[0] != 0 or ticks[-1] != visible*SCALE or
                    any(type(t) is not int or not 0 <= t <= 0xffffffff for t in ticks) or
                    any(b <= a for a, b in zip(ticks, ticks[1:]))):
                raise ValueError("Invalid quantized map: non-monotone, zero-width, or wrong endpoints")

    @property
    def x(self):
        return AxisMap(boundaries(self.source_width), tuple(t/SCALE for t in self.x_ticks))

    @property
    def y(self):
        return AxisMap(boundaries(self.source_height), tuple(t/SCALE for t in self.y_ticks))

    def serialize(self) -> bytes:
        return json.dumps({'version': 1, 'fraction_bits': FRACTION_BITS,
            'dimensions': [self.source_width, self.source_height, self.visible_width, self.visible_height],
            'x_ticks': self.x_ticks, 'y_ticks': self.y_ticks}, separators=(',', ':'), sort_keys=True).encode('ascii')

    @classmethod
    def parse(cls, data: bytes):
        obj = json.loads(data)
        if set(obj) != {'version','fraction_bits','dimensions','x_ticks','y_ticks'} or obj['version'] != 1 or obj['fraction_bits'] != FRACTION_BITS:
            raise ValueError("Unsupported geometry schema")
        return cls(*obj['dimensions'], tuple(obj['x_ticks']), tuple(obj['y_ticks']))
