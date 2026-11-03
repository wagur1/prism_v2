# J0 kernel package

The upload directory is `kaggle/job_specs/j0_gate0`. It contains only the Python
entry point and Kaggle metadata. Validation and command rendering are offline:

```text
python kaggle/package.py kaggle/job_specs/j0_gate0 --krun /path/to/krun.py
```

This prints `python /path/to/krun.py kernels push -p <absolute-job-spec-path>`.
It does not execute the command. The external wrapper's CLI was not available
in the reference directories; ZCode must confirm its argument convention.
The metadata owner follows the supplied v1 metadata (`htran123456`); adjust the
owner to the account selected by the wrapper before validating and pushing.

The kernel identity has a single editable source: the first `id` field in
`kaggle/job_specs/j0_gate0/kernel-metadata.json`. The entry point does not hardcode
the slug. If re-pushing an errored slug returns HTTP 409, the auditor can set
`id` to a fresh `owner/slug` and optionally update `title`, then rerun the offline
package validator before pushing. The existing r2 id is preserved here; no push
or network operation is part of this fix round.

## QG64 acceptance implementation and evidence hierarchy

The downloaded r2 JUnit report contains **68 collected, 67 passed, 1 skipped**.
The skip is the warped fixture's missing individual QG16 edge observations.
`runs/j0_out_r2/runs/j0_gate0_receipt.json` correctly remains FAIL. The earlier
recovery narrative below describes the preceding implementation, not a new PASS.

`run_retarget_fixture` now requires both forms of adapter evidence for M2/QR:

1. **Primary:** an additional CRF20 encode at `qg-size=64`, comparing every CU
   telemetry row to exactly one reduced adapter QG64 value at `rtol=0,
   atol=1e-6`. The independent expected grid is the mean of each 4x4 block of
   QG16 cells, saved as `offsets_qg64.npy`. The coded dimensions stay 128x80;
   all four QG64 blocks, including both bottom partial CTUs, must be covered.
   Every row must report `qg_size=64`; missing, corrupt, or nonfinite rows fail.
2. **Corroborating:** the existing QG16 CU-parent mean fidelity runs at all five
   CRFs. Their traces explicitly say `evidence=cu_mean`; coarse parents are
   permitted without claiming individual QG16 edge observations. A QG16
   failure still prevents acceptance even when QG64 evidence is available.

The native quantOffsets ABI retains its 16-cell storage for QG64, so the
encoder receives the original adapter buffer and the verifier receives the
reduced 2x2 oracle. For this fixture the bottom padded rows repeat the last
coded row; its full 4x4 block mean equals the native height-clipped mean. Offline
regressions verify this against the patch's scalar footprint calculation.

At `qg-size=64`, the QG parent spans one CTU64. A CU telemetry row therefore
refers to exactly one QG64 value, including at the partial bottom boundary;
smaller CU leaves may repeat that parent value. Equality is checked for every
row and coverage for every QG, so duplicate leaves cannot hide a missing block
or a conflicting observation. This is per-QG edge evidence at QG64. It does
not establish individual QG16 offsets or efficacy, which remains separately
gated by D6 at QG16 under CONFIG B1.

The explicit `qg_size_override=64` is used only by the two CRF20 acceptance
arms. Ordinary `EncoderConfig`, sign fixtures, and efficacy retain QG16.
The old insufficient-individual-QG16-edge exception is removed; the genuine
native/adapter stride mismatch exception remains. Native tests assert six
CRF20 runs, both QG64 equality results and QG16 corroboration, and propagate
fixture failures instead of converting them into skips.

**Kernel readiness remains blocked by the pinned native telemetry patch.**
In `third_party/x265/patches/x265_residual_telemetry.patch:148`,
`supported()` requires `p.rc.qgSize == 16`. Both `prismTelemetryFrame()` and
`prismTelemetryCUs()` return immediately when it is false (patch lines 183 and
207), emitting `x265_prism_telemetry_v2: unsupported AQ/refinement configuration`.
Consequently, a QG64 encode would provide no native `requested_offset` rows to
compare with the adapter. This is independent of CU partition choices.

