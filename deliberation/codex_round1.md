# CODEX Round 1 + Round 2 — Implementer and skeptic

My position is to preserve the verified ΔQ path, exclude Δx training from Phase 1, and give retargeting a bounded opportunity to become the second core lever. COCO-intra is the evaluation scope. A working control channel, an interesting prototype, and a publishable improvement are separate milestones.

This is a proposal for Round 3, not a signed configuration, an implementation report, or authorization to launch the full matrix. This turn reads local documents and writes only this file; it performs no network actions. The two requested documents were read in order and in full. The v1 source tree, signed result files, cache manifests, and kernel timing logs are not present in this workspace and have not been independently inspected.

## Evidence and number conventions

- **[P]** means the frozen [input pack](00_INPUT_PACK_V2.md), SHA-256 **590a38f02e7ddbf55b25b905669034b6f07bd05af2d0837ec1aacb1ac54a4a91**. Section citations below identify the evidence being used. This hash authenticates the local pack, not the historical artifacts it describes.
- **[Z]** means [the auditor's Round 1](zcode_round1.md), SHA-256 **a4c626f34a0e82c561e742f86a962f4ae9697a6c854d2a1eb5b80410ce581f72**.
- **[PROPOSED]** identifies a design choice, threshold, allocation, or experiment count, not an observed result. **[DERIVED]** identifies arithmetic with stated inputs. **[NEEDS VERIFY]** identifies an estimate, assumption, or uninspected source detail. No proposed gain below is a performance forecast.
- Historical provenance supplied by [P]: val5k report at results_tier1b/tier1b_val5k_final_report.json, commit acd209aa; calibration audit at docs/reports/step3_report.json; reusable source HEAD a34d943; net-effect criteria identifier 316134d2. Full historical artifact SHA-256 values are **[NEEDS VERIFY]**. A commit or abbreviated criteria identifier must not be relabeled as an artifact SHA-256.

## Round 1 — Independent positions

### v2-D1 — Drop Δx from Phase 1; preserve a clean M2

**Decision:** choose the ΔQ-only path with a retargeting spike. Do not port the residual training path or fund a Δx oracle sweep in Phase 1.

[P] §1.1 gives M2 BD-rate of **−2.58% for Faster R-CNN and −6.79% for YOLO11-L**, whereas the nominal M3 results are **+4.55% and +7.60%**, and M4 gives **+1.81% and −0.41%**. More decisive than those labels is §1.2: **two consecutive calibration failures**, forced-zero Δx, a detached reconstruction path, a rate proxy failing the **≤5% MAPE** requirement, and a semantic loss minimized at zero. Removing a detach does not establish either a useful objective or transfer through real x265.

There is also an unresolved evidence inconsistency. The reported M3/M1 byte totals differ by only **7,982 bytes**, and M4/M2 by **−2,457 bytes** [DERIVED from §1.2]. Exact aliases under identical decoded predictions, CRFs, and pairing should not produce the substantially different BD-rates in §1.1. Similar aggregate bytes alone cannot resolve this; inspect per-image/per-CRF hashes, predictions, and integration inputs. Until reconciled, the pack supports a working ΔQ effect and a failed residual mechanism, not a numerical estimate of Δx harm or benefit. Do not recycle M3/M4 as distinct successful ablations.

**Bet and kill criteria:** the useful inherited mechanism is M2, rather than the proxy-trained residual branch. Kill the proposed M2 port as a reproducible baseline if its zero-map identity, control-channel sign, or frozen-input parity checks fail. Block M2 efficacy claims until a valid held-out comparison supports them; a small smoke run need not numerically reproduce the val5k percentages. The Δx branch is already killed for Phase 1, so the implementation contains no dormant training path that can consume budget silently.

**Reopening rule [PROPOSED, later phase only]:** reopening requires a separately signed, bounded real-codec feasibility experiment. Allow at most **two** preregistered development attempts. Include the identity candidate; select candidates on development data and test selection on disjoint held-out images. Require nonzero useful output and **BD ≤ −1% versus M1**, an upper 95% bound below zero, and the inherited multiple-comparison protocol, using complete real-codec rate/task curves. Supervised imitation must retain this benefit in the student; oracle benefit alone does not pass. If a differentiable rate proxy is reintroduced, it must additionally pass the inherited **≤5% MAPE** gate and a finite, nonzero post-codec gradient check. Failure at the attempt limit closes the branch. This threshold is a decision rule, not an expected saving.

### v2-D2 — Retargeting is a candidate core lever, with geometry and baselines specified

**Decision:** implement a training-free geometry spike first; promote retargeting into the core only after its contract and efficacy gates pass.

[P] §2 reports PUT at **approximately 40–50%**, Różek at a **maximum −29.41% in random access**, and Yuan Zhang at **maximum 28.09%**. These justify investigating spatial allocation. They do not forecast a COCO-intra x265 result: codecs, operating modes, data, tasks, and reporting of maxima differ. RPP's **16.27% average / −39.77% best** concerns VMAF and cannot set an OD target. Likewise, M2's **−6.79%** is an observed point, not a demonstrated ceiling on QP reallocation. Expected v2 BD-rate is **[NEEDS VERIFY; no defensible numeric forecast]**. The pack's literature novelty assertion is a hypothesis pending a verified search, not a repository claim.

**Geometry contract [PROPOSED]:**

1. Use a continuous, separable, monotone piecewise-linear map over the complete source image. Put source knots at **QG16** boundaries, including partial edge cells. Compute horizontal and vertical ROI marginals from a bounded saliency field. Allocate destination interval widths proportional to source interval width times **1 + r**, with r in [0,1]. Thus empty ROI yields uniform scaling, and maximal saliency has twice the interval weight. These constants are design choices; two-dimensional separability is a limitation to test.
2. Test only **two** development configurations: output dimensions approximately equal to the source, or approximately half of each source dimension. Pad coded dimensions to multiples of **16**, record the visible rectangle, and use the same actual output dimensions for every spatial baseline. Freeze interpolation and antialiasing before evaluation. If a quantized map loses strict monotonicity or allocates a zero-width interval, reject it. There are no holes, overlapping pasted regions, or implicit lost background.
3. Serialize the geometry version, original and visible output dimensions, and quantized knot locations in a specified HEVC user-data SEI payload. The encoder and evaluator use the same quantized map. Count the entire transmitted access unit, including SEI and required headers, in rate. Spatial baselines must likewise transmit any geometry required by the evaluator. Preserve the original zero-map byte-identity test without injecting new metadata into its stock/M2 path. Exact field widths and payload overhead are **[NEEDS VERIFY]**, to be frozen in a serialization test before efficacy runs. No evaluation-time sidecar may supply missing geometry.
4. Run the detector on the decoded retargeted image. Undo the detector's own resize/letterbox transform, then map predicted boxes back through the inverse monotone coordinate map. Evaluate against the unchanged original COCO annotations; retain the original areas for AP_small. Separability permits box extrema to be mapped consistently. No image reconstruction inverse is needed, but coordinate inversion is essential. A crop baseline maps its predictions back and still misses objects outside its crop; those ground-truth objects must not disappear.
5. For Q+R, resample the source ΔQ field into the new geometry, reduce it onto the destination QG16 grid, and preserve the inherited **|ΔQ| ≤ 6** bound. Derive CTU/QG dimensions from each coded frame. The v1 **17×30 → 68×120** example is not a universal shape. Freeze and test this adapter as a new codec-path claim.

Use distinct arms: **M1** (stock), **M2** (ΔQ), **R** (retarget only), **QR** (ΔQ plus retarget), **U** (uniform resize), **QU**, **C** (center crop with defined resize/letterbox), and **QC**. U/C use R's output pixel budget; QU/QC use the same ΔQ source and the declared geometry adapter. Freeze C's crop rectangle and resizing rule in development. If a full-size configuration makes a spatial baseline identical to M1 or M2, record and reuse that alias rather than presenting it as independent evidence. This tests both the geometry itself and whether its benefit survives comparison with a cheap geometry plus ΔQ. Foundation teachers are offline label sources; held-out deployment must use the student unless explicitly labeled as a teacher upper bound.

**Kill criteria [PROPOSED]:** stop immediately on an unparseable payload, inconsistent coordinate inversion, invalid map, or decoder disagreement. After the **two** development configurations, stop retargeting work for this phase if neither produces a valid overlapping rate/task curve with a negative point estimate for QR versus both constituent arms on both detectors. This is a resource triage rule, not statistical evidence. Final promotion requires **BD ≤ −3% versus M2 AND versus R**, upper 95% bounds below zero, and the inherited corrected inference protocol, on both detectors. Reject a foundation-ROI superiority claim unless R beats both U/C and QR beats both QU/QC with upper 95% BD bounds below zero after correction. A positive geometry result without this advantage supports only a narrower retargeting claim.

Replacing the inherited comparison against **M3** with **R** is an **explicit proposed amendment** to [P] §3: these are now the two actual constituent mechanisms. It is not already binding. Without both parties' signatures, report exploratory R results and do not claim that QR satisfies the old full-model gate.

### v2-D3 — COCO-intra core; temporal allocation deferred

**Decision:** no MOT17 efficacy run or temporal claim in Phase 1. The pack establishes COCO **5,000-image** intra results, a **4-vCPU** encoder environment, and **19** Kaggle accounts with approximately **30 h/week** each [P] §§1.1, 3. It supplies no measured video encode throughput. A pool's nominal capacity does not remove a sequential GOP dependency or make temporal QP allocation verified.

The existing GATE 0 result is evidence for its tested codec configuration, not a license to assume inter-frame behavior, reference quality propagation, or tracking stability. Keep **cutree=0** and the rest of the frozen intra contract in the primary work.

**Boundary and kill criteria:** the bet is that a defensible still-image study is feasible before adding temporal confounders. The Phase-1 manifest rejects non-intra jobs. A later temporal proposal must first measure a declared GOP on the actual Kaggle CPU, rerun control-channel and two-decoder checks in that mode, and forecast completion from measured throughput within the then-available allocation. Failure of any gate defers video. No MOT result is added merely because a short run happened to look favorable; task, sequence split, seeds, and statistical clusters must be signed before results. Paper wording must say COCO-intra preprocessing, not demonstrated video/track performance.

### v2-D4 — Reuse verified caches; provisionally port the joint oracle

**Decision:** reuse compatible v1 cache entries and the ΔQ oracle machinery. Treat the joint SAM2/DINOv2 prototype as a candidate label generator. Do not extend the sweep into Δx-space.

[P] §4 supplies **DINOv2-Base 500+500** and **SAM 2.1-Base 3,025 masks**, with the joint prototype at **a34d943**. A mask count is not an image count, and “500+500” does not establish image-ID overlap, split membership, or preprocessing. Before reuse, verify source-image hashes, teacher checkpoint identities, transforms, dtype, spatial coordinates, and split membership. Cache existence is not proof of compatibility.

The default fusion candidate combines normalized SAM occupancy and a DINO foreground prior in source coordinates, with **equal weights [PROPOSED]**. Fit PCA orientation, normalization, and any selection thresholds using training/development data only. Compare SAM-only, DINO-only, and fused labels on the same development IDs through real-codec downstream evaluation. Teacher-to-student agreement is diagnostic; rate/task improvement decides usefulness. Maintain separate named manifests for each codec/build/configuration. Shared semantic features can be reused, but a label optimal for one encoder setting is not automatically optimal for another.

Retargeting geometry derived from masks is a heuristic teacher target until scored through the real codec; do not call it an optimal oracle. Preserve the M2 student baseline and add a separately trained saliency head/model whose geometry is produced by the deterministic transform. Evaluate QR as explicit composition with M2. Joint training is a later hypothesis and cannot be credited with coupling gains that were never tested.

**Kill criteria:** reject any cache entry with unknown identity, incompatible transforms, or training/evaluation leakage. Recompute only missing valid entries. Drop fused labels in favor of the best single teacher if a frozen development comparison shows no downstream advantage; do not expand the fusion search after inspecting val5k. Joint-foundation claims remain unproven without their own confirmatory ablation. Stop teacher extension before the inherited **60 GPU-h total** cap would be exceeded, accounting for consumed history and the next job's estimate. **0.294 h** is the pack's cache timing anchor, not the cost of every SAM mask or a forecast for oracle encodes [P] §3.

### v2-D5 — Separate Phase-1 engineering from the confirmatory matrix

**Decision:** the immediate Phase-1 deliverable is M1/M2 reproducibility plus a real-codec retargeting spike. The minimum confirmatory matrix for the full two-mechanism and cheap-baseline story uses:

| Axis | Preregistered proposal |
|---|---|
| Training/development | Disjoint COCO training-side subsets, with a **500-image** development set [PROPOSED]; recover and audit old split IDs first |
| Held-out data | COCO val2017, **5,000 images**; no training, fusion fitting, geometry selection, or checkpoint selection on these IDs |
| Arms | M1, M2, R, QR, U, QU, C, QC: **8** [PROPOSED] |
| Detectors | Faster R-CNN and YOLO11-L, frozen weights and preprocessing |
| Codec operating points | CRF **{20,24,28,32,36}**, inherited |
| Seeds | **3 independent training seeds**, inherited minimum; pair corresponding learned systems and images |
| Inference | Paired image-cluster bootstrap, **≥1,000** resamples, **95%** intervals; account for seed variability; Holm–Bonferroni over the signed family |

Three invocations of a deterministic model are not three independent training seeds. Deterministic M1/U/C bitstreams and predictions may be content-addressed and shared across seed blocks; they do not create extra statistical samples. Teacher-only engineering spikes can use a single deterministic run but cannot support comparative claims.

The primary comparison family is **M2:M1, QR:M2, QR:R, R:U, R:C, QR:QU, QR:QC**, each on both detectors: **14 comparisons [PROPOSED/DERIVED]**. Add other tested claims to the preregistered correction family rather than reporting opportunistic significance. Bootstrap paired image IDs across arms and CRFs and resample independent seed blocks; recompute dataset AP and the resulting BD-rate for each resample. Do not average invented per-image AP values. Report seed-wise results as well.

Use PCHIP on log-rate over a declared common task-performance interval. Insufficient overlap or non-monotonic raw curves yields **BD-INVALID-RAW** plus per-CRF results, as [P] §3 requires. The historical **PAVA-PCHIP** numbers can be reproduced as labeled legacy diagnostics; isotonic repair cannot silently turn an invalid raw curve into a passing primary result.

**Kill/cut policy [PROPOSED]:** cut Δx and video first, then optional oracle/fusion searches. If the retargeting gates fail, shrink the scientific claim to M1/M2 and preserve both detectors, the full CRF grid, and the required seeds. If the full study does not fit measured capacity, complete a labeled development pilot and defer confirmation. Do not cut seeds, hide failed operating points, shrink held-out data after observing outcomes, or remove a baseline while retaining the claim it was meant to falsify. Job sizing and estimates appear below.

**H2 is unresolved:** [P] §3 literally requires savings in **[1.0, 2.9)%** and **AP_small ≥ +0.5 pp**. The pack's YOLO saving of **6.79%** lies outside that interval; Faster R-CNN's **2.58%** lies inside, but no AP_small result is supplied for either. Thus M2-only is an engineering fallback, not an already earned paper acceptance. I propose replacing the upper-capped interval with **savings ≥1.0%**, retaining AP_small **≥+0.5 pp** and valid corrected inference. Both parties must sign that amendment and specify its detector scope before a confirmatory fallback run; otherwise the literal gate remains and no success is declared.

### v2-D6 — Fresh evidence-first repository; fail closed on claims

**Decision:** create new documentation and an evidence ledger; inherit neither README results nor v1 success flags.

[P] §1.3 identifies unsupported README claims of **−15.90%** and **−63.31%** and a nonexistent linked report. The failure was evidentiary, so a percentage regex alone cannot repair it. Numbers such as AP_small, speed, sample size, and GPU-hours also need provenance. Design constants, literature quotations, rejected historical claims, and measured v2 results need distinct types.

Each measured claim record should identify its exact metric/unit, detector and weights, split manifest, seed set, CRFs, model checkpoint, source commit, patch/build hashes, analysis configuration, uncertainty, validity status, and immutable result/harvest SHA-256. Literature claims point to verified external sources; unverified pack quotations stay labeled as such. Planning estimates record their formula and inputs. A claims check validates ledger entries and hashes and flags uncited quantitative prose for review; it must not imply that a regex proves truth.

README initially contains scope, actual status, and evidence/report links. Promotion to a measured result requires a complete validated harvest. The report must retain failures, missing shards, and invalid BD curves. The v1 README issue is quarantined in this new repo; fixing the predecessor is outside this file-only task.

**Proposed log/monitoring protocol:** each Kaggle run writes append-only structured events, a configuration manifest, resource usage, checkpoint identifiers, and a hashed completion receipt. Completed immutable bundles are ingested by a designated exporter into runs/ and evidence/ after secret scanning. That exporter serializes commits and pushes of sanitized log/receipt bundles, using the run ID and manifest hash to prevent concurrent overwrite; interrupted runs export their last durable status on recovery. Large bitstreams/checkpoints remain external artifacts referenced by content hash; credentials and pool account secrets never enter bundles or Git. A **10-minute heartbeat and 10-minute scheduler poll [PROPOSED]** detect missing progress; **three missed heartbeats [PROPOSED]** marks a run stale for inspection, not failed science or permission to duplicate it. Use a single harvest writer and idempotent shard keys. Resume only missing work from verified receipts. Monitor CPU time, GPU-device time, free disk, and available account allocation. Cron/scheduler configuration is a future implementation proposal, not installed by this deliberation.

**Kill criteria:** a missing hash, stale result/config association, duplicate or incomplete shard coverage, leaked secret, or unsupported numerical claim blocks result promotion. Resource forecasts that exceed the approximately **20 GB** working-space limit or the available Kaggle allocation block the next job, not the recording of a failure. Manual review remains necessary for whether a cited artifact actually supports its prose.

### v2-D7 — Port verified contracts and M2 behavior; rewrite failed/new mechanisms

**Decision:** use selective ports with parity gates, not a blanket rewrite of the student or a wholesale copy of v1 runners.

[P] §1.4's **6/6 GATE 0 pass**, **11 escalations**, stock zero-map SHA identity, and independent **FFmpeg + HM-16.2** decoding represent hard-won knowledge. Preserve CRF with **aq-mode=1, aq-strength=1.0, hevc-aq=0, cutree=0, qg-size=16**, assembly enabled, the patch identity, and the base-drift-removed net metric. CQP is not a substitute because the pack says it kills quantOffsets. Conversely, §1.2 explicitly disqualifies the current residual/proxy training design.

**Kill criteria:** no port is accepted solely because its parent project passed. The codec/harness must reproduce its fixtures in the pinned v2 environment; M2 must match frozen inputs/outputs; harvest and statistics must reproduce a signed legacy analysis while honoring the new protocol wrapper. Missing historical fixtures means **[NEEDS VERIFY]**, not PASS. Reject or isolate the affected module if it fails; do not casually replace the x265 patch to make an integration test green. The per-module decisions and acceptance evidence are specified below.

## Round 2 — Cross-critique of ZCode

### Attack 1: v2-D5 violates its own statistical commitment and has no defensible CPU schedule

ZCode proposes cutting **3 seeds to 2** while saying “Never cut: stats protocol” and requiring the inherited protocol unchanged for sign-off [Z] D5 and blocking condition 3. Those positions are incompatible with [P] §3's **≥3 independent seeds**. Neither more bootstrap resamples nor a second detector substitutes for independent training seeds. Keep three or explicitly downgrade the run to a pilot with no comparative efficacy claim.

Its arm list also counts **M2+R** and **M4' (ΔQ+R)** separately without defining a difference. As written these are duplicates, and there is no R-only arm to test whether ΔQ adds anything. Distinct model manifests and a constituent R control are required before estimating workload.

The asserted **264 images/shard, 5.7 h CPU, 13,200 observations, ~43 observations/minute**, and **9/12-hour session caps** do not appear in [P]. The pack supplies **19 shards**, **5,000 images**, and the teacher cache timing, not a CPU stopwatch. Even accepting the auditor's unverified timing provisionally, **13,200 / (5.7 × 60) = 38.60 observations/minute [DERIVED]**, not 43. It must also define whether an observation includes an encode, a detector inference, both, or a reused encode. Thus **~20 eval shards + ~4 pilot shards** is not an evidence-backed allocation.

My replacement is the count-based plan below: isolate CPU encodes from detector inference, benchmark both on Kaggle, preserve required replication, and size jobs from receipts. The auditor's timing can be displayed as an explicitly unverified sensitivity scenario, never as an input-pack fact.

### Attack 2: v2-D1's proposed Δx gate does not establish a usable rate/task mechanism

“BD ≤ −1% vs M1@same-CRF” conflates two estimands [Z] D1. A same-CRF point provides bytes and task performance at that point. BD-rate requires multiple rate/task samples with a common task interval; it cannot be established by finding one favorable fixed-CRF pattern.

An oracle winner from a search over global **±1, ±2, ±3** sharpen/blur choices plus per-QG variants is selected evidence. The basis, parameter units, clipping, candidate count, and holdout procedure are unspecified. Real encoding could make that search more expensive than the proxy work it replaces. **Spearman ≥0.8 per CTU** does not show useful rate/task transfer and can be undefined for a constant global label. Ordering labels also does not ensure correct residual amplitude.

I concede that supervised real-codec labels can eliminate the need for a differentiable rate proxy. In that route the detached proxy should be removed from the path; it is not repaired by imitation training. But a valid gate must test the trained student through real x265 on unseen images and full curves. [P] provides **two failures** and a **≤5% MAPE** condition, not evidence that the other fixes or the proposed oracle search are cheap. This is why I defer Δx rather than spend Phase-1 capacity on this gate.

### Concessions, with reasons

- **Matched-budget center crop belongs in the comparison set.** ZCode's D2 falsification is persuasive: a foundation ROI method must survive a cheap spatial competitor, not just stock coding. I include both crop and uniform resize, and their ΔQ combinations, so the full-model comparison does not confound geometry with the existing QP gain.
- **Retargeting deserves the first second-lever spike.** The pack's OD/OT spatial results are a stronger relevance argument than its VMAF examples. I accept this prioritization, while rejecting the auditor's unsupported **−10 to −15%** target and its treatment of **−6.79%** as a ceiling.
- **Video belongs after the intra study.** ZCode's D3 recognizes the absence of temporal evidence and the **4-vCPU** bottleneck. I agree with deferral, without importing its suggested GOP as an already verified codec contract.
- **Reuse teacher caches, x265, and the control harness.** The pack establishes real reusable assets and scarce teacher budget. Reuse is conditional on manifests and parity; the joint oracle remains experimental.
- **Rebuild claims documentation.** The absent report and contradictory README figures justify starting fresh. I strengthen the policy to validate evidence associations beyond percentages.

### Remaining deadlock for Round 3

1. **Δx now versus later:** ZCode funds a two-attempt oracle rescue; I exclude it from Phase 1. Default if unresolved: M1/M2 plus the retargeting engineering spike.
2. **Retargeting promotion and geometry:** a two-zone box/background sketch does not yet define a complete map, multi-object handling, or box evaluation. I require the monotone contract, original-coordinate scoring, payload byte accounting, and constituent/cheap controls. No signed geometry means no retargeting efficacy claim.
3. **Student/oracle reuse:** ZCode rewrites all student heads and freezes the joint prototype. I preserve the known M2 path and gate the fusion/new head. Its **K=8**, fallback to **K=6**, **14 wrapper iterations**, and **MobileNetV4-Conv-Small @256²** are not evidenced in [P]; source inspection is **[NEEDS VERIFY]**. Changing K changes label generation and must not happen invisibly mid-matrix.
4. **Statistical cuts and job budget:** no reduction to two seeds; the CPU anchor and session limits need receipts. Default is fewer scientific claims or a deferred confirmatory run, not a weaker hidden protocol.
5. **Gate amendments:** both signatures are required to replace M3 with R in the full-model gate and to resolve the H2 interval/AP_small issue. Until then, exploratory results do not satisfy either amended gate.

## Proposed prism_v2 repository layout

This tree is a design proposal; only the present deliberation file is being created.

~~~text
prism_v2/
  README.md                         # Scope, actual status, evidence links
  pyproject.toml
  deliberation/
    00_INPUT_PACK_V2.md
    zcode_round1.md
    codex_round1.md
    CONFIG_V2.md                    # Round-3 signatures and explicit amendments
  configs/
    codec_intra.yaml
    dev.yaml
    phase1_confirmatory.yaml        # Frozen arms, seeds, CRFs, claim family
  src/prism_v2/
    codec/                          # Pinned x265 adapter, QG maps, SEI
    data/                           # Split/cache manifests and transforms
    teachers/                       # Cache readers, optional teacher extraction
    oracle/                         # Real-codec ΔQ scoring and label provenance
    models/                         # Preserved M2, new saliency student
    retarget/                       # Geometry, resampling, box inverse
    training/                       # Supervised objectives; no Δx proxy path
    evaluation/                     # Detector adapters, rates, AP, BD, bootstrap
    evidence/                       # Schemas, hashes, claim/receipt validators
  third_party/x265/
    PINNED_SOURCE.json
    patches/
  scripts/
    build_codec.*
    gate0.*
    check_claims.py
    harvest.py
  kaggle/
    package.py
    entrypoint.py
    monitor.py
    job_specs/                      # No credentials or account secrets
  tests/
    codec/
    geometry/
    data/
    evaluation/
    evidence/
    fixtures/                       # Small licensed fixtures and provenance
  evidence/
    ledger.jsonl
    manifests/
    receipts/
  runs/                             # Compact immutable logs and manifests
  reports/                          # Generated reports tied to ledger entries
~~~

Bulky datasets, caches, checkpoints, and bitstreams stay outside Git with hashes and artifact locators. The split manifests, schemas, code, and small verification fixtures belong in Git.

## Phase-1 Kaggle jobs and wall-time accounting

### What can actually be derived from the supplied timing

[P] §3 provides exactly one wall-time-like compute anchor: **0.294 h for the 500+500 teacher cache on COCO500**. It does not establish whether this is elapsed wall time or summed GPU-device time. Under a matched single-GPU, sequential cache-generation implementation, a repeated complete cache batch would take **approximately 0.294 h = 17.64 min [DERIVED estimate; NEEDS VERIFY]**. If this denotes two teacher passes over the same 500 images, it is **2.1168 s/source image**, or **1.0584 s/teacher-image pass [DERIVED; NEEDS VERIFY interpretation]**.

For m missing source images requiring both teachers under that same interpretation, use **T_teacher = 0.294 × m / 500 hours [NEEDS VERIFY linear scaling]**, plus measured setup/I/O. Rebuilding 5,000 such paired entries would be **2.94 h [DERIVED estimate; NEEDS VERIFY]**, not a request to compute them. Reusing valid entries requires no teacher inference but still has unmeasured read/validation time. Charge actual GPU-device hours against **60**, including prior attributable usage; do not assume two devices halve elapsed time.

There is **no input-pack timing anchor for x265, detector inference, student training, oracle candidate evaluation, bootstrap, or packaging**. A numeric schedule for all these jobs cannot honestly be derived from [P]. Their estimates below are parameterized until the first timing receipt. [Z]'s separate CPU assertion is shown afterward as a sensitivity calculation.

Define measured seconds per item: e_a for encoding arm a (including its preprocessing/SEI work), d for decoding and verification, f for Faster R-CNN inference, y for YOLO inference, and o for oracle scoring beyond those components. Measure rates with the actual **4-vCPU** worker and actual GPU. Let L be measured startup/staging time in hours and T_fit measured training time in hours per independent seed. For a serial job, estimate **T = L + [sum(n_a × e_a) + n_decode × d + n_F × f + n_Y × y] / 3600 hours [NEEDS VERIFY]**. If stages are pipelined, use measured end-to-end throughput rather than assuming perfect overlap.

### Launch order and estimates

Every numerical pilot size, job cap, or attempt count in this table is **[PROPOSED]**. Model/CRF/seed counts for the confirmatory matrix follow the proposal above. Estimated times remain **[NEEDS VERIFY]** until replaced by Kaggle receipts.

| Job | Work and dependency | Wall-time estimate and exit condition |
|---|---|---|
| J0: package, codec and geometry contract | After joint configuration/matrix approval: build the pinned codec, run plus6/minus6/checkerboard and zero-map fixtures, decode with FFmpeg/HM, round-trip SEI and box coordinates | **T_build + T_gate + L**, unknown from [P]. Instrument separately. Stop on any identity/sign/geometry/decoder failure, before adding or running training code. |
| J1: M1/M2 smoke and throughput receipt | **32 images × 2 arms × 5 CRFs × 1 frozen checkpoint × 2 detectors**; deliberately mix image sizes | **320 encodes, 640 detector-image observations [DERIVED]**. T = L + [160(e_M1 + e_M2) + 320d + 320(f+y)]/3600. Verify parity; this is engineering, not a three-seed claim. |
| J2: cache audit and missing teachers | Validate training/development IDs; reuse compatible entries; build only the missing paired cache entries | Audit time unknown; inference estimate **0.294m/500 h**, plus setup/I/O. For m=500, **~17.64 min** under the matched-anchor assumptions. Stop before the teacher budget would be exceeded. |
| J3: ΔQ labels and geometry development | Port ΔQ sweep; score fixed candidate sets with real x265; test at most **2** geometry configurations on the **500-image** development split, using a frozen M2 checkpoint and teacher-derived geometry | Oracle cost is proportional to **N_label × K × number of scored CRFs**, using measured encode/score time plus o; **K, training-label count N_label, and the actual scoring grid NEED VERIFY** from audited source/split manifests and must be frozen before launch. An 8-arm, 5-CRF, 2-detector screen is **20,000 encodes / 40,000 detector-image observations per geometry/teacher configuration [DERIVED]** before cache reuse. Multiply by the actual number of teacher variants screened; include training-label generation separately. No defensible total duration yet. Stop at the registered candidate/configuration limit. |
| J4: train frozen-scope students | After contract gates and dev selection: preserve M2 recipe; train saliency student and any required M2 replication for **3 independent seeds** on training IDs | **3 × T_fit + staging/cache I/O**, with T_fit explicitly covering the selected models per seed. Pack provides no training-time anchor. Benchmark the first seed and project remaining work; do not substitute repeated inference for training. |
| J5: confirmatory COCO evaluation | Freeze checkpoints/configuration before val5k; **8 arms × 5 CRFs × 3 seeds × 2 detectors × 5,000 images** | Nominal **600,000 encodes and 1,200,000 detector-image observations [DERIVED]**. Sharing deterministic M1/U/C across seeds gives **450,000 encodes and 900,000 observations [DERIVED]** if all learned arms still have distinct seed outputs. Apply the measured per-stage formula; retargeted image sizes may change e, d, f, and y. |
| J6: harvest, corrected statistics, report | Verify exact coverage, hashes, split separation, pairing and detector outputs; run the signed bootstrap/correction family | **T_ingest + T_bootstrap + T_report**, each unmeasured in [P]. Time a bootstrap batch before projecting **≥1,000** resamples. Release no comparative number from an incomplete harvest or invalid curve. |

Cache reuse in J5 is an implementation optimization, not a reduction in statistical replication. The deterministic arms number **3** and the seed-dependent arms number **5**, so the deduplicated encode count is **5,000 × 5 × (3 + 5 × 3) = 450,000**. Detector weights do not change the bitstream in this design, hence detector count does not multiply encodes.

**Shard sizing [PROPOSED]:** target at most **6 h** per job, but treat this as an allocation, not an established Kaggle session limit. At the inherited **19-way** image partition, shards contain **263 or 264 images [DERIVED from 5,000/19]**. Each shard must contain complete paired work for its assigned IDs, or use an explicit arm/seed/CRF task manifest whose harvest restores full pairing. Choose the actual partition from measured time and disk demand; do not equate account count with a required shard count. Abort/reduce the next shard before projected peak storage exceeds the approximately **20 GB** limit. Delete only verified local temporary artifacts after durable receipt creation.

### Sensitivity calculation using the auditor's unverified CPU anchor

For planning visibility only, suppose [Z]'s **13,200 observations in 5.7 h** means the same complete encode/decode/detector work as one detector-image observation above. This equivalence and the historical timing are both **[NEEDS VERIFY]**; shared encodes, detector differences, and retargeting can invalidate it. The implied rate is **38.60 observations/minute**.

Under that assumption, J1 would take **~0.276 h**, each full J3 geometry screen **~17.27 h**, and nominal J5 **~518.18 aggregate worker-hours**; the deterministic-cache scenario would be **~388.64 h [all DERIVED conditional estimates; NEEDS VERIFY]**. Over **19** perfectly balanced concurrent workers, J5 alone would have an ideal lower-bound makespan of **~27.27 h**, or **~20.45 h** with that cache scenario, excluding all other jobs and scheduling losses. With the proposed 6-hour job target, those totals require at least **87** or **65** job slots respectively. These are sensitivity calculations, not a launch promise or a conversion of CPU time into GPU quota.

Thus the auditor's unverified anchor itself does not justify approximately 20 six-hour evaluation jobs for this matrix. The only evidence-backed numerical compute extrapolation from the pack is the teacher-cache estimate. Obtain J0/J1 receipts before signing a concrete full-run allocation; if capacity fails, use the cut policy above and deliver a truthful pilot.

## Module-by-module port versus rewrite

These are module-level decisions based on [P], not claims about inspected v1 filenames or APIs. Recover each module from the pinned source and record its source hash before implementation. “Port” permits interface adaptation but requires preserved behavior and an acceptance fixture.

| prism-vcm module or responsibility | Decision | Acceptance evidence / reason to reject |
|---|---|---|
| x265 source pin, quantOffsets patch, build scripts | **PORT** | Record source, patch, compiler, binary hashes and assembly setting. Reproduce CRF control and stock zero-map byte identity. Reject unpinned or behavior-changing build. |
| GATE 0 fixture generation and runner | **PORT** | Preserve plus6/minus6/checkerboard cases and frozen settings. Extend fixtures for variable geometry; do not replace historical cases. |
| Net-effect/base-drift verifier | **PORT** | Recover exact criteria associated with **316134d2** and expected outputs. Reject using raw base drift as ΔQ effect. |
| FFmpeg/HM verification adapters | **PORT** | Pin both independent decoders; compare decoded samples under the declared format. Extend to new dimensions/SEI; fail on mismatch. |
| Image/color/padding and detector preprocessing | **PORT + isolate contracts** | Preserve M1/M2 pixels and detector inputs. Add explicit original/visible/coded coordinate metadata. Reject implicit geometry changes. |
| CTU64-to-QG16 ΔQ expansion and codec interface | **PORT + geometry adapter** | Preserve existing mappings on old fixtures; add partial-cell and variable-size fixtures. The warped-QG adapter is new and requires new GATE evidence. |
| DINOv2/SAM cache readers and extractors | **PORT** | Verify teacher/data/transform hashes and split provenance. Replace undocumented cache schemas with a validated adapter; no silent reinterpretation. |
| Existing real-codec ΔQ oracle sweep | **PORT core scoring; rewrite manifest wrapper** | Include identity/control candidates and real bitstream bytes. Freeze candidate list, K, CRFs, and scoring rule. Disable silent K reduction for confirmatory label generation. |
| Joint SAM/DINO fusion prototype | **PORT as experimental candidate** | Run unimodal/fused development ablations; verify PCA fitting/sign and spatial alignment. Reject promotion on mere prototype existence. |
| M2 backbone, ΔQ head, inference/checkpoint loading | **PORT** | Preserve checkpoint compatibility and frozen-input ΔQ outputs; architecture details are **[NEEDS VERIFY]**. A new second head is not a reason to destroy the baseline. |
| ProxyCodec, Dirac rate estimator, residual head | **DO NOT PORT into Phase 1** | Pack documents detach, failed calibration, and zero-minimum loss. Reopening requires the separate D1 gate, not a flag. |
| Retarget saliency head, geometry, resampler, SEI, box inverse | **NEW** | New mechanism: monotonicity, no holes, serialized-map equality, original-coordinate AP, full byte accounting, baseline comparisons. |
| M2 supervised training recipe | **PORT where verified** | Match labels, normalization, checkpoint selection, and independent-seed behavior. Do not inherit residual/proxy loss terms. |
| Multicomponent training orchestration | **REWRITE** | Explicit separate M2 and saliency training, provenance, deterministic resumes, no val5k selection. Any future joint objective is a distinct experiment. |
| Shard execution and restart logic | **PORT proven primitives; rewrite job schema** | Unique split/arm/seed/CRF/codec/checkpoint keys; no stale-cache reuse or silent candidate changes; measured resource estimates. |
| Harvest/receipt and coverage verification | **PORT + strengthen validation** | Reconstruct expected Cartesian coverage, reject duplicates/missing pairs, verify every artifact hash. Similar aggregate bytes are insufficient. |
| AP/detector evaluation adapters | **PORT + rewrite coordinate adapter** | Reproduce M1/M2 evaluation; verify inverse geometry against original annotations and original AP_small area groups. |
| PCHIP/BD integration primitives | **PORT with signed fixtures** | Recover legacy PAVA-PCHIP output for audit only. New primary wrapper enforces common support and **BD-INVALID-RAW**. |
| Bootstrap and multiplicity orchestration | **PORT verified resampling primitives; REWRITE protocol wrapper** | Must pair images, retain seed dependence, recompute dataset AP/BD, and apply the frozen Holm family. Reject any implementation that treats CRFs/detector rows as independent images. |
| Kaggle packaging, pool rotation integration | **PORT credential-free interfaces only** | Account/token handling remains external. No embedded credentials, unverified quota constants, or unbounded retries. |
| Heartbeat/monitoring and artifact exporter | **NEW minimal wrapper** | Idempotent runs, immutable receipts, secret scanning, single-writer ingestion, resource guards. Staleness must not manufacture scientific failure/success. |
| README, result badges, reports, claim checks | **REWRITE** | No inherited PASS flags or unsupported percentages. Every promoted number resolves to a complete, valid, hashed artifact and analysis. |

## One-paragraph summary

Preserve the verified x265/ΔQ mechanism and its GATE 0 assets, defer Δx rescue and video, and give retargeting a bounded COCO-intra spike with in-band geometry, original-coordinate task evaluation, and matched-budget spatial baselines. Keep three independent seeds and the full inherited inference protocol for comparative claims; obtain real Kaggle timing receipts before committing to the confirmatory matrix because the pack contains a teacher-cache anchor but no CPU evaluation timing. Promote no foundation, coupling, fallback, or performance claim without its specific evidence and gates, and require explicit Round-3 agreement on replacing M3 with R and resolving H2. Selective ports preserve reproducibility; new geometry, orchestration, and evidence controls carry the actual v2 work.
