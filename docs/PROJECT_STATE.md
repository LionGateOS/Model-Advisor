# Project State

Last reconciled: 2026-10-22.

This file is the index for current project status and the next safe action.
Verify the live repository before relying on any recorded checkpoint.

## Project identity

- Project: LionGateOS Model Advisor
- Public repository: `LionGateOS/Model-Advisor`
- Purpose: **Know what AI your machine should run.**
- Active milestone: M08 — recommendation layer.
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
- Last recorded M08 implementation checkpoint: `abc31d0` —
  `Harden M08 compatibility and add durable continuity`.
- Later continuity-only commits may exist beyond that checkpoint. Always verify
  the live HEAD with Git instead of treating an embedded documentation commit
  ID as permanently current.
- `origin/m08-recommendation-layer` was still at `3f9171f` at the latest
  verified pre-push check.
- The reviewed eight-file M08 hardening and continuity change set was committed
  as `abc31d0`.
- Immediately after the commit, `git status --short` was clean.
- The dashboard implementation file had no outstanding change.
- No push had been performed at that checkpoint.

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

- Full recommendation logic remains unfinished.
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
- Full recommendation logic and benchmark execution/comparison remain
  unfinished.

Do not infer a completed recommendation engine from the branch name or from
the existence of qualification capability surfaces.

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
- Full recommendation ranking and benchmark execution remain unfinished.
- No GPU or model execution was required.
- Next: map additional reference vectors without weakening conservative
  unknown/unsupported behavior.

## 2026-10-25 — M08 dashboard context comparison checkpoint

- Status: **IMPLEMENTED / AUTOMATED TESTS VERIFIED**; browser visual review pending.
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
  passed all 131 tests; browser visual verification remains pending.