The local patch, the downloaded r2 patch, the r2 receipt and `PINNED_SOURCE.json`
agree on SHA-256
`df3abe02bbc8428b2f1f4a620a4527ae39763b1ee9c8c164eec2ece7909daf59`.
The actual patched r2 source confirms the guard at
`runs/j0_out_r2/j0_stack/src/x265/source/encoder/prism_telemetry.cpp:73`, with
both early returns at lines 108 and 132. The implemented options override
cannot bypass that native guard. The new QG64 pass will fail on missing
telemetry with the current pinned build; it cannot honestly report PASS.

The Python acceptance implementation and offline regressions are complete,
but native acceptance is unproven. Supporting QG64 telemetry requires a native
instrumentation change and a matching patch pin; `PINNED_SOURCE.json` is
explicitly protected in this task, so neither was changed. Do not launch the
final kernel with the current pinned patch. Bands, `deliberation/`,
`net_effect.py`, `sei.py`, and `geometry.py` are unchanged.

### Collected-tier skip audit

The kernel's exact selection remains `tests/codec tests/geometry tests/evaluation`
(`j0_gate0.py:343`). All skip/xfail mechanisms in that selection are listed here:

| Location | Condition with a valid native `PRISM_CODEC_STACK` file |
| --- | --- |
| `tests/codec/test_native.py:18`, class `unittest.skipUnless` | Disabled when the variable names an existing file; applies to three native methods. Merely setting a nonexistent path still skips. |
| `tests/codec`, method-level `skipTest` / `skipif` / `expectedFailure` / `xfail` | None. Both former `FixtureNeedsVerify` handlers are removed. |
| `tests/geometry`, all skip / expected-failure mechanisms | None. |
| `tests/evaluation`, all skip / expected-failure mechanisms | None. |
| `tests/port_parity/test_deferred.py:6`, `unittest.skip` | Always skips historical replay until its signed bundle is recovered; outside the kernel tier. |
| `tests/port_parity/test_deferred.py:10`, `unittest.skip` | Always skips J1 parity until its checkpoint/expansion fixture is recovered; outside the kernel tier. |

There are no other skip markers/calls, `skipif`, `xskip`, or `xfail` in those
three directories, and no `conftest.py` overrides. Both historical/J1 placeholders
are now in `tests/port_parity/test_deferred.py` (lines 6 and 10), outside the
kernel selection. The kernel still rejects every collected skip or xfail.
With an existing stack file, no collected-tier skip can fire; invalid native
artifacts or missing telemetry now fail the tests.

Local verification this round: `python -m pytest tests/ -q` could not collect
(`No module named pytest`, exit 1) using the available Python 3.12.14 runtime.
Unittest discovery completed with **95 collected,
90 passed, 5 skipped, zero failures/errors**. The five are three absent-native-
stack skips and the two historical/J1 placeholders. `PRISM_CODEC_STACK` is unset
locally; the downloaded Linux binaries are not a runnable Windows stack. No
pytest-green or new native result is claimed, and no dependency was downloaded.
The requested pytest result with only two placeholder skips has therefore
**not** been achieved. Logs and the source/skip audit are in `runs/j0-qg64-*`.
The package validator, secret scan of all tracked files and these new logs,
and protected-file/whitespace checks pass. The port provenance manifest
updates only the changed Python bridge's destination hash.

## Execution and evidence

The standalone entry point clones public `wagur1/prism_v2` **main** into
`/kaggle/working/prism_v2`, records the resolved commit, installs missing build
tools and Python dependencies, and fetches the exact x265 and HM commits in
`third_party/x265/PINNED_SOURCE.json`. Both patch byte hashes are checked before
the build starts. The offline repo builder rechecks them, applies residual then
telemetry with no fuzz, and builds separate stock/patched x265 libraries and
header shims with assembly enabled. Its flags retain the v1 release/8-bit/shared/
NUMA configuration and HM diagnostic compatibility wrapper. HM's target is
`TAppDecoderStatic`; the other decoder is the system FFmpeg, whose binary is hashed.

