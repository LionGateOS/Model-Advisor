# Project State

Last reconciled: 2026-10-22.

This file is the index for current project status and the next safe action.
Verify the live repository before relying on any recorded checkpoint.

## Project identity

- Project: LionGateOS Model Advisor
- Public repository: `LionGateOS/Model-Advisor`
- Purpose: **Know what AI your machine should run.**
- M08 — qualification and recommendation layer: **COMPLETE / VERIFIED** at its bounded conservative scope.
- Public/private boundary: Model Advisor is a standalone public project.
- Machine-specific checkout paths are intentionally excluded from these
  public records.

Owner-specific workflow and local continuation details are intentionally kept outside the public repository at `~/.local/share/liongateos/model-advisor/OWNER_CONTINUITY.md`.

## Authoritative record index

| Record | Owns |
|---|---|
| `docs/PROJECT_STATE.md` | Current status, verification, constraints, next action |
| `docs/ROADMAP.md` | Milestone status, planned work, known limitations |
| `docs/ACCOMPLISHMENTS.md` | Dated milestone history and evidence |
| `README.md` | Public introduction, current capabilities and limitations |
| `tests/` | Executable regression and behavior tests |

The live repository and test results take precedence over stale documentation.
Update these records at meaningful checkpoints. Preserve historical entries
when current status changes.

## Last verified repository checkpoint

- Branch: `m08-recommendation-layer`
- Verified M08 implementation checkpoint: `29d1cb6` —
  `Add conservative recommendation CLI`.
- Local HEAD and `origin/m08-recommendation-layer` were verified identical at
  `29d1cb6005164d26895389430b9039f39677b718`.
- Working tree was clean after the verified push.
- Final implementation verification: **181 Python tests passed**, JavaScript
  syntax passed, live recommendation CLI passed, privacy check passed, and the
  backup checksum/readability check passed.

Recheck `git status` and `git log` before using this as a current checkpoint.
The subsequent continuation reread all durable records, verified the live branch and HEAD, and completed a no-pager review of the code/test patch.

## Latest test evidence

Initial verification on 2026-10-22, before creating these continuity records:

- `PYTHONPATH=src python3 -m unittest discover -s tests -q`
  — **121 tests passed**.
- `git diff --check` — passed.

Post-documentation verification on 2026-10-22:

- Full suite rerun after the three records and README links were added — **121
tests passed in 2.533 seconds**.
- `git diff --check` — passed.
- The working tree contained the existing code/test changes, README links, and
  three new continuity records. Nothing was staged, committed or pushed.

Final pre-commit verification on 2026-10-22:

- **121 tests passed in 2.532 seconds**.
- `git diff --cached --check` — passed.
- Exactly eight reviewed files were staged.
- Commit `abc31d0` — `Harden M08 compatibility and add durable continuity` —
  was created successfully.
- Immediately afterward, the working tree was clean.
- No push had been performed.

## Current implementation work

The M08 hardening changes committed in `abc31d0` cover:

- `cli.py`: a `--passive` option for compatibility assessment, plus graceful
  handling of `BrokenPipeError` when printing JSON.
- `qualification.py`: deduplication of runtime evidence-source entries.
- `tests/test_cli.py`: regression coverage for passive mode and default
  capability probing.
- `tests/test_dashboard.py`: an assertion that dashboard data does not expose
  the `runtime_paths` field.

The dashboard must continue using configured runtime paths internally for
discovery; those paths should not be returned as dashboard data.

Status: implemented, verified by the recorded test run, and committed in
`abc31d0`.

## Current important capabilities and artifacts

Important current capability surfaces include:

- hardware discovery and manual hardware entry;
- runtime discovery for Ollama, llama.cpp, and vLLM;
- conservative runtime compatibility assessment;
- provenance-aware model metadata and Ollama inventory discovery;
- memory/fit foundations;
- qualification capability surfaces;
- local read-only dashboard;
- CLI and JSON interfaces;
- regression tests under `tests/`.

Important current public records include:

- `docs/PROJECT_STATE.md`;
- `docs/ROADMAP.md`;
- `docs/ACCOMPLISHMENTS.md`;
- `README.md`.

Do not treat this as a complete artifact inventory. Verify paths and ownership
before relying on or changing an artifact.

