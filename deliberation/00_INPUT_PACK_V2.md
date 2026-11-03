# PRISM v2 — DELIBERATION INPUT PACK (FROZEN CONTEXT FOR BOTH PARTIES)

**Parties:** Codex (gpt-6-astra, effort high — implementer + skeptic) and ZCode (GLM — auditor, ARA Rigor D1–D6).
**Language:** English. **Output repo:** `github.com/wagur1/prism_v2` (empty, fresh start).
**Predecessor:** `github.com/wagur1/prism-vcm` (HEAD `a34d943`) + local dossier `C:\Users\Wagur1\Desktop\HOI_DONG_9\`.
**Mission:** agree on PRISM v2 development direction, implement it, cross-critique the code, then only run on Kaggle. Owner is asleep; no owner input available.

---

## 1. WHERE v1 LANDED (ALL NUMBERS FROM SIGNED ARTIFACTS, NOT PROSE)

### 1.1 Frozen-protocol evaluation — COCO val2017 5,000 images, x265 (patched, quantOffsets per-QG16), CRF grid {20,24,28,32,36}, 3 seeds, 19 shards, harvest receipt SHA-pinned (`results_tier1b/tier1b_val5k_final_report.json`, repo commit `acd209aa`)

BD-rate (negative = saving), PAVA-PCHIP axis @ equal mAP@[.50:.95]:

| Model | Definition | Faster R-CNN | YOLO11-L |
|---|---|---|---|
| M1 | stock codec anchor | 0 | 0 |
| M2 | ΔQ-only (single-shot student QP map, CTU64 17×30 → QG16 68×120) | **−2.58%** | **−6.79%** |
| M3 | Δx-only (pre-codec bounded pixel residual) | +4.55% | +7.60% |
| M4 | hybrid ΔQ+Δx | +1.81% | −0.41% |

### 1.2 Why M3/M4 failed — calibration gate audit (`docs/reports/step3_report.json`, Escalation #12, 6/6 unanimous, 2026-11-02)

`status = FAIL_CLOSED_DELTA_X_ZERO`, `delta_x_forced_zero = True`, `m3_aliases_m1 = True`, `m4_aliases_m2 = True`, 2 consecutive calibration failures. Three architectural root causes (verbatim):

1. `ProxyCodec.forward` detaches the feature before the reconstruction conv → **zero post-codec gradient reaches the residual head**.
2. Single-layer Dirac proxy rate estimator **fails ≤5% MAPE against x265 entropy coding**.
3. Pre-codec semantic loss `1 − cos(Φ(x+Δx), Φ(x))` attains its **global minimum at Δx = 0** → head collapses to zero.

So in val5k: M3 ≡ M1 (bytes 971,589,756 vs 971,581,774) and M4 ≡ M2 (bytes 977,364,401 vs 977,366,858). The measured deltas are ΔQ-only effects.

### 1.3 Open honesty issue (must fix in v2, non-negotiable)

`prism-vcm` README claims: *"Tầng 1a Step 3 Pilot ✅ PASS (… BD-rate −15.90% YOLO11-L, −63.31% Faster R-CNN)"* — links to `docs/reports/STEP3_M1_M4_EMPIRICAL_REPORT.md` **which does not exist**, and the numbers contradict the frozen-protocol val5k report. This is the same over-claim pattern the v1 council quarantined (source S7). v2 repo must never contain an unbacked number.

### 1.4 GATE 0 (codec control channel) — PASSED 6/6, reusable asset

x265 patched; `quantOffsets` per-QG verified: plus6/minus6/checkerboard sign fidelity, zero-map byte-identity with stock (SHA-256), two independent decoders (FFmpeg + HM-16.2). CQP kills quantOffsets → **CRF primary** (`aq-mode=1, aq-strength=1.0, hevc-aq=0, cutree=0, qg-size=16`). Net-effect metric (base-drift removed) ratified criteria v3, sha `316134d2`. 11 escalations on record.

## 2. LITERATURE ANCHORS (from our 2026-11 survey; BD-rate unless noted)

| Work | Task | Number |
|---|---|---|
| PUT RoI preprocessing + retargeting (MPEG m64712, VTM CE12) | VCM OD/OT | ~40–50% saving, training-free retargeting |
| Różek et al. 2025 (EURASIP JIVP) | VCM OD, ROI retargeting | max −29.41% (random access) |
| Yuan Zhang (ITU 2022) | VCM OD, Fast R-CNN + ffmpeg preproc | max 28.09% |
| RPP (Bilibili, arXiv 2301.10455) | HVS streaming, NN pre-filter | avg 16.27%, best −39.77% (VMAF, H.265) |
| Netflix Film Grain Synthesis | HVS, grainy | ~30% |
| NETINT cloud-gaming ROI | HVS | 33%+ (SSIM) |

Implication: spatial retargeting is the strongest published lever (28–50%); bounded QP reallocation alone (|ΔQ|≤6) lives in the single digits for intra images. No published work uses SAM2/DINOv2 as ROI extractor for VCM — the novelty slot is intact.

## 3. CARRIED-OVER CONSTRAINTS (from v1 CONFIG v1.3/v1.4 — binding unless we explicitly amend)

- **Stats protocol:** any comparative claim needs ≥3 independent seeds, cluster bootstrap 95% ≥1,000 resamples, paired per-image, Holm–Bonferroni over the tested family, BD-rate on the rate axis @ equal task performance (PCHIP log-rate, non-monotonic → per-QP + BD-INVALID-RAW).
- **Gate carried from v1.3 §D:** proposed full model must reach BD ≤ −3% vs M2 AND vs M3, CI95 upper bound < 0.
- **H2 fallback (pre-registered):** if coupling fails, M2-only paper is acceptable with −BD ∈ [1.0; 2.9)% and AP_small ≥ +0.5pp (M2 yolo already exceeds this: −6.79%).
- **Claims language:** "no out-of-band side information" (in-band signaling only), no "task-agnostic" without the Adversarial Relevance Probe suite; numbers enter abstract only after runs exist.
- **Infra:** Kaggle pool only (19 accounts, P100/T4 ×2, ~30 h/week each; CPU 4 vCPU for x265 — intra COCO encode feasible, video random-access slow; /kaggle/working ~20 GB). Tokens NEVER in repo. Encoder pins: repo-pinned x265 build + patch SHA logging, assembly on, two-decoder verification for any new codec-path claim.
- **Teacher budget:** DINOv2-Base + SAM 2.1-Base, ≤60 GPU-h total (v1 used 0.294 h for 500+500 cache on COCO500).

## 4. DISPUTES TO RESOLVE (v2-D1 … v2-D7) — each needs a position + falsifiable reasoning

- **v2-D1 Δx fate:** (a) revive Δx by fixing all three root causes (differentiable proxy without detach; calibrated rate estimator or oracle-supervised Δx; anti-collapse semantic loss targeting Φ(codec(x+Δx)) vs teacher, plus rate penalty), or (b) drop Δx, ship M2-only, keep retargeting as the second lever. Decide with a kill criterion (e.g., dev-split calibration pass ≤ N attempts, else drop).
- **v2-D2 retargeting channel:** adopt machine-side retargeting (ROI up-weighted region, background downscale; detector consumes retargeted frame directly — no decoder inverse needed, compatible with "no out-of-band side info" if geometry is signaled in-band). In scope for v2 core or extended? Grid/geometry spec? BD-rate expectation vs PUT 40–50%?
- **v2-D3 video:** MOT17 temporal ΔQ allocation in v2 core (QP-map is naturally temporal) or COCO-intra only for v2 paper + MOT as future work? Kaggle CPU budget reality check.
- **v2-D4 teacher/oracle reuse:** reuse v1 caches (DINOv2-Base 500+500, SAM 2.1-Base 3,025 masks) + extend oracle sweep to Δx-space labels? Joint SAM2+DINOv2 oracle (already prototyped in prism-vcm HEAD `a34d943`) vs per-encoder fusion?
- **v2-D5 experiment scope phase 1:** minimum publishable matrix on Kaggle (detectors × CRF × seeds × datasets), job wall-times, what to cut first.
- **v2-D6 repo & claims hygiene:** fresh repo layout, evidence policy (every number → artifact SHA), README rules, log-push protocol, cron monitoring.
- **v2-D7 code reuse:** what to port from prism-vcm (patched x265 build scripts, GATE 0 harness + verifier net-mode, oracle sweep, shard harvest) vs rewrite in prism_v2. Porting saves days; rewrite risks regressions. Decide per-module.

## 5. DELIBERATION PROTOCOL (2-party)

1. **Round 1 (independent):** each party posts positions on v2-D1…D7 with ARA-rigor reasoning (evidence relevance, falsifiability, scope calibration). No "agree with prior doc" — every position needs its own reasoning or a cited artifact.
2. **Round 2 (cross-critique):** each party attacks the other's weakest points (≥2 disputes each), concedes with reasons where convinced, lists remaining deadlock.
3. **Round 3 (synthesize):** ZCode drafts `CONFIG_V2.md` (sections A–H: architecture, codec contract, training, experiment protocol, falsification table, Kaggle phase plan, claims policy, roadmap/roles). Both parties sign by explicit vote; unresolved items escalate to a documented decision with default-safe choice.
4. **Then:** Codex implements module-by-module; ZCode reviews each module (rigor + code review) before merge; GATE-style spike before any training code; Kaggle runs only after both parties declare the matrix OK. All runs via pool rotation; logs pushed to repo; no token ever committed.

## 6. SUCCESS CRITERIA FOR THE OVERNIGHT RUN

1. `CONFIG_V2.md` signed by both parties in `deliberation/`.
2. Working code in `prism_v2` implementing Phase-1 scope: at minimum M1/M2 reproducibility on a small pilot + the first Δx-fix or retargeting spike, with unit tests and GATE-style verification.
3. All code pushed; kernel package ready or launched; evidence ledger started.
4. A written handover report for the owner (what ran, what passed, what failed, next actions) — honest numbers only.
