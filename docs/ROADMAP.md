# Roadmap

Last reconciled: 2026-10-22.

Status labels:
- **VERIFIED** — supported by recorded test or execution evidence.
- **IMPLEMENTED** — present in the project; verification may be incomplete.
- **PLANNED** — intended but not implemented.
- **DEFERRED** — postponed; do not treat as active implementation.
- **HISTORICAL** — an earlier milestone or decision, not current status.

## Milestone history

The commit references below were observed in repository history. Their
presence proves that the corresponding changes were committed; it does not
by itself prove every real-hardware scenario is covered.

| Milestone | Recorded implementation | Status and limits |
|---|---|---|
| M01 — Hardware profile | `a6d5451` — Add M01 hardware profile | IMPLEMENTED; hardware discovery is Linux-focused |
| M02 — Runtime discovery | `6be0131` — Add M02 runtime discovery | IMPLEMENTED; supported runtime coverage remains limited |
| M03 — Runtime compatibility | `309649c` — Add M03 runtime compatibility | IMPLEMENTED; unknown is retained when evidence is insufficient |
| M04 — Dashboard | `54c2296` — Add M04 local evidence dashboard | IMPLEMENTED; local read-only dashboard |
| M05 — Model metadata | `ea8ef8f` — Add provenance-first model metadata foundation | IMPLEMENTED; metadata normalization is not the same as fetching artifacts |
| M06 — Memory estimation | `d8dd8df` — Add M06 model memory estimation foundation | IMPLEMENTED foundation; do not infer universal fit accuracy |
| M07 — Ecosystem discovery and conservative fit foundations | `2efb00f` — Add ecosystem model discovery and conservative fit foundations | IMPLEMENTED foundation; broader recommendation behavior remains unfinished |
| M08 — Qualification and recommendation layer | `29d1cb6` — Add conservative recommendation CLI | COMPLETE; conservative qualification and workload recommendation surfaces are implemented and verified; broader ranking, benchmarking, quantization guidance, and workload coverage remain future work |

## Current M08 work

The earlier M08 hardening and durable-continuity work was reviewed, verified,
committed, and pushed. The implementation checkpoint is `abc31d0` —
`Harden M08 compatibility and add durable continuity`.

Verified hardening included:

- CLI passive compatibility mode and graceful broken-pipe handling;
- deduplicated qualification evidence sources;
- CLI regression tests for passive and default capability probing;
- dashboard regression protection ensuring `runtime_paths` is not returned.

The last full code/test verification before documentation-only continuity
commits passed all 121 tests in 2.532 seconds.

M08 is complete at its bounded conservative scope. Existing model metadata,
catalog discovery, fit, execution-fit, and qualification foundations now feed
read-only workload recommendations without inventing performance rankings.

Hugging Face catalog discovery already supports bounded public search,
bounded detail enrichment, task/parameter filtering, deduplication, explicit
partial/unavailable states, and conservative GGUF metadata handling. Repo-level
GGUF totals are not promoted to exact model parameter counts or concrete
artifact sizes without stronger evidence.

A separate owner-requested candidate-model evaluation is recorded in
`PROJECT_STATE.md`; its model identity and video claims remain unverified.

## Implemented foundations

The README and source history support these implemented foundations:

- Hardware profile discovery and manual hardware entry.
- Read-only discovery for supported local runtimes.
- Conservative compatibility assessment based on explicit evidence.
- Provenance-aware model metadata and local Ollama inventory discovery.
- Local dashboard and normalized JSON output.
- Memory/fit foundations and qualification capability surfaces.

Implementation status is not a guarantee that every GPU, runtime, model, or
workload has been independently tested.

## Planned or incomplete

- Broader NVIDIA, AMD, Intel, Apple Silicon and CPU support.
- Broader runtime discovery and runtime metadata.
- More complete model/runtime compatibility information.
- VRAM, RAM, storage and offload estimates.
- Quantization guidance and task-specific recommendations.
- Reproducible benchmarks, comparison and benchmark history.
- Clearer explanations, themes, accessibility and translations.
- Arbitrary GGUF filesystem scanning is not currently part of Model Advisor.

Do not mark a planned capability implemented until source changes and suitable
verification evidence exist. Do not create a competing scanner or cache
without an explicit product decision.

## Next safe action

Inspect the remaining model-discovery and normalization paths against current
official Ollama and Hugging Face metadata. Identify the smallest missing
evidence fields needed for conservative recommendation logic before changing
the recommendation schema or adding ranking heuristics.

## 2026-10-25 — M08 external evidence checkpoint

**VERIFIED:** Three FitLLM-derived hybrid KV reference calculations
match Model Advisor's existing calculator; 123 tests passed.

**PARTIAL:** Remaining 46 external reference vectors have not yet been
mapped to Model Advisor's supported architectures and contracts.

**PLANNED:** Evidence-bounded quantization/context guidance, followed
by measured benchmarking when separately approved.

**LIMITATION:** This checkpoint does not establish a complete
recommendation engine or universal model/hardware compatibility.

## M08 context comparison — implementation checkpoint

**IMPLEMENTED / PARTIALLY VERIFIED:** The read-only dashboard compares local
Ollama artifacts at 4096, 8192, 16384 and 32768 tokens, preserves unknown
memory evidence, separates context-limit status from memory fit, and shows
independent GPU assessments. The complete 131-test Python suite and JavaScript syntax checks pass
outside the restricted sandbox; browser visual review was subsequently completed
successfully. Full quantization guidance and numerical performance ranking remain
PLANNED future work.

