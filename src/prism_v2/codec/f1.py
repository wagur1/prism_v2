"""J0 F1 acceptance, using frozen sign criteria and independent decode evidence.

The small retarget fixture uses nearest pixel sampling solely as a deterministic
codec stimulus. It does not freeze an interpolation policy for efficacy runs.
"""
import csv
import json
import os
from pathlib import Path
import time

import numpy as np

from .decoders import DecoderPin, verify_decoders
from .encoder import encode_intra
from .fixtures import synthetic_frames, CONTROL_CRF, FixtureNeedsVerify
from .gate0 import run_gate
from .qg import warp_qg
from .sei import GeometrySignal, extract, has_sei
from .x265_bridge import BuildPin, X265Library, file_sha256, qg_shape
from prism_v2.retarget.boxes import inverse_boxes
from prism_v2.retarget.geometry import QuantizedMap, from_saliency

F1_CHECKS = (
    'sign_plus6', 'sign_minus6', 'sign_checkerboard', 'zero_map_identity',
    'stock_m2_sei_free', 'sei_round_trip', 'warped_qg_partial_cells',
    'two_decoder_equality', 'quantized_map_validity', 'box_coordinate_round_trip',
)


def retarget_fixture():
    """Nonuniform warp; partial source/destination cells and partial coded CTUs."""
    saliency = np.zeros((7, 9))
    saliency[1:5, 2:7] = 1
    # Width is CTU-aligned so the v1 padded adapter and native QG row strides
    # agree. Height 80 retains a partial CTU; visible 113x65 retains edge cells.
    geometry = from_saliency(saliency, 130, 98, 113, 65).quantize()
    signal = GeometrySignal(geometry, 130, 98, 128, 80)
    source = np.where(np.indices((7, 9))[1] < 4, -6., 6.)
    offsets = warp_qg(source, geometry, 128, 80)
    # Independent scalar rectangle integration, including edge extension. This
    # oracle deliberately does not use the adapter's overlap-matrix algorithm.
    expected = np.empty(qg_shape(128, 80), np.float32)
    xs, ys = list(geometry.x.destination), list(geometry.y.destination)
    xs[-1], ys[-1] = expected.shape[1] * 16, expected.shape[0] * 16
    for row, col in np.ndindex(expected.shape):
        total = 0.
        for sy, sx in np.ndindex(source.shape):
            dx = max(0, min((col + 1) * 16, xs[sx + 1]) - max(col * 16, xs[sx]))
            dy = max(0, min((row + 1) * 16, ys[sy + 1]) - max(row * 16, ys[sy]))
            total += dx * dy * source[sy, sx]
        expected[row, col] = total / 256
    np.testing.assert_allclose(offsets, expected, atol=1e-6, rtol=0)
    if offsets.shape != (8, 8) or not np.isfinite(offsets).all() or abs(offsets).max() > 6:
        raise ValueError('Invalid warped QG buffer')
    if QuantizedMap.parse(geometry.serialize()) != geometry:
        raise ValueError('Quantized geometry round-trip failed')
    for axis in (geometry.x, geometry.y):
        points = np.linspace(0, axis.source[-1], 101)
        np.testing.assert_allclose(axis.inverse(axis.forward(points)), points, atol=1e-10)
    original = np.array([[0, 0, 130, 98], [7, 11, 119, 91]], float)
    mapped = original.copy()
    mapped[:, [0, 2]] = geometry.x.forward(original[:, [0, 2]])
    mapped[:, [1, 3]] = geometry.y.forward(original[:, [1, 3]])
    np.testing.assert_allclose(inverse_boxes(mapped, signal), original, atol=1e-10)
    frame = np.frombuffer(synthetic_frames(130, 98)[0][:130 * 98], np.uint8).reshape(98, 130)
    xx = np.floor(geometry.x.inverse(np.arange(113) + .5)).astype(int)
    yy = np.floor(geometry.y.inverse(np.arange(65) + .5)).astype(int)
    luma = np.pad(frame[np.ix_(yy, xx)], ((0, 15), (0, 15)), mode='edge')
    yuv = luma.tobytes() + bytes([128]) * (128 * 80 // 2)
    return signal, offsets, yuv


def verify_warped_telemetry(path, offsets, width=128, height=80):
    """Check v1 requested_offset semantics and independent edge-QG evidence.

    gate0/x265_residual_telemetry.patch, prismTelemetryCUs/offsets: each cu row
    describes a committed leaf, but requested_offset is the arithmetic mean of
    quantOffsets at 16-pixel steps over (qg_x, qg_y, qg_size). Sub-QG leaves
    repeat their parent's value. Larger QGs can span 32/64 pixels. This is not
    a mean over the leaf origin (x,y), nor over the full CTU-padded buffer.
    """
    offsets = np.asarray(offsets)
    if (offsets.shape != qg_shape(width, height) or not np.isfinite(offsets).all()
            or np.any(abs(offsets) > 6)):
        raise ValueError('Invalid warped QG buffer')
    if offsets.shape[1] != (width + 15) // 16:
        raise FixtureNeedsVerify('[NEEDS VERIFY] Warped fixture native and adapter QG strides differ')
    with Path(path).open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if any(None in row or None in row.values() or row['record_type'] not in ('frame', 'cu') for row in rows):
        raise ValueError('Malformed warped telemetry')
    frames = [r for r in rows if r['record_type'] == 'frame']
    if len(frames) != 1 or frames[0]['frame'] != '0' or frames[0]['slice_type'] != 'I' or frames[0]['rc_mode'] != 'CRF':
        raise ValueError('Incomplete warped fixture telemetry')
    covered, residual, direct = set(), set(), set()
    for row in rows:
        if row['record_type'] != 'cu':
            continue
        if row['frame'] != '0' or row['slice_type'] != 'I' or row['rc_mode'] != 'CRF':
            raise ValueError('Unexpected warped CU identity')
        x, y, size = (int(row[k]) for k in ('qg_x', 'qg_y', 'qg_size'))
        if size not in (16, 32, 64) or x < 0 or y < 0 or x >= width or y >= height or x % size or y % size:
            raise ValueError('Invalid warped telemetry QG')
        cells = [(cy // 16, cx // 16) for cy in range(y, min(y + size, height), 16)
                 for cx in range(x, min(x + size, width), 16)]
        expected = float(np.mean([float(offsets[cy, cx]) for cy, cx in cells]))
        if not np.isclose(float(row['requested_offset']), expected, rtol=0, atol=1e-6):
            raise ValueError(f'Native warped quantOffsets differ from adapter at QG {(x, y, size)}: '
                             f'requested={row["requested_offset"]}, expected={expected}')
        if row['has_residual'] not in ('0', '1') or row['skip'] not in ('0', '1'):
            raise ValueError('Invalid warped residual/skip flags')
        covered.update(cells)
        if size == 16:
            direct.update(cells)
        if row['has_residual'] == '1' and row['skip'] == '0':
            residual.update(cells)
    required = {(y, x) for y in range((height + 15) // 16) for x in range((width + 15) // 16)}
    if covered != required or not residual:
        raise ValueError('Warped telemetry lacks coverage/residual, including partial CTUs')
    edges = {(y, x) for y, x in required
             if y in (0, (height - 1) // 16) or x in (0, (width - 1) // 16)}
    if not edges <= direct:
        raise FixtureNeedsVerify('[NEEDS VERIFY] Warped telemetry lacks individual 16x16 edge QG '
                                 'evidence; coarse means cannot prove every edge offset')
    return {'covered_qgs': len(covered), 'residual_qgs': len(residual),
            'direct_edge_qgs': len(edges), 'requested_offsets_verified': True}


def run_retarget_fixture(output, stack, crfs=(20, 24, 28, 32, 36)):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    signal, offsets, yuv = retarget_fixture()
    (output / 'geometry.json').write_bytes(signal.geometry.serialize())
    np.save(output / 'offsets.npy', offsets)
    build = stack['builds']['patched']
    if not stack['enable_assembly'] or not build['pin']['enable_assembly']:
        raise ValueError('F1 requires assembly ON')
    codec = X265Library(shim=build['shim'], library=build['library'], pin=BuildPin(**build['pin']))
    decoders = [DecoderPin(**stack['decoders'][name]) for name in ('ffmpeg', 'hm')]
    runs = []
    saved = {key: os.environ.get(key) for key in ('PRISM_X265_RC_TELEMETRY', 'PRISM_X265_QP_TRACE')}
    try:
        for crf in crfs:
            streams = {}
            for arm in ('M1', 'M2', 'R', 'QR'):
                prefix = output / f'crf{crf}_{arm}'
                telemetry = prefix.with_suffix('.telemetry.csv')
                os.environ['PRISM_X265_RC_TELEMETRY'] = str(telemetry.resolve())
                os.environ.pop('PRISM_X265_QP_TRACE', None)
                au = encode_intra(codec, yuv, 128, 80, prefix.with_suffix('.csv'), arm=arm,
                    offsets=offsets if arm in ('M2', 'QR') else None,
                    signal=signal if arm in ('R', 'QR') else None, crf=crf)
                path = prefix.with_suffix('.hevc')
                path.write_bytes(au)
                streams[arm] = au
                if arm in ('M1', 'M2'):
                    if has_sei(au):
                        raise ValueError('Stock/M2 path contains SEI')
                elif extract(au) != [signal]:
                    raise ValueError('Retargeted encode SEI round-trip failed')
                trace = verify_warped_telemetry(telemetry, offsets) if arm in ('M2', 'QR') else None
                runs.append({'crf': crf, 'arm': arm, 'au_bytes_including_headers': len(au),
                    'bitstream_sha256': file_sha256(path), 'warped_telemetry': trace,
                    'decode': verify_decoders(path, *decoders, 128, 80, 1)})
            if streams['M1'] == streams['M2'] or streams['R'] == streams['QR']:
                raise ValueError('Warped offset stimulus had no encoded effect')
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return runs


def run_f1(output, stack):
    """Full CRF grid at historical control resolution; never inherits v1 PASS."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'FAIL', 'gate0_complete': False,
              'checks': {name: {'status': 'FAIL', 'detail': 'Not completed'} for name in F1_CHECKS},
              'timing_seconds': {}, 'control_dimensions': [1920, 1080],
              'crfs': [20, 24, 28, 32, 36], 'net_effect_crfs': [CONTROL_CRF], 'retarget_runs': []}
    stage = 'controls'
    started = time.monotonic()
    try:
        print('[F1] controls: 5 CRFs x 6 maps x 10 frames; FFmpeg + HM', flush=True)
        controls = run_gate(output / 'controls', stack)
        expected = {(crf, name) for crf in report['crfs'] for name in
                    ('stock', 'same_binary_no_map', 'zero', 'plus6', 'minus6', 'checkerboard')}
        observed = [(r['crf'], r['map']) for r in controls.get('runs', [])]
        expected_net = {(CONTROL_CRF, name) for name in ('plus6', 'minus6', 'checkerboard')}
        observed_net = [(r['crf'], r['map']) for r in controls.get('net_effect', [])]
        if (controls.get('status') != 'CODEC_CONTROLS_PASS' or set(observed) != expected
                or len(observed) != len(expected) or set(observed_net) != expected_net
                or len(observed_net) != len(expected_net)
                or controls.get('net_effect_crfs') != [CONTROL_CRF]):
            raise ValueError('Incomplete/duplicate frozen-grid control evidence')
        report['timing_seconds'][stage] = time.monotonic() - started
        for name in ('sign_plus6', 'sign_minus6', 'sign_checkerboard'):
            report['checks'][name] = {'status': 'PASS', 'detail': 'controls/gate0.json; ratified CRF20/GOP1 fixture'}
        report['checks']['zero_map_identity'] = {'status': 'PASS', 'detail': 'controls/gate0.json; all 5 CRFs'}
        stage = 'retarget'
        started = time.monotonic()
        print('[F1] retarget: SEI, warped QG, partial cells, two decoders', flush=True)
        report['retarget_runs'] = run_retarget_fixture(output / 'retarget', stack)
        report['timing_seconds'][stage] = time.monotonic() - started
        for name in F1_CHECKS[4:]:
            report['checks'][name] = {'status': 'PASS', 'detail': 'controls/gate0.json and retarget artifacts; all 5 CRFs'}
        report.update(status='PASS', gate0_complete=True)
    except FixtureNeedsVerify as exc:
        report['error'] = str(exc)
        for check in report['checks'].values():
            if check['status'] != 'PASS':
                check.update(status='SKIP', detail=str(exc))
        raise
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        report['timing_seconds'][stage] = time.monotonic() - started
        report['artifacts'] = {str(p.relative_to(output)): file_sha256(p)
                               for p in output.rglob('*') if p.is_file()}
        (output / 'f1.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report
