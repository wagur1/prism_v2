# Ported from C:/Users/Wagur1/prism-vcm/prism/models/student.py:upsample_qp_map; v1 commit a34d943; port date 2026-11-04.
"""NumPy interface to v1 bilinear align_corners=False CTU64 expansion.

The codec buffer includes complete edge CTUs; the visible geometry never does.
The warped adapter extends the boundary field before destination-area reduction.
Identity geometry preserves a supplied full v1 buffer, including its CTU padding.
"""
import numpy as np
from .x265_bridge import qg_shape
from prism_v2.retarget.geometry import QuantizedMap, SCALE, boundaries, dimension


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
    """Reduce a source QG field into top-left-visible coded QGs.

    Accept the visible QG grid or the full CTU-padded grid from expand_ctu64.
    Pass the full grid for exact v1 identity parity; discarded padding cannot
    be reconstructed from a visible-only grid. Nonidentity maps use visible
    source cells and replicate their boundary values into destination padding.
    """
    if not isinstance(geometry,QuantizedMap):
        raise ValueError("Warp adapter requires the serialized quantized geometry")
    dimension(coded_width);dimension(coded_height)
    if coded_width%16 or coded_height%16 or coded_width<geometry.visible_width or coded_height<geometry.visible_height:
        raise ValueError("Invalid coded dimensions")
    source=np.asarray(source_offsets,dtype=np.float64)
    shape=(len(boundaries(geometry.source_height))-1,len(boundaries(geometry.source_width))-1)
    padded_shape=((geometry.source_height+63)//64*4,(geometry.source_width+63)//64*4)
    if source.shape not in (shape,padded_shape) or not np.isfinite(source).all() or np.any(abs(source)>6):
        raise ValueError("Expected bounded visible or CTU-padded source QG16 offsets")
    rows,cols=qg_shape(coded_width,coded_height)
    identity=all(ticks==tuple(s*SCALE for s in boundaries(length))
                 for length,ticks in ((geometry.source_width,geometry.x_ticks),
                                       (geometry.source_height,geometry.y_ticks)))
    if identity and source.shape==padded_shape:
        return np.pad(source,((0,rows-source.shape[0]),(0,cols-source.shape[1])),mode='edge').astype(np.float32)
    source=source[:shape[0],:shape[1]]
    def overlap(axis,count):
        src=np.asarray(axis.destination)
        dst=np.arange(count+1,dtype=np.float64)*16
        widths=np.maximum(0,np.minimum(dst[1:,None],src[None,1:])-np.maximum(dst[:-1,None],src[None,:-1]))
        widths[:,-1]+=np.maximum(0,dst[1:]-np.maximum(dst[:-1],src[-1]))
        return widths/16
    result=overlap(geometry.y,rows)@source@overlap(geometry.x,cols).T
    return np.clip(result,-6,6).astype(np.float32)