The kernel exports `PRISM_CODEC_STACK` for subprocesses and runs:

```text
python -m pytest tests/codec tests/geometry tests/evaluation -ra --strict-markers --junitxml=...
python scripts/gate0.py --f1 --stack /kaggle/working/j0_stack/stack.json --output /kaggle/working/runs/j0_f1
```

The pytest tier must collect and pass the native acceptance methods; missing
tests, skips, xfails, errors, nonzero exits, or a missing/malformed report fail
the job. Historical telemetry replay and J1 frozen checkpoint parity placeholders
remain explicitly skipped under `tests/port_parity`; they have not been accepted
or replaced by fresh-build evidence.

F1 control coverage is all CRFs `{20,24,28,32,36}`, all six stock/no-map/zero/
plus/minus/checkerboard conditions, and ten seeded intra frames at 1920x1080.
Every stream is decoded by FFmpeg and HM and compared byte for byte. Stock,
patched no-map, and patched zero-map streams must be byte-identical and contain
no SEI. Numerical sign checks use the recovered **CRF20/GOP1/B0** fixture only;
the other CRFs retain identity, SEI-absence, and decoder checks. The v1 five QP
labels were repetitions at CRF20, not a five-CRF calibration. F1 records
`net_effect_crfs: [20]`; the kernel requires that attribution. Sign checks retain
the frozen criteria and coverage rules unchanged.

The retarget fixture maps a 130x98 source through a nonuniform quantized map to
a 113x65 visible rectangle in a 128x80 coded frame. It compares warped offsets
against an independent scalar area-integration oracle, verifies the requested
offsets in native telemetry including edge QGs, checks a nonzero encoded effect,
and round-trips geometry through actual R/QR access units at every CRF. M1/M2
access units remain SEI-free. Both decoders must reconstruct identical samples.
Nearest pixel sampling is a deterministic fixture stimulus, not an efficacy
interpolation policy. Its oracle and acceptance scope require auditor review;
no native result was inherited from v1.

Outputs are:

- `/kaggle/working/runs/j0_gate0_receipt.json`: versioned receipt with source
  commit, patch hashes/order, assembly setting, binary hashes, checks, timings,
  and hashes of the stack, F1 report, JUnit report, and logs.
- `/kaggle/working/j0_gate0.log`: human-readable progress and subprocess output.
- `/kaggle/working/runs/j0_gate0.events.jsonl`: append-only command, heartbeat,
  stage, check, and final-status events.
- `/kaggle/working/j0_stack/build.log` and `stack.json`: detailed build commands,
  compiler/source/shim provenance, and individual x265/HM build timings.
- `/kaggle/working/runs/j0_f1`: hashed bitstreams, telemetry, geometry, offsets,
  and F1/control reports. A controls-only PASS never sets F1 complete.

Every required receipt check starts as FAIL. Errors/timeouts retain FAIL for
unfinished checks, finalize logs and an atomic receipt, and exit nonzero. An
existing output receipt/log is never overwritten. Use a fresh Kaggle session.
An external hard kill can prevent finalization; absence of a valid final receipt
is failure, never permission to proceed. `training_authorized` remains false.

## Runtime estimate

**[NEEDS VERIFY; derived estimate, not a benchmark]** Assume four build workers
and one encoder worker per stream on a Kaggle CPU instance. Budget, in minutes:

```text
T = setup + 2*x265_build + HM_build + pytest
    + (300+60)*(encode_seconds + ffmpeg_seconds + HM_decode_seconds)/60
    + 22*small_retarget_seconds/60 + margin
  = 10 + 2*20 + 15 + 5 + 360*(6 + 0.15 + 0.8)/60 + 22*0.5/60 + 20
  = 131.88 minutes (about 2.2 hours)
```

