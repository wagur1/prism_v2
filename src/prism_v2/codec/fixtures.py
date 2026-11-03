# Ported from C:/Users/Wagur1/prism-vcm/scripts/spike_gate0.py; v1 commit a34d943; port date 2026-11-04.
"""Historical deterministic stimuli; no historical PASS is inherited."""
import hashlib
import numpy as np
from .x265_bridge import qg_shape

def synthetic_frames(width: int, height: int) -> list[bytes]:
    """Council esc#4: independent seeded noise per frame so every P-frame carries
    residual CUs (the rolled single-texture design made P-frames skip-dominant)."""
    seeds = np.random.SeedSequence(0).spawn(10)
    chroma = bytes([128]) * (width * height // 2)
    return [
        np.random.Generator(np.random.PCG64(seed)).integers(
            16, 236, size=(height, width), dtype=np.uint8
        ).tobytes() + chroma
        for seed in seeds
    ]


def synthetic_content_sha256(width: int, height: int) -> str:
    digest = hashlib.sha256()
    for frame in synthetic_frames(width, height):
        digest.update(frame)
    return digest.hexdigest()


def offset_maps(width: int, height: int) -> dict[str, np.ndarray]:
    shape = qg_shape(width, height)
    yy, xx = np.indices(shape)
    return {"zero": np.zeros(shape, np.float32), "plus6": np.full(shape, 6, np.float32),
            "minus6": np.full(shape, -6, np.float32),
            "checkerboard": np.where((yy // 4 + xx // 4) % 2, 6, -6).astype(np.float32)}


