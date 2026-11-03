# PRISM v2 — CONFIG_V2 (Round-3 synthesis; binding after both signatures)

Sources: `00_INPUT_PACK_V2.md` [P], `zcode_round1.md`/`zcode_round2.md` [Z], `codex_round1.md` [C].
Convention: [PROPOSED] = design choice, not measured; [NEEDS VERIFY] = pending artifact/fixture; protocol thresholds are design constants, not performance claims. Historical/literature quotations retain their source and verification status.

## A. Architecture & contracts

- **A1 Student (ported):** preserve the single-shot M2 backbone/ΔQ head (CTU64 → QG16 grid) and checkpoint compatibility. Reported MobileNetV4-Conv-Small @256² architecture [NEEDS VERIFY at port]. Add a separately trained saliency head/model without changing the frozen M2 path; QR is explicit composition, joint training deferred.
- **A2 Δx head: EXCLUDED from Phase 1** (no dormant training path). Reopening only via the signed Δx spike rule (§E-F3).
- **A3 Retarget geometry:** continuous, separable (H+V), monotone piecewise-linear map over the full source frame; knots at QG16 boundaries incl. partial edge cells; destination interval width ∝ source width × (1 + r), r ∈ [0,1] from bounded saliency marginals (empty ROI ⇒ uniform; max saliency ⇒ 2× weight). Reject non-monotone or zero-width quantized maps. No holes/overlaps.
- **A4 Dev configurations:** exactly 2 — output ≈ source size, or ≈ half per dimension. Coded dims padded to multiples of 16; visible rectangle recorded; all spatial baselines use identical coded output dims; interpolation/antialiasing frozen before eval.
- **A5 Geometry signaling:** serialized into HEVC user-data SEI (version, original/visible dims, quantized knots). Encoder and evaluator consume the same quantized map; total AU bytes (incl. SEI and required headers) count in rate. Spatial baselines likewise transmit geometry required by the evaluator; no evaluation-time sidecar may supply missing geometry. Stock/M1 and M2 paths write no SEI. Payload fields/widths, including crop/resize metadata, frozen via serialization tests before any efficacy run [NEEDS VERIFY at J0].
- **A6 Evaluation geometry:** detector runs on decoded retargeted frame; undo detector resize/letterbox and account for the visible rectangle before inverse-mapping predictions onto original coordinates. Crop/resize baselines use their own coordinate transforms; objects outside a crop remain in unchanged COCO annotations. Original areas retained for AP_small.
- **A7 Q+R composition:** source ΔQ field resampled into retargeted geometry, reduced to destination QG16 grid, |ΔQ| ≤ 6 preserved; grid dims derived per coded frame (17×30 is an example, not a constant). Adapter frozen + GATE-tested before use.

## B. Codec contract (inherited from GATE 0, re-verified on v2 build)

- **B1 x265 pinned build + quantOffsets patch** (source/patch/compiler/binary hashes recorded; assembly on). CRF primary: `aq-mode=1, aq-strength=1.0, hevc-aq=0, cutree=0, qg-size=16`; CQP excluded (kills quantOffsets — [P] §1.4). Phase 1 is COCO-intra only; manifests reject non-intra jobs.
- **B2 CRF grid {20, 24, 28, 32, 36}**, frozen before test contact.
- **B3 Zero-map byte-identity** with stock re-verified on the v2 build (SHA-256) — J0 gate item, re-run after SEI writer lands.
- **B4 Two independent decoders** (FFmpeg + HM) for any new codec-path claim (SEI, retargeted dims, warped-QG adapter).
- **B5 Measurement:** net-effect (base-drift-removed) metric for control-channel verification, with recovered criteria `316134d2` and fixtures [NEEDS VERIFY; abbreviated identifier is not an artifact SHA-256]. BD-rate always on rate @ equal task performance axis (PCHIP log-rate over a declared common interval; insufficient overlap or non-monotonic raw ⇒ BD-INVALID-RAW + per-CRF). Freeze overlap-validity rules before efficacy runs; legacy PAVA repair is audit-only. "Fewer bits at same CRF" is never a BD claim.

## C. Training (oracle-supervised only)

