"""Spatial prediction mapping requires geometry recovered from the access unit."""
from prism_v2.codec.sei import extract
from prism_v2.retarget.boxes import DetectorTransform, inverse_boxes


def predictions_to_original(boxes, access_unit: bytes, *, detector=DetectorTransform()):
    signals=extract(access_unit)
    if len(signals)!=1:
        raise ValueError('Spatial evaluation requires exactly one in-band geometry map per AU')
    return inverse_boxes(boxes,signals[0],detector)
