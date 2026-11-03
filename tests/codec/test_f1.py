import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from prism_v2.codec.f1 import F1_CHECKS, retarget_fixture, run_f1, verify_warped_telemetry
from prism_v2.codec.ffmpeg_stream import frame_bytes
from prism_v2.codec.fixtures import FixtureNeedsVerify


class F1Tests(unittest.TestCase):
    def test_retarget_fixture_partial_cells_and_signed_offsets(self):
        signal, offsets, yuv = retarget_fixture()
        self.assertEqual((signal.geometry.source_width, signal.geometry.source_height), (130, 98))
        self.assertEqual((signal.geometry.visible_width, signal.geometry.visible_height), (113, 65))
        self.assertEqual(len(yuv), frame_bytes(128, 80))
        self.assertEqual(offsets.shape, (8, 8))
        self.assertEqual(offsets.shape[1], (signal.coded_width + 15) // 16)
        self.assertGreaterEqual(min(signal.coded_width, signal.coded_height), 64)
        self.assertNotEqual(signal.coded_height % 64, 0)
        self.assertTrue((offsets < 0).any() and (offsets > 0).any())
        self.assertTrue((np.abs(offsets) < 6).any())

    def test_native_telemetry_rejects_wrong_offsets_and_missing_edge_qg(self):
        _, offsets, _ = retarget_fixture()
        fields = ['record_type', 'frame', 'slice_type', 'rc_mode', 'qg_x', 'qg_y',
                  'qg_size', 'requested_offset', 'has_residual', 'skip']
        rows = [dict(record_type='frame', frame=0, slice_type='I', rc_mode='CRF')]
        for y in range(5):
            for x in range(8):
                rows.append(dict(record_type='cu', frame=0, slice_type='I', rc_mode='CRF',
                                 qg_x=x * 16, qg_y=y * 16, qg_size=16,
                                 requested_offset=float(offsets[y, x]), has_residual=1, skip=0))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trace.csv'
            def write():
                with path.open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fields)
                    writer.writeheader()
                    writer.writerows(rows)
            write()
            self.assertEqual(verify_warped_telemetry(path, offsets)['covered_qgs'], 40)
            rows[-1]['requested_offset'] = 0
            write()
            with self.assertRaisesRegex(ValueError, 'differ'):
                verify_warped_telemetry(path, offsets)
            rows.pop()
            write()
            with self.assertRaisesRegex(ValueError, 'coverage'):
                verify_warped_telemetry(path, offsets)

    def test_patch_qg_parent_means_duplicates_and_individual_edges(self):
        # Distinct values in both axes expose stride errors and averaging over
        # the leaf (x,y) rather than its reported QG parent.
        offsets = np.linspace(-6, 6, 64, dtype=np.float32).reshape(8, 8)
        rows = [dict(record_type='frame', frame=0, slice_type='I', rc_mode='CRF')]
        for y in range(5):
            for x in range(8):
                rows.append(dict(record_type='cu', frame=0, slice_type='I', rc_mode='CRF',
                    x=x*16+8, y=y*16+8, qg_x=x*16, qg_y=y*16, qg_size=16,
                    requested_offset=float(offsets[y,x]), has_residual=1, skip=0))
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trace.csv'
            def verify(data):
                with path.open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fields)
                    writer.writeheader(); writer.writerows(data)
                return verify_warped_telemetry(path, offsets)
            # v1 repeats the parent's mean for every committed sub-QG leaf.
            self.assertEqual(verify(rows + [dict(rows[1], x=0, y=0)])['direct_edge_qgs'], 22)
            interior = [r for r in rows if not (r.get('qg_x') in (32,48) and r.get('qg_y') in (32,48))]
            parent = dict(rows[1], x=32, y=32, qg_x=32, qg_y=32, qg_size=32,
                          requested_offset=float(offsets[2:4,2:4].astype(float).mean()))
            self.assertEqual(verify(interior + [parent])['covered_qgs'], 40)
            with self.assertRaisesRegex(ValueError, 'differ'):
                verify(interior + [dict(parent, requested_offset=float(offsets[2,2]))])
            # A footprint mean must never substitute for individual edge proof.
            no_corner = [r for r in rows if not (r.get('qg_x') in (0,16) and r.get('qg_y') in (0,16))]
            corner = dict(parent, x=0, y=0, qg_x=0, qg_y=0,
                          requested_offset=float(offsets[:2,:2].astype(float).mean()))
            with self.assertRaisesRegex(FixtureNeedsVerify, r'\[NEEDS VERIFY\].*edge'):
                verify(no_corner + [corner])
            # Mutate each perimeter QG separately; no edge may be ignored.
            for row in rows[1:]:
                if row['qg_x'] in (0,112) or row['qg_y'] in (0,64):
                    bad = [dict(r) for r in rows]
                    bad[rows.index(row)]['requested_offset'] += 1
                    with self.assertRaisesRegex(ValueError, 'differ'):
                        verify(bad)
            with self.assertRaisesRegex(FixtureNeedsVerify, 'strides'):
                verify_warped_telemetry(path, offsets, width=112)

    def test_needs_verify_keeps_f1_incomplete(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'f1'
            with patch('prism_v2.codec.f1.run_gate', side_effect=FixtureNeedsVerify('[NEEDS VERIFY] calibration')):
                with self.assertRaises(FixtureNeedsVerify):
                    run_f1(output, {})
            report = json.loads((output / 'f1.json').read_text())
            self.assertEqual(report['status'], 'FAIL')
            self.assertFalse(report['gate0_complete'])
            self.assertTrue(all(c['status'] == 'SKIP' for c in report['checks'].values()))

    def test_control_failure_cannot_leave_a_pass_receipt(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'f1'
            with patch('prism_v2.codec.f1.run_gate', side_effect=ValueError('sign failure')):
                with self.assertRaisesRegex(ValueError, 'sign failure'):
                    run_f1(output, {})
            report = json.loads((output / 'f1.json').read_text())
            self.assertFalse(report['gate0_complete'])
            self.assertEqual(report['status'], 'FAIL')
            self.assertEqual(set(report['checks']), set(F1_CHECKS))
            self.assertTrue(all(c['status'] == 'FAIL' for c in report['checks'].values()))

    def test_pass_label_without_full_grid_evidence_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('prism_v2.codec.f1.run_gate', return_value={'status': 'CODEC_CONTROLS_PASS'}):
                with self.assertRaisesRegex(ValueError, 'Incomplete'):
                    run_f1(Path(tmp) / 'f1', {})
