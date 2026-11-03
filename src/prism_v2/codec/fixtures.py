# Ported from C:/Users/Wagur1/prism-vcm/scripts/spike_gate0.py; v1 commit a34d943; port date 2026-11-04.
"""Historical deterministic stimuli; no historical PASS is inherited."""
import hashlib
import numpy as np
from .x265_bridge import qg_shape

# Recovered verbatim from gate0/band_calibration_v3_proposal.json settings
# (confirmatory #2), scripts/spike_gate0.py and gate0/recalibrate_offline.py.
# The five nominal QP labels all used CRF20; they were not a CRF sweep.
# GOP1 is the ratified intra subset. GOP10/B3 remains excluded by CONFIG B1.
CONTROL_WIDTH, CONTROL_HEIGHT = 1920, 1080
CONTROL_CRF, CONTROL_GOP, CONTROL_BFRAMES = 20.0, 1, 0
CONTROL_FRAMES = 10
CONTROL_QP = 32  # Existing v1 nominal label; inactive under CRF.


class FixtureNeedsVerify(RuntimeError):
    """Unratified fixture conditions: no codec verdict may be issued."""


def require_control_domain(width, height, crf):
    if (width, height, crf) != (CONTROL_WIDTH, CONTROL_HEIGHT, CONTROL_CRF):
        raise FixtureNeedsVerify(
            '[NEEDS VERIFY] Net-effect bands cover the v1 1920x1080 CRF20 '
            'ten-frame GOP1/B0 stimulus only in this intra runner; other '
            'conditions need owner-level calibration data, not wider bands')


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