## M08 Conservative Recommendation V1 — 2026-10-25

- IMPLEMENTED: A pure, read-only local-artifact recommendation classifier.
- Workloads initially supported: coding, general chat, and reasoning.
- Reuses existing ModelIdentity, ModelArtifact, and ModelQualification contracts.
- Explicit reported task/capability evidence is required for workload matching.
- Unknown hardware suitability is never promoted to qualified.
- Remote artifacts and mismatched identities are rejected.
- No performance scoring, downloads, model execution, or WorkRunner authority.
- Dashboard integration and a dedicated conservative recommendation CLI surface are implemented.
- LIMITATION: Workload taxonomy is intentionally narrow and requires future review.

## M08 dashboard workload recommendations — 2026-10-25

- IMPLEMENTED: Existing local-model dashboard cards now show coding,
  general-chat and reasoning recommendation classifications.
- Reuses Conservative Recommendation V1 and existing suitability evidence.
- Preserves the complete-memory safeguard: unknown total memory cannot
  produce a confirmed positive hardware qualification.
- Remote-backed artifacts are excluded from local recommendations.
- Missing reported workload metadata remains unknown.
- No numerical performance ranking or benchmark claims are introduced.
- No model execution, downloads, installation or WorkRunner authority.
- Verification: full Python suite, JavaScript syntax and regression tests
  must pass before this checkpoint is committed.
- VERIFIED: Browser visual inspection completed successfully on 2026-10-25.


## M08 recommendation evidence-quality correction — 2026-10-25

Recommendation evidence matching now requires reported provenance for the
specific metadata field that produced the workload match. Generic Ollama
capabilities are not promoted into unsupported workload claims. Hardware
qualification safeguards remain unchanged. The complete 167-test Python
suite, JavaScript syntax check, and Git whitespace check pass.

Explicit workload metadata for local Ollama models remains incomplete;
broader ranking, benchmarking, and quantization guidance remain future work.

## M08 local Ollama registry identity — 2026-10-25

Optional registry-relative identity is now derived from a unique local Ollama
manifest whose model-layer blob exists and matches the declared size. Invalid,
missing, and ambiguous matches remain unknown. This does not infer workload
specialization and does not change recommendation or hardware qualification.
Verification, live registry identity review, backup, commit and push completed.

## M08 recommendation CLI — 2026-10-25

- IMPLEMENTED: `recommend` exposes the existing conservative local-artifact
  recommendation pipeline as JSON.
- `--workload` supports coding, general_chat and reasoning.
- The CLI reuses the dashboard's existing qualification and recommendation
  pipeline rather than introducing competing recommendation policy.
- Output explicitly states that recommendations are conservative and that
  performance ranking is not provided.
- Remote-backed artifacts remain excluded by the existing pipeline.
- Numerical performance ranking, benchmark claims and model execution are not
  introduced.
- VERIFIED: live CLI, privacy, full 181-test suite, JavaScript syntax, backup, commit and push completed before M08 closeout.

## M08 closeout — 2026-10-25

**COMPLETE / VERIFIED:** M08 is closed at its intentionally conservative scope.

Verified delivered behavior includes qualification, local Ollama suitability
presentation, context comparison, evidence-bounded workload recommendations for
coding/general chat/reasoning, dashboard presentation, a structured recommendation
CLI, and local Ollama registry identity provenance.

Final M08 verification reached **181 passing Python tests**. The recommendation
CLI was also exercised against the live local Ollama inventory, privacy checks
passed, JavaScript syntax and Git whitespace checks passed, and the final CLI
checkpoint was backed up before commit.

M08 does **not** claim numerical performance ranking, benchmark-derived model
ranking, comprehensive quantization guidance, universal hardware/runtime support,
or comprehensive workload metadata. Those are later product/research milestones
and do not block this bounded M08 closeout.

The public/private boundary is unchanged: Model Advisor provides public advisory
evidence and recommendations only. It has no WorkRunner execution, routing,
approval, installation, dispatch, or policy authority.

## M09A model-origin evidence validator V1 — 2026-10-26

- IMPLEMENTED / VERIFIED (automated): read-only, fail-closed local
  origin-evidence validation for one specific local Ollama artifact under the
  single documented trust root `local-ollama-manifest-digest-record`.
- The only cryptographic check recomputes the SHA-256 of the small local
  Ollama manifest file and chains its single model-layer digest to the
  recorded evidence. Model weight blobs are never read.
- `upstream_origin_verified` is always `False` in V1; upstream-origin strings
  are recorded as claims only. Names, URLs, sizes, architectures and
  quantizations are never accepted as proof of origin.
- Reuses the existing manifest-identity parsing helpers; no competing
  manifest scanner or recommendation policy was introduced.
- Verification: full suite reached **216 tests, OK**, including **35** new
  simulated-fixture M09A tests, all passing; zero assertion failures.
- LIMITATION: no upstream-origin verification, no model-blob verification,
  no CLI or dashboard integration, and the trust root remains a declared
  local assumption rather than proof of what the registry received.
- Uncommitted at this checkpoint; commit awaits explicit owner approval.