The extra 60 full-resolution frames are the native pytest sign fixture, now
restored to its ratified resolution. Inputs are planning assumptions, including
download speed and CPU throughput; `pytest` above covers its other overhead.
The command runner enforces a 145-minute overall deadline, a 75-minute build
limit, and a 75-minute F1 limit, each capped by the remaining overall time.
Commands emit heartbeats every 30 seconds. Slow upstreams or slower CPUs fail
the deadline rather than reducing the grid, changing criteria, or reporting PASS.

## ZCode pre-push review

- Ensure the reviewed kernel, builder, F1 module, tests, and provenance manifest
  are present on public **main**; the kernel clones main at launch. Compare its
  recorded SHA with the reviewed commit after launch.
- Confirm metadata owner/id, private visibility, CPU-only execution, internet
  enabled, no attached datasets, and the external `krun.py` calling convention.
- Review the exact pinned source commits, patch bytes/order, v1-equivalent flags,
  assembly ON configuration, and the new warped/partial-cell fixture oracle.
- Obtain a full local pytest result with an installed pytest runtime. Local
  native skips reflect the absence of the built Linux stack; the Kaggle J0 tier
  accepts no skips. Historical/J1 parity stays pending outside this tier.
- Run the package validator and manually inspect the upload bundle for secrets.
  The scanner covers token patterns, not every possible secret representation.
- Confirm CPU/time allocation for the estimate. After execution, require a
  schema-valid PASS receipt, complete per-CRF artifacts, both decoder hashes,
  matching artifact/log hashes, and no missing checks before accepting F1.
  A J0 receipt does not authorize training or later launch gates by itself.

Local validation evidence is recorded in `runs/j0-package-local-checks.json`.
No Kaggle push or source/dependency download was performed during implementation.

## Failed native run: diagnosis and recovery (2026-11-04)

Read `runs/j0_out/j0_gate0.log` directly; no dependency on the downloading receipt.
The run at commit `b69e45b0c55a64d27fd8b4af2a6f6fe4b26976a2` built successfully,
then reported 58 passed and three failed native tests. The tracebacks distinguish:

- `test_native_geometry_sei_decoder_match_and_baseline_absence`: the first M1
  encode was 64x48. x265's stderr says `Picture size must be at least one CTU`.
  All M1/M2/R fixture encodes now use 64x64. Encoder-open exceptions include
  dimensions and captured native fd-2 stderr, which is also replayed to the log.
- `test_sign_controls_identity_and_two_decoders`: the actual traceback is the
  minus6 frame-3 median 6.5 outside [5,6] at 128x80/CRF20. It now uses the
  recovered 1920x1080, ten-frame independent PCG64 noise, CRF20, medium preset,
  GOP1/B0, FPS30 settings. Frame 0 is first/uncompensated; frames 1-9 are
  compensated despite being I slices. The generator matches the read-only v1
  function byte for byte; ten-frame SHA-256 is
  `938e0f62f5477ce5581dd4630b3e2f4c5965413c6edfd7b0bb4f681d66e84a01`.
- `test_native_warped_qg_acceptance`: the read-only patch's `offsets()` uses
  `cols=(m_picWidth+15)/16`; `prismTelemetryCUs()` records the requested mean
  over the **reported QG parent**, not the CU leaf origin. QGs can be 16, 32,
  or 64 pixels; sub-QG leaves repeat their parent's value. The previous 112-wide
  fixture passed an eight-column CTU-padded map to a seven-column native grid.
  Its replacement uses width 128 so those strides agree, retains partial
  source/visible cells and the 80-high partial bottom CTU, and checks every
  reported QG footprint. That earlier version additionally required individual
  observations for all 22 perimeter QG16 cells; the QG64 acceptance hierarchy
  above supersedes that requirement.