## Pending decisions, failures and unresolved work

- Conservative workload recommendation logic is implemented and verified; numerical performance ranking and broader recommendation coverage remain future work.
- Benchmark execution/comparison remains unfinished.
- Arbitrary GGUF filesystem scanning is not part of Model Advisor.
- The owner-requested “NVIDIA Neatron Bolt 74B” evaluation remains
  PLANNED / UNVERIFIED.
- No current known regression is recorded at this checkpoint.
- External disaster-recovery backup remains unverified.

Record important new failures, regressions, owner decisions, rejected
approaches, and completed investigations here or in the appropriate durable
historical record instead of relying on chat memory.

## Stable capabilities and limitations

The public README is the current summary of product capabilities. Important
limitations include:

- Hardware discovery is Linux-focused.
- Runtime discovery covers Ollama, llama.cpp and vLLM.
- Compatibility assessment is conservative and can remain unknown without
  explicit positive capability evidence.
- Live local model inventory uses the Ollama API.
- Arbitrary GGUF filesystem scanning is not implemented in Model Advisor.
- Conservative workload recommendation logic is implemented and verified;
  benchmark execution/comparison and numerical performance ranking remain future work.

Do not infer universal model ranking or benchmark-backed performance guidance
from the completed conservative M08 recommendation surfaces.

## Pending owner-requested model evaluation

- Evaluate the video claim for a model named “NVIDIA Neatron Bolt 74B,”
  described as a roughly 2-bit quantization and a roughly 22 GB artifact.
- Status: **PLANNED / UNVERIFIED**. Confirm the model's canonical identity,
  artifact source, quantization format, size, memory/offload needs, and
  evidence for coding and agentic workloads before recommending a download.
- No download or model launch is authorized by that request. Recheck GPU
  availability before any later test; Harness, CASE, or vLLM work may
  change availability. Do not use protected hardware without explicit approval.
- This is a research/advisory task, not approval to expand Model Advisor's
  filesystem discovery or runtime scope.

## Cross-project boundary

Model Advisor owns its public hardware, runtime, compatibility, model metadata
and qualification interfaces. Keep those interfaces stable unless a specific
contract change is justified and approved.

Do not introduce a competing GGUF scanner or discovery cache merely to
duplicate a separate model-management workflow. Do not include private
implementation details from related projects in this public repository.

## Preservation and next action

At the latest verified post-push checkpoint, local HEAD and
`origin/m08-recommendation-layer` both resolved to `8b97be9`, and the working
tree was clean. Verify live Git state before relying on this checkpoint.
External disaster-recovery backup remains unverified.

Do not claim a backup or recovery state without verifying it.

Next action:

1. Record and commit this post-push continuity update.
2. Verify the resulting HEAD and working tree.
3. Continue M08 recommendation-layer development from the roadmap without
   rediscovering M01-M07.

## 2026-10-25 — M08 external conformance checkpoint

- Live verified branch: `m08-recommendation-layer`.
- Published checkpoint: `0773e5d`.
- Three external hybrid KV-cache reference cases pass.
- Full suite: **123 tests passed**.
- Working tree was clean at the start of the current job.
- FitLLM reference inventory: 49 vectors; three verified,
  46 not yet assessed for Model Advisor conformance.
- Numerical performance ranking and benchmark execution remain future work.
- No GPU or model execution was required.
- Next: map additional reference vectors without weakening conservative
  unknown/unsupported behavior.

## 2026-10-25 — M08 dashboard context comparison checkpoint

- Status: **IMPLEMENTED / VERIFIED**; automated tests and subsequent browser visual review passed.
- Added `context_comparisons` to the existing read-only dashboard payload for
  locally stored Ollama artifacts only.
- The dashboard compares 4096, 8192, 16384 and 32768 tokens using the existing
  memory calculator and independent GPU assessment functions.
- Remote-backed artifacts and hosted-only offerings are excluded.
- KV precision is never inferred from weight quantization or artifact size.
  Unknown KV cache, total memory and fit status remain unknown when evidence is
  incomplete. Context-limit compatibility remains separate from memory fit.
- Targeted non-socket regression run: **124 tests passed**. JavaScript syntax
  check passed.