- **C1 No differentiable proxy path in Phase 1** (ProxyCodec/Dirac estimator not ported). ΔQ trained supervised-from-oracle, recipe ported from M2 [NEEDS VERIFY at port].
- **C2 Oracle:** v1 sweep machinery ported; **K frozen in {8..16}** at cache-audit time as a design choice, recorded in manifest; silent K reduction prohibited in confirmatory label generation; K=6 allowed only for dev spikes with ledger note. Freeze identity/control candidates, candidate list, scoring CRFs/rule, training-label count, and codec/build provenance before launch; scoring counts real bitstream bytes. Historical K remains [NEEDS VERIFY].
- **C3 Teacher caches:** v1 DINOv2-Base 500+500 / SAM 2.1-Base 3,025 masks reused only after identity/transform/split audit; incompatible entries recomputed. Joint SAM/DINO fusion = experimental candidate; SAM-only / DINO-only / fused compared on the same dev IDs through real-codec downstream evaluation. Adopt [C] §v2-D4's cache identity, alignment, fusion/PCA fitting, and best-single-teacher fallback safeguards; joint-foundation claims require a confirmatory ablation. GPU budget ≤60 h total incl. history; stop before the next job would exceed it.
- **C4 Saliency/retarget student:** trained on training IDs only, 3 independent seeds; selection on dev only. Val2017 (5,000) untouched until confirmatory; checkpoints/configuration frozen before test contact. Confirmatory deployment uses students; teacher-derived geometry is limited to labeled engineering spikes or separately labeled upper bounds.
- **C5 Split hygiene:** recover and audit parent split manifests [NEEDS VERIFY]; dev (500) / held-out (val5k) / train disjointness enforced by manifest. Training labels use training IDs only; dev scoring does not authorize training on dev IDs.

## D. Experiment protocol (confirmatory matrix)

- **D1 Arms (8):** M1 stock; M2 ΔQ; R retarget-only; QR = ΔQ∘R; U uniform resize; QU; C center-crop (crop selection and resize/letterbox rules frozen in dev, identical across CRFs/seeds); QC. U/C use R's pixel budget; QU/QC use the declared ΔQ adapter under U/C's respective transforms with the same ΔQ source. Aliased arms recorded as aliases, not independent evidence.
- **D2 Grid:** 8 arms × CRF{20,24,28,32,36} × 3 independent training seeds (learned arms: M2, R, QR, QU, QC; pair M2/saliency seed blocks across compositions; deterministic M1/U/C shared across seeds via content-addressing) × 2 detectors (Faster R-CNN, YOLO11-L, frozen weights and preprocessing) × COCO val2017 5,000. Repeated deterministic inference creates no extra seeds; smaller engineering pilots support no comparative efficacy claim.
- **D3 Primary comparison family (Holm-Bonferroni):** M2:M1, QR:M2, QR:R, R:U, R:C, QR:QU, QR:QC — each on both detectors (14 BD tests). Add H2′ AP_small on both detectors if claimed (16 tests total), and any other claimed endpoints, to the frozen family before test contact. For a predeclared M1/M2-only fallback, the family is BD and AP_small on each detector (4 tests); freeze branch/family before held-out contact. Bootstrap: paired image clusters across arms/CRFs, ≥1,000 resamples, 95% CI, dataset AP and BD recomputed per resample; paired seed blocks resampled as units; report seed-wise results. D4/D5/F4 require Holm-corrected inference at α=0.05 as well as their thresholds.
- **D4 Full-model gate (AMENDMENT-1, signed in §I):** QR must reach BD ≤ −3% vs **M2 AND vs R** (replaces M3), CI95 upper < 0, both detectors.
- **D5 Fallback paper gate (AMENDMENT-2):** H2′ = M2 vs M1 savings ≥ 1.0% AND AP_small gain ≥ +0.5pp on **both detectors**, with valid corrected inference under D3 (replaces v1 H2 interval [1.0;2.9)%). Freeze the AP_small comparison operating point/aggregation before test contact. Historical M2 BD alone does not establish this gate.
- **D6 Promotion rule (pre-registered):** after at most the 2 A4 configurations, dev (COCO500) QR vs M2 must have valid overlapping curves + point-estimate BD ≤ −1.5% on both detectors, and QR vs R must have valid overlapping curves + negative point-estimate BD on both detectors. J3's teacher-derived screen selects the candidate for J4; selected J4 students must satisfy this rule on dev before full J5, with seed aggregation frozen before scoring. This is resource triage, not comparative evidence. Otherwise v2 paper scope = M1/M2 (+H2′ path), retargeting → future work.
- **D7 Report:** failures, missing shards, invalid curves retained in report; no number released from incomplete harvest.

