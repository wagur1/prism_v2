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
no SEI. Sign checks retain the frozen criteria and coverage rules unchanged.

The retarget fixture maps a 130x98 source through a nonuniform quantized map to
a 97x65 visible rectangle in a 112x80 coded frame. It compares warped offsets
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
    + 300*(encode_seconds + ffmpeg_seconds + HM_decode_seconds)/60
    + 20*small_retarget_seconds/60 + margin
  = 10 + 2*20 + 15 + 5 + 300*(6 + 0.15 + 0.8)/60 + 20*0.5/60 + 20
  = 124.92 minutes (about 2.1 hours)
```

Inputs are planning assumptions, including download speed and CPU throughput.
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
