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
| M08 — Qualification and recommendation layer | `2a52897`, `ec0cb73`, `3f9171f` | ACTIVE; qualification surfaces are committed, but full recommendation logic remains unfinished |

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

Current M08 investigation is focused on reusing existing model metadata,
catalog discovery, fit, execution-fit, and qualification foundations before
adding recommendation ranking logic.

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