## E. Falsification table (frozen)

- **F1 Codec gate (J0):** plus6/minus6/checkerboard sign fidelity; zero-map identity; two-decoder match; SEI round-trip; stock/M2 paths SEI-free; quantized-map validity, box-coordinate round-trip, and warped-QG/partial-cell fixtures. Any fail ⇒ stop before adding or running training code.
- **F2 M2 port gate (J1):** frozen-input ΔQ outputs match v1 checkpoint on shared fixtures; throughput receipt produced. Fail ⇒ isolate module.
- **F3 Δx spike rule (deferred, separate sign-off):** ≤2 preregistered development attempts; include identity candidates, select on dev using real-codec full curves, and test on disjoint held-out images. Student must retain oracle benefit with useful nonzero output, BD ≤ −1% vs M1 full-curve, CI95 upper <0, and inherited seed/bootstrap/multiplicity safeguards. Any reintroduced differentiable proxy must pass ≤5% MAPE and finite, nonzero post-codec gradient checks. Failure at the attempt limit ⇒ branch closed.
- **F4 Retargeting promotion:** per D6/D4; foundation-ROI superiority claim requires R > U/C and QR > QU/QC (CI95 upper <0). Geometry result without that supports only a narrower claim.
- **F5 Video gate (future, AMENDMENT-3):** measured declared-GOP throughput on Kaggle CPU + control-channel and two-decoder re-verification in that mode + completion forecast within available allocation + signed task/sequence/split/seed/statistical-cluster plan before results; else no MOT/temporal claim anywhere.

## F. Kaggle phase plan

| Job | Content | Gate/exit |
|---|---|---|
| J0 | Codec build + GATE-0 fixtures + SEI serialization + geometry round-trip | F1 pass |
| J1 | M1/M2 smoke: 32 mixed-size imgs × 2 arms × 5 CRF × 1 frozen checkpoint × 2 detectors; per-stage timing receipt | F2 pass; receipts stored; engineering only |
| J2 | Cache audit + missing teacher entries (≤60 GPU-h cap) | manifest validated |
| J3 | Dev spike: retarget geometry ×2 configs with frozen M2 checkpoint and teacher-derived geometry; ΔQ labels on train IDs, oracle scoring on COCO500 | preliminary D6 screen; teacher variants/scoring budget frozen |
| J4 | Train students (3 seeds; M2 replication + saliency head if J3 passes) | checkpoints + dev selection frozen; student D6 check if retaining R/QR |
| J5 | Confirmatory val5k matrix (§D), or predeclared M1/M2-only fallback with the same detectors/CRFs/seeds/held-out set | J1 receipts + J4 completion + recorded go; full matrix additionally requires student D6 pass |
| J6 | Harvest + corrected stats + report | D7 |

- **Overnight boundary:** J0–J3 (+J4 if receipts allow); an upper scope, not a completion promise. J5 requires explicit go recorded in `runs/GO_J5.md` with both-party matrix approval, an owner-visible resource plan based on J1/J4 receipts, frozen checkpoints/inference family, and either student D6 pass or the predeclared M1/M2 fallback decision.
- Job wall target ≤6 h (allocation, not a verified session cap); shard keys complete (split/arm/seed/CRF/codec/checkpoint); peak-storage guard ~20 GB; all experimental runs on the Kaggle pool, rotation external (krun.py); tokens never in repo; every run's sanitized logs+hashed receipt pushed to `runs/`; stale ≠ failed. Size shards from measured throughput/storage and available allocation; shared encodes are not multiplied by detector count. Cut optional searches first; if confirmation does not fit, deliver a labeled pilot and defer it without cutting required seeds, detectors, CRFs, held-out IDs, or claim-defining controls.

## G. Claims & evidence policy