- Required full run reached 131 tests: 125 passed and 6 existing HTTP tests
  errored because this sandbox denied loopback socket creation with
  `PermissionError: [Errno 1] Operation not permitted`. No assertion failure
  was reported. A subsequent full run in the owner's normal terminal
  passed all 131 tests; browser visual verification was subsequently completed successfully.

## M08 Ollama active-memory observation checkpoint — 2026-10-25

- Read-only `/api/ps` observation added for already-loaded local Ollama models.
- Reported loaded and GPU memory remain observations, not predicted requirements.
- Remote-backed registrations are excluded from dashboard memory observations.
- Missing observations do not establish a zero-memory requirement.
- Existing suitability and qualification rules remain unchanged.
- Malformed and unavailable API responses are handled conservatively.
- Live Ollama endpoint was reachable with zero loaded models.
- Active-model measurements remain unverified; no model was started.
- Numerical performance ranking remains future work outside the bounded M08 closeout.

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

- VERIFIED: Workload evidence must now come from the reported metadata field
  that actually contains the matching workload label.
- Generic Ollama capabilities such as `completion`, `thinking`, `tools`, and
  `embedding` are not treated as proof of coding, general-chat, or reasoning
  specialization.
- Hardware qualification safeguards are unchanged.
- Verification: 14 recommendation tests and the complete 167-test Python
  suite pass; JavaScript syntax and Git whitespace checks pass.
- LIMITATION: Current Ollama metadata does not provide the explicit workload
  labels required for positive workload classification, so unknown results
  remain expected unless suitable sourced task metadata is available.

## M08 local Ollama registry identity — 2026-10-25

- IMPLEMENTED: optional registry-relative identity on model artifacts.
- Identity is attached only when a unique local manifest matches the exact
  registration path and its model-layer blob exists with the declared size.
- Missing, malformed, invalid, or ambiguous matches remain unknown.
- Local filesystem paths are not exposed in the normalized identity.
- Remote-backed registrations do not receive local manifest identities.
- Registry identity is provenance only; recommendation and hardware
  qualification behavior is unchanged.
- VERIFIED: full suite, live local registry identity, privacy, backup, commit and push completed.

## M08 final closeout — 2026-10-25

- Status: **COMPLETE / VERIFIED** at the bounded conservative recommendation scope.
- Final implementation checkpoint: `29d1cb6` — `Add conservative recommendation CLI`.
- Local and remote feature-branch commits were verified identical after push.
- Final implementation suite: **181 tests passed**.
- Live `recommend --workload coding` execution succeeded against 11 local Ollama
  artifacts; all remained `workload_unknown` because sufficiently sourced coding
  metadata was absent. This is intended conservative behavior.
- Privacy, JavaScript syntax, Git whitespace, backup checksum and backup
  readability checks passed.
- Numerical performance ranking, benchmark execution/comparison, comprehensive
  quantization guidance, broader hardware/runtime coverage and richer workload
  metadata remain future work.
- Model Advisor remains advisory only and gains no WorkRunner execution authority.


## 2026-10-26 — M09A model-origin evidence reconciliation checkpoint

- IMPLEMENTED / VERIFIED (automated): M09A local model-origin evidence
  validator V1, read-only and fail-closed.
- Files: `src/liongateos_model_advisor/model_origin_evidence.py` and
  `tests/test_model_origin_evidence.py` (35 simulated-fixture tests).
- Verified by read-only code review: the only cryptographic check recomputes
  the SHA-256 of the small Ollama manifest file and chains the single
  model-layer digest; model blobs are never read or hashed;
  `upstream_origin_verified` is always `False`; upstream evidence strings
  are preserved as claims only; no network access, no writes; reason strings
  contain no paths, timestamps, or evidence values.
- Anchored evidence does not change recommendation behavior; the
  non-promotion regression test confirms `workload_unknown` status and
  evidence sources remain unchanged.
- The validator is not yet integrated into the CLI or dashboard; no
  competing recommendation policy was introduced.
- Verification in this session (disposable workspace temp dir under a
  workspace-write sandbox grant, removed afterward): full suite
  `discover` — **216 tests, OK**; targeted M09A module — **35 tests, OK**;
  zero assertion failures.
- The two M09A files and these record updates were uncommitted at this
  checkpoint; commit and push await explicit owner approval.
- Next: owner-approved commit of the four reviewed files; no push without
  further approval.
