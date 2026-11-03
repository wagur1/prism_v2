# Ported from C:/Users/Wagur1/prism-vcm/prism/models/student.py:upsample_qp_map; v1 commit a34d943; port date 2026-11-04.
"""NumPy interface to v1 bilinear align_corners=False CTU64 expansion.

The codec buffer includes complete edge CTUs; the visible geometry never does.
The new warped adapter exactly integrates a piecewise-constant source QG field
in destination area, then edge-extends into the codec's padded buffer.
"""
import numpy as np
from .x265_bridge import qg_shape
from prism_v2.retarget.geometry import QuantizedMap, boundaries, dimension


def expand_ctu64(delta_qp, width: int, height: int):
    values=np.asarray(delta_qp)
    dimension(width);dimension(height)
    rows,cols=((height+63)//64*4,(width+63)//64*4)
    if values.ndim!=4 or values.shape[1:]!=(1,rows//4,cols//4) or not np.isfinite(values).all():
        raise ValueError("Expected finite [B,1,ceil(H/64),ceil(W/64)]")
    if not np.issubdtype(values.dtype,np.floating):
        raise ValueError("Continuous floating-point CTU values required")
    def indices(n):
        p=np.clip((np.arange(n,dtype=np.float64)+.5)/4-.5,0,n//4-1)
        lo=np.floor(p).astype(int);hi=np.minimum(lo+1,n//4-1)
        return lo,hi,(p-lo).astype(values.dtype)
    x0,x1,wx=indices(cols); y0,y1,wy=indices(rows)
    horizontal=values[...,x0]*(1-wx)+values[...,x1]*wx
    return horizontal[:,:,y0,:]*(1-wy[None,None,:,None])+horizontal[:,:,y1,:]*wy[None,None,:,None]


def warp_qg(source_offsets, geometry: QuantizedMap, coded_width: int, coded_height: int):
    if not isinstance(geometry,QuantizedMap):
        raise ValueError("Warp adapter requires the serialized quantized geometry")
    if coded_width%16 or coded_height%16 or coded_width<geometry.visible_width or coded_height<geometry.visible_height:
        raise ValueError("Invalid coded dimensions")
    source=np.asarray(source_offsets,dtype=np.float64)
    shape=(len(boundaries(geometry.source_height))-1,len(boundaries(geometry.source_width))-1)
    if source.shape!=shape or not np.isfinite(source).all() or np.any(abs(source)>6):
        raise ValueError("Expected bounded visible source QG16 offsets")
    def overlap(axis,visible):
        src=np.asarray(axis.destination)
        dst=np.asarray(boundaries(visible))
        widths=np.maximum(0,np.minimum(dst[1:,None],src[None,1:])-np.maximum(dst[:-1,None],src[None,:-1]))
        return widths/np.diff(dst)[:,None]
    visible=overlap(geometry.y,geometry.visible_height)@source@overlap(geometry.x,geometry.visible_width).T
    rows,cols=qg_shape(coded_width,coded_height)
    return np.pad(np.clip(visible,-6,6),((0,rows-visible.shape[0]),(0,cols-visible.shape[1])),mode='edge').astype(np.float32)