- **G1 Typed claim records** in `evidence/ledger.jsonl`: measured / literature / design-constant / derived-estimate / rejected-historical; each measured claim: metric+unit, detector+weights, split manifest, seeds, CRFs, checkpoint, commit, build/patch hashes, analysis configuration, uncertainty, validity, result/harvest artifact SHA-256. Estimates record formula, inputs, assumptions, and verification status; hashes/locators resolve to immutable evidence.
- **G2** `scripts/check_claims.py` validates ledger + flags uncited quantitative prose; regex is a tripwire, manual review decides support.
- **G3** README: scope + status + links only; no BD-rate until harvest receipt exists. v1's −15.90%/−63.31% claims are quarantined; prism_v2 inherits no v1 success flags. The v1 M3/M4 alias-versus-BD inconsistency ([P] §§1.1–1.2) remains unresolved pending per-image/per-CRF hashes, predictions, and integration inputs; it supports no numerical Δx effect claim.
- **G4** Literature numbers (PUT ~40–50%, Różek max −29.41% in random access, RPP avg 16.27%/best −39.77% on VMAF) are quotations from [P] §2 [NEEDS VERIFY against external sources]; publication requires verified source links and task/codec context, never treatment as our targets/forecasts. Novelty remains a hypothesis pending verified literature review; M2's observed saving is not a QP ceiling.
- **G5 Inherited claims language:** "no out-of-band side information" requires A5; no "task-agnostic" without the Adversarial Relevance Probe suite. Quantitative abstract claims require validated runs/harvests. Phase-1 wording is COCO-intra preprocessing; composition alone establishes no joint-training mechanism.

## H. Roadmap & roles

1. Codex implements J0 modules first (codec contract + geometry + SEI); ZCode reviews each module (rigor + code) before merge to main.
2. GATE-style spike before any training code. All tests green + both-party matrix OK ⇒ only then Kaggle runs.
3. ZCode monitors runs (cron/poll), pushes logs, maintains ledger; Codex fixes from receipts. Adopt [C] §v2-D6's log/monitoring protocol: append-only events, resource/config manifests, immutable receipts, secret-scanned bundles, a serialized exporter/single harvest writer, and idempotent recovery from verified missing work. Heartbeat/poll every 10 minutes; 3 missed heartbeats means stale for inspection. Large artifacts remain external with hashes/locators; local temporary cleanup follows durable receipts. Disputes → documented escalation with default-safe choice.
4. Handover report to owner after overnight phase: what ran, receipts, pass/fail, next actions.
5. Adopt [C]'s **Module-by-module port versus rewrite** table and acceptance fixtures in full, as accepted by ZCode Round-2 §C.3, plus [C]'s proposed repository layout. Source hashes/parity evidence and exact harvest coverage/hash/pairing/duplicate checks are required; missing fixtures remain [NEEDS VERIFY], never PASS. This CONFIG governs conflicts; unresolved differences use the documented escalation rule.

## I. Signed amendments (Round 3)

- **AMENDMENT-1 (D4):** full-model gate comparisons replace M3 with R. Proposed by Codex Round-1 §v2-D2, accepted ZCode Round-2 §D.
- **AMENDMENT-2 (D5):** H2′ replaces v1 H2 interval. Proposed by Codex Round-1 §v2-D5, accepted ZCode Round-2 §A.5; detector scope and endpoint registration are completed in D3/D5.
- **AMENDMENT-3 (B1/F5):** video deferred to Phase 2; no MOT/temporal claim in the v2 paper unless F5 passes. Agreed in both Round-1 §v2-D3 positions and listed as amendment (iii) in ZCode Round-2 §D.

All three amendments and A2's Phase-1 Δx exclusion become binding only after both parties sign this revised text. ZCode Round-2 §A.4 accepts the corrected reopening rule, but is not itself a signature accepting Phase-1 exclusion.

## SIGNATURES

- **ZCode (auditor):** SIGNED — 2026-11-04 — reviewed the 13 Codex edits against both round documents; all accepted (D6 QR-vs-R condition, D3 16-test family, G3 alias-inconsistency note, §H port-table adoption). Config is binding. Launch gates (F1/F2, D6 promotion, GO_J5 record) remain hard prerequisites for any Kaggle efficacy run.
- Codex (implementer): SIGNED — 2026-11-04 — ZCode countersignature on this revision required; all protocol and launch gates remain binding.
