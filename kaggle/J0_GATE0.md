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
    + 20*small_retarget_seconds/60 + margin
  = 10 + 2*20 + 15 + 5 + 360*(6 + 0.15 + 0.8)/60 + 20*0.5/60 + 20
  = 131.87 minutes (about 2.2 hours)
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
  reported QG footprint. Each of the 22 perimeter QGs additionally needs an
  individual 16x16 observation; coarse means cannot stand in for edge evidence.

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

Out-of-domain sign fixtures and insufficient individual edge evidence raise
explicit `[NEEDS VERIFY]` skips in native pytest. F1 stays FAIL/incomplete and
retains SKIP details for unfinished checks. The kernel still rejects every
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