Recovery sources and exact hashes are in
`evidence/manifests/j0_control_fixture.json`: `run_gate0_kaggle.py`,
`calibrate_bands.py`, `recalibrate_offline.py`, the complete v3 proposal settings,
`scripts/spike_gate0.py`, and `prism/codec/x265_bridge.py`. The supplied
`gate0/src/` is empty; the runner resolves to those script/package sources.
The proposal includes GOP1 and GOP10; this runner uses its GOP1 intra subset
as CONFIG B1 requires. Its historical pin declares assembly OFF, whereas the
current build must retain assembly ON. Fixture recovery is not a historical
binary replay or proof of native acceptance on this build.

Frozen criteria SHA-256 remains
`316134d2f2cf448f6d1e4292d7c9fee0e9fbd60c58e1cb4c196f624d9cad2cdc`:
minus6 compensated [5,6], plus6/checkerboard compensated [5,7], first-frame
[5.5,6.5], fidelity 1.0, aggregate floor 4.9. No criteria, codec patch, source
pin, build flag, or production geometry/QG contract changed. The sign fixtures
now match the recovered ratified stimulus domain; their native result remains
**[NEEDS VERIFY]** until the next pinned-stack run.

In that earlier version, out-of-domain sign fixtures and insufficient
individual edge evidence raised explicit `[NEEDS VERIFY]` skips in native
pytest. The implementation above removes those method-level skips. F1 remains
FAIL/incomplete on missing evidence. The kernel still rejects every
skip/xfail/missing test and keeps `training_authorized=false`. New conditions
such as band checks at CRF24/28/32/36 require owner-level ratified calibration
data; this fix does not extrapolate thresholds. Native coverage at other coded
widths whose padded/native strides differ is also pending separate evidence.

The only kernel entry-point change requires `net_effect_crfs == [20]` in the
F1 report. Build commands, patch hashes, timeouts, and fail-closed final receipt
logic are unchanged. No network operation or kernel rerun was performed.

Local regression run: **91 collected, 86 passed, 5 skipped, zero failures/errors**
with `python -m unittest discover -s tests -t . -v`. The five skips are the three
native cases (no pinned local stack) plus the two existing historical/J1 parity
placeholders. Seven new offline regression methods cover these fixes; the
existing frozen-band and kernel skip-rejection tests still pass. Logs and
machine-readable results are in `runs/j0-fixture-fixes-*`.

**[NEEDS VERIFY] pytest execution:** `python -m pytest tests/ -q` was attempted
using the local Codex Python 3.12.14 runtime and failed before collection with
`No module named pytest`. The available Hermes Python 3.11 runtime also lacks
pytest; no accessible offline wheel/install was found. The suite is green via
unittest, but a pytest-green result cannot be claimed without the missing local
dependency. No installation or download was attempted.

## Changed files

| Files | Purpose |
| --- | --- |
| `kaggle/job_specs/j0_gate0/{kernel-metadata.json,j0_gate0.py}` | Upload bundle, CPU bootstrap, schema validator, ordered patch verification, receipts and logs |
| `kaggle/package.py` | Offline metadata/script/secret validation and print-only wrapper command |
| `src/prism_v2/codec/f1.py`, `scripts/gate0.py` | Complete F1 runner and native retarget/adapter fixture |
| `scripts/build_codec.py` | Build progress and per-component timing; build flags preserved |
| `tests/kaggle/test_package.py`, `tests/kaggle/__init__.py` | Receipt, patch, secret-scan, packaging, and JUnit failure tests |
| `tests/codec/test_f1.py`, `tests/codec/test_native.py` | Partial-cell oracle, telemetry tripwires, fail-closed F1, native warped fixture |
| `tests/codec/test_contracts.py`, `tests/port_parity/{__init__.py,test_deferred.py}` | Preserve deferred historical/J1 placeholders outside the fresh J0 tier |
| `evidence/manifests/port_sources.json` | Updated destination hashes for the modified ported scripts |
| `runs/j0-package-{local-checks.json,pytest.log,unittest.log}` | Local verification results and hashed logs; distinct from a Kaggle acceptance receipt |
| `kaggle/J0_GATE0.md` | Scope, runtime formula, and auditor handoff |
