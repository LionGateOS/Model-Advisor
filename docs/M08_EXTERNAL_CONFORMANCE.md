# M08 External Conformance — Reference Classification

Status: **PARTIAL / RESEARCH**

Source: FitLLM `fit-vectors-v1.json`, 49 reference vectors.
License: MIT; attribution to the FitLLM contributors.

This document is an inventory, not a claim that all vectors pass.
The existing regression suite verifies three selected KV cases.
Other cases require architecture and expected-result mapping before
they can be treated as Model Advisor conformance tests.

## Reference inventory

| Vector | Kind | Status |
|---|---|---|
| `gemma31b-kv-full-bf16` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `gemma31b-kv-131k-q8` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `gemma12b-kv-full-bf16` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `qwen27b-kv-131k-q8` | `kv_total_bytes` | VERIFIED — existing KV regression |
| `glm47-mla-per-token` | `kv_per_token_bytes` | UNASSESSED — requires individual mapping |
| `glm52-mla-per-token` | `kv_per_token_bytes` | UNASSESSED — requires individual mapping |
| `gptoss20b-marginal-past-window` | `kv_per_token_bytes` | UNASSESSED — requires individual mapping |
| `agentworld-kv-10k` | `kv_total_bytes` | VERIFIED — existing KV regression |
| `v-gemma31b-64gb-8bit-8k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-gemma31b-64gb-bf16-full` | `verdict` | UNASSESSED — requires individual mapping |
| `v-glm52-mac512-4bit` | `verdict` | UNASSESSED — requires individual mapping |
| `v-glm52-mac512-8bit` | `verdict` | UNASSESSED — requires individual mapping |
| `v-gptoss120b-rtxpro6000-q4-32k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-llama31-3060-8gb-q4-8k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-e2b-ple-fp16-3060-8gb-headless` | `verdict` | UNASSESSED — requires individual mapping |
| `hy3-kv-full-f16` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `qwen38-27b-kv-full-f16` | `kv_total_bytes` | VERIFIED — existing KV regression |
| `qwen38-27b-linear-state` | `linear_state_bytes` | UNASSESSED — requires individual mapping |
| `qwen38-2.4t-kv-full-f16` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `qwen38-2.4t-linear-state` | `linear_state_bytes` | UNASSESSED — requires individual mapping |
| `qwen36-27b-linear-state` | `linear_state_bytes` | UNASSESSED — requires individual mapping |
| `hy3-linear-state-zero` | `linear_state_bytes` | UNASSESSED — requires individual mapping |
| `laguna-xs-kv-full-f16` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `laguna-s-kv-full-f16` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `v-qwen38-27b-5090-q4-32k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-qwen38-27b-5060ti16-q4-32k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-laguna-xs-mac64-q4-131k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-qwen38-2.4t-mac512-q4-8k` | `verdict` | UNASSESSED — requires individual mapping |
| `spark-x25-4b-kv-1m-f16` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `granite42-30b-kv-128k-f16` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `minicpm5-2b-kv-128k-f16` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `nex-n25-mini-kv-128k-f16` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `nex-n25-pro-kv-128k-f16` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `v-gptoss120b-dgxspark128-q4-8k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-gptoss120b-dgxspark128-q6k-32k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-lagunas-dgxspark128-q6k-256k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-gptoss120b-2xdgxspark128-q8-8k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-nexpro-4xdgxspark128-q8-128k` | `verdict` | UNASSESSED — requires individual mapping |
| `dsv41-flash-1017-kv-per-token-f16` | `kv_per_token_bytes` | UNASSESSED — requires individual mapping |
| `dsv41-flash-1017-kv-1m-f16` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `dsv4-flash-kv-1m-q8` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `dsv4-pro-kv-per-token-f16` | `kv_per_token_bytes` | UNASSESSED — requires individual mapping |
| `muse-spark-open-kv-1m-f16` | `kv_total_bytes` | UNASSESSED — requires individual mapping |
| `v-dsv41-1017-4xdgxspark128-q4km-8k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-dsv4flash-4xdgxspark128-q8-224k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-dsv41-1017-m3ultra512-4bit-8k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-gptoss120b-dgxspark128-q8-8k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-lagunas-dgxspark128-q6k-128k` | `verdict` | UNASSESSED — requires individual mapping |
| `v-dsv4flash-2xdgxspark128-q8-144k` | `verdict` | UNASSESSED — requires individual mapping |

## Evidence and limitations

- Three hybrid KV arithmetic cases passed Model Advisor's calculator.
- The full test suite passed 123 tests at commit `0773e5d`.
- The remaining vectors are not claimed to pass or fail.
- Hardware-fit verdicts must not be equated with KV arithmetic.
- MLA, sliding-window, linear-state and hardware-verdict cases need
  architecture-specific inspection before any support claim.
- Do not change production formulas merely to match a competitor.
- Do not copy restricted-license competitor code.

## Next action

Independently map supported reference cases to the existing model
schema, add narrowly justified tests, and document unsupported
cases with explicit reasons.
