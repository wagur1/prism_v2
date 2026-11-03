# J0 ESCALATION — codec gate NOT PASSED after 2 fix-rerun rounds (contract budget exhausted)

*Written by ZCode monitor, 2026-11-04 ~05:05 UTC. Owner decision required before any further kernel run.*

## Final state (r3 = `htran123456/prism-v2-j0-gate0-r3`, receipt `runs/j0_r3_receipt.json`)

- Build stack: **PASS** (pinned x265 `f0c1022` + patches SHA-verified, HM-16.2, assembly ON; 308.6 s).
- Native pytest: **71 passed / 1 failed** (`test_native_warped_qg_acceptance`).
- **12 of 13 checks PASS natively**: sign fidelity plus6/minus6/checkerboard at the ratified v1 domain (bands untouched, criteria `316134d2`), zero-map byte identity, stock/M2 SEI-free, SEI round-trip, two-decoder equality, quantized-map validity, box coordinate round-trip, QG16 warped CU-mean corroboration at all 5 CRFs.
- **1 check blocked**: `warped_qg_partial_cells` (per-edge-QG adapter acceptance).

## Root cause of the blocked check (pinned, with evidence)

1. v1 telemetry patch (`prism-vcm/gate0/x265_residual_telemetry.patch`) emits rows **per CU**; at `qg-size=16` a CU mean cannot prove per-16×16-QG offsets (r2 finding).
2. Fix attempt: acceptance arm at `qg-size=64` (CU==QG → exact per-QG equality). r3: the patch's telemetry writer **refuses to write** under this configuration — stderr `x265_prism_telemetry_v2: unsupported AQ/refinement configuration` (2×, exactly the M2+QR QG64 passes), therefore `FileNotFoundError` on `crf20_M2_qg64.telemetry.csv` (f1.py:182). Patch guard located at `x265_residual_telemetry.patch` line ~150 (`if (!ok) fprintf(stderr, "unsupported AQ/refinement configuration")`).
3. Conclusion: **patch limitation, not an adapter defect** — the adapter produced valid QG64 bitstreams; the evidence channel refused. All 71 other native tests pass.

## Attempt history (honest)

| Run | Result | Action taken |
|---|---|---|
| v1 (`prism-v2-j0-codec-gate`) | ERROR: 3 fixture-design bugs (sub-1-CTU pictures, per-CU vs per-QG expectation mismatch, fixture domain outside ratified bands) | Fix round 1: fixtures matched ratified domain verbatim (CONTROL_QP=32, 1920×1080 CRF20), per-QG expectation aligned to patch semantics. Old slug 409 on re-push → r2 |
| r2 (`…-gate0-r2`) | FAIL: 67 pass / **1 skip** (fail-closed rejects skips) | Fix round 2: QG64 acceptance arm (CU==QG exact per-QG equality), guarded `qg_size` override, fail-closed re-raise → r3 |
| r3 (`…-gate0-r3`) | FAIL: 71 pass / 1 fail (telemetry writer refuses QG64 config) | **Budget exhausted → this escalation** |

## Recovery options for the owner (ranked)

1. **Extend the telemetry patch** to support the qg-size=64 AQ/refinement path (understand its `ok` validation; emit per-QG64 rows). Costs: new patch SHA → `PINNED_SOURCE.json` + v1 parity fixtures re-verified per CONFIG B4. Cleanest evidence, medium risk.
2. **Re-scope J0 warped acceptance** to CU-mean fidelity (already passing at all 5 CRFs) + ledger entry `per-edge-QG delivery [NEEDS VERIFY]`; let A7's "GATE-tested" rest on QG16 corroboration + zero-map identity + SEI round-trip. Cheapest; weakens the A7 evidence claim, must be disclosed in the paper's artifact appendix.
3. **Indirect per-QG probe at qg16**: sign-alternating ±6 per 16-cell inside single CUs on synthetic content; measure per-QG rate response differentially. No patch change; statistical rather than exact.

## Resource / repo state

- Repo `github.com/wagur1/prism_v2` current; local suite **90 passed / 5 out-of-tier skips**; secret-scan clean; bands/pins/patch untouched throughout.
- Kaggle spend: 3 J0 runs (v1, r2, r3), all CPU, ~35–50 min each at ERROR/FAIL points (r3 ran the full native tier).
- J1 (M2 checkpoint parity + smoke) is **gated** on this escalation's resolution per CONFIG F2 — do not launch until the owner picks a recovery option.
