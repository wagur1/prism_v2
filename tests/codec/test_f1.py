import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from prism_v2.codec.f1 import F1_CHECKS, retarget_fixture, run_f1, verify_warped_telemetry
from prism_v2.codec.ffmpeg_stream import frame_bytes


class F1Tests(unittest.TestCase):
    def test_retarget_fixture_partial_cells_and_signed_offsets(self):
        signal, offsets, yuv = retarget_fixture()
        self.assertEqual((signal.geometry.source_width, signal.geometry.source_height), (130, 98))
        self.assertEqual((signal.geometry.visible_width, signal.geometry.visible_height), (97, 65))
        self.assertEqual(len(yuv), frame_bytes(112, 80))
        self.assertEqual(offsets.shape, (8, 8))
        self.assertTrue((offsets < 0).any() and (offsets > 0).any())
        self.assertTrue((np.abs(offsets) < 6).any())

    def test_native_telemetry_rejects_wrong_offsets_and_missing_edge_qg(self):
        _, offsets, _ = retarget_fixture()
        fields = ['record_type', 'frame', 'slice_type', 'rc_mode', 'qg_x', 'qg_y',
                  'qg_size', 'requested_offset', 'has_residual', 'skip']
        rows = [dict(record_type='frame', frame=0, slice_type='I', rc_mode='CRF')]
        for y in range(5):
            for x in range(7):
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
            self.assertEqual(verify_warped_telemetry(path, offsets)['covered_qgs'], 35)
            rows[-1]['requested_offset'] = 0
            write()
            with self.assertRaisesRegex(ValueError, 'differ'):
                verify_warped_telemetry(path, offsets)
            rows.pop()
            write()
            with self.assertRaisesRegex(ValueError, 'coverage'):
                verify_warped_telemetry(path, offsets)

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
