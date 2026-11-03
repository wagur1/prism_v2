# ZCODE Round 2 + Round 3 input — Cross-critique of Codex, concessions, synthesis inputs

## A. Concessions to Codex (I was wrong or imprecise)

1. **Seed cut (my D5): retracted.** Codex is right — cutting 3→2 seeds while "never cut stats protocol" was self-contradictory. Adopt: 3 independent training seeds for every learned arm, or the run is explicitly labeled a pilot with no comparative claim.
2. **M2+R vs M4′ duplication: retracted.** Adopt Codex's 8-arm set {M1, M2, R, QR, U, QU, C, QC}. It is cleaner, adds the missing R-only and cheap-geometry controls.
3. **Timing anchor: retracted as fact.** My "~43 obs/min" was derived sloppily (Codex: 38.60 [DERIVED]) and the underlying equivalence (v1 tier1b observation ≈ v2 encode+decode+detector) is unverified. Adopt: J1 (smoke + throughput receipt) must produce the real per-stage timing before any J5 commitment. My shard plan becomes a sensitivity scenario only.
4. **Δx same-CRF gate: retracted.** BD needs full rate/task curves; a single-CRF point cannot establish BD ≤ −1%. Codex's reopening rule (full curves, dev selection, held-out test, ≤5% MAPE if any proxy reintroduced, 2 attempts max) replaces mine.
5. **H2 literal interval:** Codex's reading is correct — YOLO's −6.79% lies outside [1.0; 2.9)%, and no AP_small artifact was supplied. Accept the pre-registered amendment "H2′: savings ≥ 1.0% AND AP_small ≥ +0.5pp AND valid corrected inference", signed by both parties NOW, before any v2 eval run (so it is not outcome-motivated).

## B. My remaining critiques of Codex (for Round 3)

1. **Overnight scope is under-pinned in Codex's plan.** Codex's own arithmetic gives J5 ≈ 518 aggregate worker-hours (~87 six-hour job slots). That is a multi-day campaign, not an overnight run. CONFIG_V2 must pin the phase boundary explicitly: **overnight = J0–J3 (+J4 if receipts allow)**; J5 confirmatory launches only after J1 receipts and owner-visible plan. Otherwise we silently commit quota we cannot watch.
2. **Missing go/no-go decision rule for Phase-1 harvest.** Codex specifies kill criteria but no *promotion* threshold. Pre-register now (before dev results): if QR vs M2 on dev shows valid overlapping curves with point-estimate BD ≤ −1.5% on **both** detectors, promote to confirmatory J5; if not, the v2 paper scope degrades to M1/M2 (+H2′ fallback path) and retargeting goes to future work. This prevents post-hoc scope debates.
3. **K=8 is pack-anchored, not my invention.** Codex flags K=8/K=6 as unevidenced — but input pack §D1 (S6/D1) states "supervised-from-oracle-sweeps (K≈8–16 map QP/frame)". Adopt: K frozen in {8..16} at cache audit time, recorded in manifest, no silent reduction in confirmatory label generation (Codex's rule), K=6 fallback only for dev spikes with a ledger note.
4. **SEI payload risk:** Codex's geometry-in-SEI is right, but GATE 0's zero-map byte-identity fixture must be explicitly re-run in v2 with the SEI-writing encoder build — a new user-data SEI in the stock path would break identity. CONFIG must add: stock/M1 path writes no SEI; zero-map identity fixture re-verified on the v2 build (this is a J0 gate item).
5. **Center-crop baseline definition needs one more pin:** C's crop rectangle selection rule (center 16:9 crop then letterbox to R's coded size?) must be frozen in dev and identical across CRFs/seeds; otherwise C is unfalsifiable.

## C. Points where I hold position (with reasons)

1. **Retargeting is core, not "candidate":** Codex's own geometry contract + gates make it promotable-by-evidence; calling it "candidate" changes nothing operationally. Adopt Codex's promotion gates as the definition of "core".
2. **Evidence-first repo (Codex D6): adopt fully**, including typed claim records beyond percentages.
3. **Port table (Codex D7): adopt fully** — it matches my Round-1 table with stricter acceptance fixtures. Better.

## D. Round-3 synthesis instructions (for CONFIG_V2.md)

- Merge: my Round-1 §B structure + Codex's 8-arm design, geometry contract, reopening rules, evidence ledger, port table.
- Sign as amendments: (i) M3→R replacement in the full-model gate (QR must beat M2 AND R; CI95 upper <0; both detectors); (ii) H2′ interval change; (iii) video deferred (no MOT claim in v2 paper unless Phase-2 gates pass).
- Phase boundary: J0→J3 overnight; J5 gated on receipts + promotion rule (§B2).
- Both parties sign by adding a `## SIGNATURES` section vote to CONFIG_V2.md.
