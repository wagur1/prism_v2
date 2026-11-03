# ZCODE Round 1 — Independent Position (auditor)

Basis: `00_INPUT_PACK_V2.md` artifacts + v1 dossier (`HOI_DONG_9/`). Numbers cited only from signed artifacts or the surveyed literature table.

## Positions on v2-D1..D7

### v2-D1 — Δx fate: **conditional revive, hard kill criterion**
- Root cause #1 (detach) is a one-line fix; root cause #3 (loss minimum at Δx=0) requires re-targeting the semantic loss to compare Φ(codec(x+Δx)) against the *teacher on the uncompressed frame* — not identity. Both are cheap to fix.
- Root cause #2 (Dirac rate proxy MAPE>5%) should NOT be repaired; it should be **removed**: Δx should be trained supervised-from-oracle exactly like ΔQ — the only recipe that produced a positive v1 result (M2). Oracle sweep over a small Δx basis (e.g., ±1, ±2, ±3 global sharpen/blur and per-QG-banded variants) on COCO500.
- **Kill criterion (falsifiable):** dev-split (COCO500) shows (a) oracle sweep finds ≥1 Δx pattern with BD ≤ −1% vs M1@same-CRF on dev, AND (b) student regression to it reaches Spearman ≥0.8 per-CTU — within 2 attempts. If either fails → drop Δx, ship M2+retargeting.
- Reasoning: v1 evidence shows Δx collapsed twice under proxy training; the published lever hierarchy (retargeting 28–50% ≫ QP reallocation single-digit) says Δx is a secondary lever. Do not spend the night's GPU budget on a third rescue attempt without the oracle-label path.

### v2-D2 — Retargeting: **IN scope, it is the core v2 lever**
- Literature: PUT m64712 ~40–50% (training-free), Różek −29.41%. QP-only ceiling observed in v1: −6.79% (M2, yolo). To reach a "solid" tier (−10~−15% consistent), retargeting must be in v2 core, not extended.
- Machine-side design: detector consumes the retargeted frame directly — no decoder-side inverse, no out-of-band side info needed for *task* evaluation (geometry travels in-band; spec the container: SEI message or per-frame header extension).
- Start with a 2-zone model (ROI quad/box preserved, background downscaled by factor s ∈ {1.5, 2, 4}) — not arbitrary mesh; ablate s. ROI source: union of SAM2.1-Base masks (cached) with DINOv2-Base PCA foreground prior, single-shot student predicts the retarget grid.
- Mandatory baseline: naive center-crop/letterbox retargeting at matched pixel budget (this is the honest "cheap" competitor — if our foundation-ROI retargeting doesn't beat center-crop retargeting, the foundation story dies; that is the v2 falsification headline).

### v2-D3 — Video: **Phase 2, not core**
- v1 measured nothing temporal; COCO-intra is the shakedown setting. Kaggle CPU 4 vCPU makes inter encoding slow (v1 note: "video random-access chậm").
- Plan: Phase 1 = COCO intra (protocol shakedown + paper core); Phase 2 = MOT17 low-delay P, short GOP (e.g., keyint=32, 1 keyframe/seq segment), ΔQ temporal allocation only (reuse GATE 0 verified channel). MOT17 in the paper as second task if wall-time allows; else future work. Decide at Phase-1 harvest, pre-registered, not post-hoc.

### v2-D4 — Teacher/oracle: **reuse v1 caches; extend oracle to retargeting labels**
- v1 cache exists: DINOv2-Base 500+500, SAM 2.1-Base 3,025 masks, 0.294 GPU-h. Reuse, don't recompute.
- Joint oracle (SAM2 masks ∪ DINOv2 PCA prior) is already prototyped at prism-vcm `a34d943` — port and freeze as `oracle_v2`. Oracle labels for retargeting = geometry derived from masks; for ΔQ = v1-style K=8 sweep, K reduction to 6 allowed if wall-time exceeded (built-in fallback in v1 runner).
- Student stays single-shot (MobileNetV4-Conv-Small @256², per v1 README) with two heads: ΔQ map + retarget grid; drop the Δx head unless D1 revive passes.

### v2-D5 — Phase-1 scope (minimum publishable matrix)
- Dev: COCO500 (train student, calibrate, spike retargeting).
- Eval: COCO val5k × {M1, M2, M2+R (retarget), M4' (ΔQ+R), center-crop baseline} × 5 CRF × 3 seeds × 2 detectors.
- Wall-time estimate basis: v1 tier1b = 264 imgs/shard ≈ 5.7 h CPU per shard for 13,200 observations → ~43 obs/min-equivalent; plan shards ≤6 h wall (Kaggle session cap 9/12 h GPU/CPU), budget ~20 shards eval + ~4 shards pilot. [NEEDS VERIFY against actual kernel timing; v1 numbers are the anchor.]
- Cut order (pre-registered): seeds 3→2 → drop Faster R-CNN (keep yolo) → shrink val5k→val2k. Never cut: stats protocol, paired bootstrap, Holm-Bonferroni.

### v2-D6 — Repo & claims hygiene
- Every quantitative claim in any md file must carry `(artifact: <path>, sha256: <...>)`. CI script scans `*.md` for `%`-numbers without a ledger reference and fails the check.
- README carries only: what the repo is, protocol status table, links to reports. No BD-rate in README until the harvest receipt exists.
- Logs from every Kaggle run pushed under `runs/` with SHA; pool tokens never enter the repo (krun.py handles rotation externally).

### v2-D7 — Port vs rewrite (module-by-module)
| Module | Decision | Why |
|---|---|---|
| x265 build + patch scripts | **PORT** | GATE 0 6/6 verified; rewrite risks silent codec-path regressions we have no budget to re-discover |
| GATE 0 harness + net-effect verifier | **PORT** | criteria frozen sha `316134d2`; reusable as-is for any new codec-path claim |
| Oracle sweep runner + K-reduction fallback | **PORT** | battle-tested 14 wrapper iterations |
| Shard runner + harvest + PCHIP/BD tooling | **PORT** | produced the only trusted v1 numbers |
| Student model + heads | **REWRITE** | new head set (ΔQ + retarget grid); Δx head behind a flag |
| Training loop | **REWRITE** | oracle-supervised joint objective; proxy path deleted |
| Docs/README/claims | **REWRITE** | hygiene policy above; v1 README is contaminated (−63.31% claim) |

## Blocking conditions for my sign-off
1. No number in repo prose without artifact reference (incl. fixing the v1 −63.31% inheritance — prism_v2 must not import that README).
2. Retargeting baseline = center-crop matched-pixel-budget is in the comparison set, else "foundation ROI" claims are unfalsifiable against the cheap alternative.
3. Stats protocol from §3 of input pack unchanged.
4. Kill criteria for Δx and for the foundation-ROI story are pre-registered before the eval run.
