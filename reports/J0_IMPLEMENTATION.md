# Local implementation review

Scope is the codec/geometry job in the [binding configuration](../deliberation/CONFIG_V2.md). Training, packaging, monitoring, harvest, and launch entrypoints remain inert placeholders. No Kaggle operation, network request, token/pool access, or commit was performed. The reference repository was read through Git blobs without modification.

The local CPU suite exercises geometry, signaling, coordinates, the historical telemetry verifier, and evidence checks. Native acceptance and historical replay remain **[NEEDS VERIFY]**. A successful CPU suite does not satisfy the complete codec gate or authorize training. The required pytest run remains blocked because pytest is unavailable in the accessible offline runtime; the receipt records the successful unittest run separately. The later [adversarial self-review](J0_SELF_REVIEW.md) and its [check receipt](../runs/j0-self-review.json) record the current corrections and validation; the original receipt below is historical.

- [Local check receipt](../runs/j0-local-checks.json)
- [Source hashes and adaptations](../evidence/manifests/port_sources.json)
- [Synthetic fixture provenance](../evidence/manifests/synthetic_fixtures.json)
- [Source and patch pin](../third_party/x265/PINNED_SOURCE.json)
- [Typed ledger](../evidence/ledger.jsonl)

The recovered historical criteria identifier is `316134d2`; the complete source-blob SHA is `316134d2f2cf448f6d1e4292d7c9fee0e9fbd60c58e1cb4c196f624d9cad2cdc`. The exact original `UTF-8` text is stored inside a provenance-commented fixture envelope, so its source hash can be reproduced separately from the envelope's file hash. Runtime criteria preserve its bands and fidelity thresholds. Every condition uses the area-weighted QG net-effect verifier; raw base drift is never a fallback. The original runner's expected criteria keys differ from the actual frozen artifact; that mismatch was adapted explicitly.

The build scripts accept clean, pinned **local** x265 and HM repositories and require installed compiler tools. They archive inputs into a fresh output directory, apply the original patch hunks in order, require assembly, and retain the inherited compiler settings. Build receipts record archive, patch, shim, compiler, decoder, and encoder identities. Old decoder/encoder binaries and their historical success flags are not accepted as a new build. The patches instrument the existing quantOffsets path; they do not create a second control mechanism.

Review these decisions closely:

- Geometry uses pixel-edge coordinates, area-weighted bounded saliency marginals, and full-frame QG boundary knots, including partial edge cells. Destination knots use unsigned fixed-point `Q16.16`, nearest rounding with positive half ties upward. Collapsed intervals are rejected rather than repaired. This wire precision is an implementation choice for reviewer approval; maximum dimensions follow the representable wire domain.
- The SEI payload has a fixed UUID and version, explicit original/coded/visible/crop rectangles, and quantized destination knots. Source knots are implicit from QG boundaries over the source/crop extent. The encoder accepts a quantized map; the evaluator reconstructs it exclusively from the AU. Spatial AU byte counts include the inserted NAL and all existing headers. Stock/M2 suppress x265 info SEI and reject SEI-bearing output. These adaptations follow the signed signaling contract. [claim:signed-contract]
- The NumPy CTU expansion reproduces the v1 half-pixel-center bilinear rule with edge replication. The warped adapter accepts the complete inherited buffer and preserves it under identity geometry. For other maps, it treats visible source QG values as piecewise constant and extends the boundary field before integrating complete destination cells, including padding. Its visible rectangle is top-left aligned; the more general SEI/box contract also supports nonzero visible origins. Image resampling/antialiasing is not yet selected and no image efficacy evaluation is enabled.
- Box inversion removes detector resize/letterbox and the visible origin before inversion. Crop offsets are restored in original coordinates. Padding-only boxes collapse to zero area; callers must discard such detections as appropriate. Original ground truth and its area groups are untouched. Baseline resize/crop maps are explicit payload kinds.
- Ledger records distinguish measured results, literature, constants, estimates, and rejected history. Artifact validation is offline and checks locally resolvable full hashes. The Markdown scanner is a tripwire; citation presence does not establish support. Historical claims are not promoted. The ledger currently records only the binding design authority.

Native tests are enabled with `PRISM_CODEC_STACK` pointing to the locally produced `stack.json`. The runner reproduces the inherited seeded noise and signed control patterns, using the signed CRF intra configuration. Both decoder outputs must match byte-for-byte in the declared sample format. Its `CODEC_CONTROLS_PASS` verdict deliberately leaves `gate0_complete` false: SEI native acceptance, warped-QG acceptance, complete historical replay, and auditor review remain separately visible obligations.

Use an installed pytest runtime for the required final command:

```text
python -m pytest -q
python scripts/check_claims.py
python scripts/build_codec.py --x265-source LOCAL_X265 --hm-source LOCAL_HM --output NEW_BUILD_DIRECTORY
python scripts/gate0.py --stack NEW_BUILD_DIRECTORY/stack.json --output NEW_GATE_DIRECTORY
```

The build and gate commands above were not launched. Missing native tools and unrecovered frozen fixtures have explicit skip reasons containing **[NEEDS VERIFY]**, with no fabricated native PASS.
