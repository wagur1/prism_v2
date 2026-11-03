# Ported from C:/Users/Wagur1/prism-vcm/tests/test_telemetry.py; v1 commit a34d943; port date 2026-11-04.
import csv
import tempfile
import unittest
from pathlib import Path
from prism_v2.codec.net_effect import project_telemetry_qg, qg_net_samples, qg_statistics, verify_net_effect_qg
QG_FIELDS = ("record_type", "frame", "poc", "encode_order", "slice_type", "x", "y", "qg_x", "qg_y", "qg_size", "final_qp", "base_qp_at_cu", "has_residual", "skip", "requested_offset")

class QGTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.zero, self.condition = self.root / "zero.csv", self.root / "condition.csv"

    def write(self, path, regions, frames=(0,)):
        """regions: (x,y,size,final_qp,active), optionally dict overrides."""
        rows = []
        for frame in frames:
            identity = {"frame": frame, "poc": frame, "encode_order": frame, "slice_type": "I"}
            rows.append({"record_type": "frame", **identity})
            for region in regions:
                x, y, size, qp, active, *overrides = region
                rows.append({"record_type": "cu", **identity, "x": x, "y": y,
                             "qg_x": x, "qg_y": y, "qg_size": size, "final_qp": qp,
                             "base_qp_at_cu": 30, "has_residual": int(active), "skip": 0,
                             **(overrides[0] if overrides else {})})
        with path.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=QG_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def verify(self, offsets, width, height, **kwargs):
        parameters = {"bands": {"first_frame": {-1: (5.5, 6.5), 1: (5.5, 6.5)},
                                "compensated": {-1: (4.9, 7), 1: (4.9, 7)}},
                      "min_fidelity": .98, "min_aggregate_median": 4.9, "i_frames": {0}}
        parameters.update(kwargs)
        return verify_net_effect_qg(self.zero, self.condition, offsets, width=width, height=height, **parameters)

    def test_partition_divergence_and_leaf_multiplicity_are_invariant(self):
        offsets = [[-6, -6, 6, 6]] * 2
        self.write(self.zero, [(0, 0, 64, 32, True)])
        self.write(self.condition, [(0, 0, 32, 26, True)] * 7 + [(32, 0, 32, 38, True)])
        divergent = self.verify(offsets, 64, 32)
        fine_zero = [(x, y, 16, 32, True) for y in (0, 16) for x in range(0, 64, 16)]
        fine_condition = [(x, y, 16, 26 if x < 32 else 38, True)
                          for y in (0, 16) for x in range(0, 64, 16)]
        self.write(self.zero, fine_zero)
        self.write(self.condition, fine_condition)
        self.assertEqual(divergent, self.verify(offsets, 64, 32))
        self.assertEqual(divergent["aggregate"]["1"]["count"], 4)
        self.assertEqual(divergent["aggregate"]["-1"]["median_abs"], 6)

    def test_clipped_edge_cells_are_fully_covered_and_padding_is_excluded(self):
        self.write(self.zero, [(0, 0, 32, 30, True), (32, 0, 16, 30, True)])
        self.write(self.condition, [(0, 0, 32, 36, True), (32, 0, 16, 1, True)])
        result = self.verify([[6, 6, -6], [6, 6, -6]], 32, 24)
        self.assertEqual(result["aggregate"]["1"]["count"], 4)
        self.assertEqual(result["per_frame"]["0:1"]["coverage"]["joint_fraction"], 1)
        projected = project_telemetry_qg(self.zero, 32, 24)
        self.assertEqual(projected["cell_area"], [256, 256, 128, 128])

    def test_inactive_support_is_excluded_and_all_coverage_categories_reported(self):
        self.write(self.zero, [(x, 0, 16, 30, x < 32) for x in (0, 16, 32, 48)])
        self.write(self.condition, [(x, 0, 16, 36, x in (0, 32)) for x in (0, 16, 32, 48)])
        row = qg_net_samples(project_telemetry_qg(self.zero, 64, 16),
                             project_telemetry_qg(self.condition, 64, 16), [[6] * 4])[0]
        self.assertEqual(row["values"], [6])
        for category in ("both", "zero_only", "condition_only", "neither"):
            self.assertEqual(row["coverage"][category], 1)
        with self.assertRaisesRegex(ValueError, "INVALID.*coverage"):
            self.verify([[6] * 4], 64, 16)

    def test_exactly_eighty_percent_joint_coverage_is_allowed(self):
        self.write(self.zero, [(x, 0, 16, 30, True) for x in range(0, 80, 16)])
        self.write(self.condition, [(x, 0, 16, 36, x != 64) for x in range(0, 80, 16)])
        result = self.verify([[6] * 5], 80, 16)
        self.assertEqual(result["per_frame"]["0:1"]["coverage"]["joint_fraction"], .8)
        self.assertEqual(result["aggregate"]["1"]["count"], 4)

    def test_skip_leaf_does_not_activate_qg_but_any_residual_leaf_does(self):
        self.write(self.zero, [(0, 0, 16, 30, True)])
        self.write(self.condition, [(0, 0, 16, 36, True, {"skip": 1})])
        with self.assertRaisesRegex(ValueError, "INVALID"):
            self.verify([[6]], 16, 16)
        self.write(self.condition, [(0, 0, 16, 36, True, {"skip": 1}), (0, 0, 16, 36, True)])
        self.assertEqual(self.verify([[6]], 16, 16)["1"], 6)

    def test_dedup_inconsistent_final_or_base_qp_raises_even_for_inactive_leaf(self):
        for override in ({"final_qp": 35}, {"base_qp_at_cu": 31}):
            with self.subTest(override=override):
                self.write(self.condition, [(0, 0, 16, 36, True), (0, 0, 16, 36, False, override)])
                with self.assertRaisesRegex(ValueError, "Inconsistent QP"):
                    project_telemetry_qg(self.condition, 16, 16)

    def test_missing_overlapping_and_unaligned_coverage_raise(self):
        for regions, message in (([(0, 0, 16, 30, True)], "Missing QG coverage"),
                                 ([(0, 0, 32, 30, True), (0, 0, 16, 30, True)], "Overlapping"),
                                 ([(8, 0, 32, 30, True)], "Invalid effective QG")):
            with self.subTest(message=message):
                self.write(self.zero, regions)
                with self.assertRaisesRegex(ValueError, message):
                    project_telemetry_qg(self.zero, 32, 16)

    def test_map_sign_ignores_effective_qg_average_request(self):
        self.write(self.zero, [(0, 0, 32, 30, True)])
        self.write(self.condition, [(0, 0, 32, 36, True, {"requested_offset": 0})])
        rows = qg_net_samples(project_telemetry_qg(self.zero, 32, 16),
                              project_telemetry_qg(self.condition, 32, 16), [[-6, 6]])
        self.assertEqual([r["values"] for r in rows], [[-6], [6]])
        with self.assertRaisesRegex(ValueError, "Sign-fidelity"):
            self.verify([[-6, 6]], 32, 16)

    def test_feedback_class_is_not_i_slice_class(self):
        self.write(self.zero, [(0, 0, 16, 30, True)], frames=(0, 1))
        self.write(self.condition, [(0, 0, 16, 36, True)], frames=(0, 1))
        # Only the second frame changes; all slice labels remain I.
        lines = self.condition.read_text().splitlines()
        lines[-1] = lines[-1].replace(",36,", ",35,")
        self.condition.write_text("\n".join(lines) + "\n")
        result = self.verify([[6]], 16, 16, i_frames={0, 1},
                             bands={"first_frame": {1: (5.5, 6.5)}, "compensated": {1: (4.9, 5.1)}})
        self.assertEqual(result["per_frame"]["1:1"]["frame_class"], "compensated")
        self.assertEqual(result["per_frame"]["1:1"]["kind"], "I")

    def test_explicit_bands_and_aggregate_floor_are_enforced(self):
        self.write(self.zero, [(0, 0, 16, 30, True)])
        self.write(self.condition, [(0, 0, 16, 36, True)])
        with self.assertRaisesRegex(ValueError, "Missing explicit QG band"):
            self.verify([[6]], 16, 16, bands={})
        with self.assertRaisesRegex(ValueError, "Aggregate QG effect"):
            self.verify([[6]], 16, 16, min_aggregate_median=6.1)
        with self.assertRaisesRegex(ValueError, "outside QG band"):
            self.verify([[6]], 16, 16, bands={"first_frame": {1: (4, 5)}, "compensated": {1: (4, 5)}})

    def test_frame_poc_mismatch_rejected(self):
        self.write(self.zero, [(0, 0, 16, 30, True)])
        self.write(self.condition, [(0, 0, 16, 36, True)])
        text = self.condition.read_text().replace(",0,0,0,I", ",0,7,0,I")
        self.condition.write_text(text)
        with self.assertRaisesRegex(ValueError, "frame/POC"):
            self.verify([[6]], 16, 16)

    def test_qg_type7_quantiles_and_magnitude_are_distinct(self):
        stats = qg_statistics([-10, 0])
        self.assertEqual((stats["p10"], stats["p90"]), (-9, -1))
        self.assertEqual((stats["median"], stats["median_abs"]), (-5, 5))

    def test_first_frame_fidelity_is_one_even_with_compensated_threshold_point98(self):
        self.write(self.zero, [(x, 0, 16, 30, True) for x in range(0, 1600, 16)])
        self.write(self.condition, [(x, 0, 16, 36 if x else 24, True) for x in range(0, 1600, 16)])
        with self.assertRaisesRegex(ValueError, "Sign-fidelity.*0.99 < 1.0"):
            self.verify([[6] * 100], 1600, 16)

