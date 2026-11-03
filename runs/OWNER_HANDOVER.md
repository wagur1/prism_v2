# PRISM v2 — Overnight Handover (written 2026-11-04 ~01:55 local, owner asleep)

## What was done tonight

1. **Deliberation (3 rounds, English, Codex gpt-6-astra high effort + ZCode auditor):**
   - `deliberation/00_INPUT_PACK_V2.md` — frozen context: v1 val5k numbers (M2 −2.58%/−6.79%, M3/M4 aliased-to-M1/M2), step3 audit 3 root causes, README over-claim quarantine, literature anchors (PUT 40–50%, Różek −29.41%, RPP 16.27%).
   - `deliberation/CONFIG_V2.md` — **signed 9-…-style by both parties**: 8-arm design {M1,M2,R,QR,U,QU,C,QC}, Δx excluded from Phase 1 (F3 reopening rule), video deferred (F5), 3 amendments (QR gate replaces M3; H2′ = ≥1.0% + AP_small ≥ +0.5pp; video→Phase 2), promotion rule (dev QR vs M2 ≤ −1.5% both detectors → confirmatory J5).
2. **J0 code implemented by Codex, adversarially self-reviewed, independently reviewed by ZCode:**
   - Ported (provenance headers, v1 commit `a34d943`): x265 pin + quantOffsets patches (SHA-pinned), GATE-0 fixtures + net-effect verifier, FFmpeg/HM decoder adapters, CTU64→QG16 expansion.
   - New: retarget geometry (monotone separable piecewise-linear, Q16.16), SEI wire format (user-data, 3 kinds), box inverse, evidence ledger + claims checker.
   - Self-review found **10 real defects** (worst: identity adapter dropped padded samples — would have broken zero-map byte-identity) — all fixed with regression tests.
   - Tests: **79 passed / 5 skipped** (skips are fail-closed `[NEEDS VERIFY]` codec-fixture gates — they FAIL J0 if still skipping on the kernel).
3. **Kaggle:** kernel `htran123456/prism-v2-j0-codec-gate` v1 pushed and running (CPU, internet on; est. ~125 min). Cron monitors every 20 min, fail-closed, max 2 fix-and-rerun attempts, then escalation note.
4. Repo: `github.com/wagur1/prism_v2` — commits `12f0817` (CONFIG), `37dd82a` (J0), + kernel package. No tokens anywhere (scanned).

## What runs next (cron-driven, per CONFIG §F)

- J0 receipt → `runs/J0_STATUS.md` (PASS) or `runs/J0_ESCALATION.md` (FAIL after 2 attempts).
- J1 (M1/M2 smoke + timing receipt) needs the frozen v1 M2 checkpoint — located & parity-planned before launch; deliberately **not** auto-launched tonight.
- J5 confirmatory matrix stays gated behind J1 receipts + D6 promotion rule. No efficacy numbers will exist tonight — by design.

## Where to look in the morning

1. `runs/J0_STATUS.md` or `runs/J0_ESCALATION.md` — codec gate result.
2. `deliberation/CONFIG_V2.md` — the binding plan both parties signed.
3. `reports/J0_SELF_REVIEW.md` — the 10 defects and fixes.
4. This file + `git log` on `wagur1/prism_v2`.
