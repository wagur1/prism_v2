"""A6: detector coordinates -> coded -> visible -> original edge coordinates."""
from dataclasses import dataclass
import numpy as np
from prism_v2.codec.sei import GeometrySignal


@dataclass(frozen=True)
class DetectorTransform:
    scale_x: float = 1.
    scale_y: float = 1.
    pad_x: float = 0.
    pad_y: float = 0.

    def __post_init__(self):
        if not np.isfinite([self.scale_x,self.scale_y,self.pad_x,self.pad_y]).all() or min(self.scale_x,self.scale_y)<=0:
            raise ValueError("Invalid detector resize/letterbox transform")


def inverse_boxes(boxes, signal: GeometrySignal, detector: DetectorTransform = DetectorTransform()):
    boxes=np.asarray(boxes,dtype=np.float64)
    if boxes.ndim!=2 or boxes.shape[1]!=4 or not np.isfinite(boxes).all() or np.any(boxes[:,2:]<boxes[:,:2]):
        raise ValueError("Expected finite ordered Nx4 xyxy boxes")
    out=boxes.copy();g=signal.geometry
    out[:,[0,2]]=(out[:,[0,2]]-detector.pad_x)/detector.scale_x-signal.visible_x
    out[:,[1,3]]=(out[:,[1,3]]-detector.pad_y)/detector.scale_y-signal.visible_y
    # Padding-only boxes collapse to zero area; caller may discard these detections.
    out[:,[0,2]]=g.x.inverse(np.clip(out[:,[0,2]],0,g.visible_width))+signal.crop_x
    out[:,[1,3]]=g.y.inverse(np.clip(out[:,[1,3]],0,g.visible_height))+signal.crop_y
    return out
