# LionGateOS Model Advisor

> **Know what AI your machine should run.**

LionGateOS Model Advisor is an open-source project for helping people determine which AI models are actually worth running on their hardware, for the work they want to do.

The goal is to reduce wasted time downloading, configuring, and testing models that are a poor fit for a machine or workload.

## Project Status

This repository is at the beginning of public development.

The public project has been established, but the Model Advisor implementation is not yet published.

Planned areas include:

- hardware discovery and manual hardware entry;
- local AI runtime discovery;
- model and runtime compatibility information;
- VRAM, RAM, storage, and offload estimates;
- quantization recommendations;
- task-specific model recommendations;
- reproducible model benchmarks;
- benchmark comparison and history;
- clear explanations for non-expert users;
- themes and accessibility improvements.

The project does **not** currently provide automatic model installation, automatic model downloading, autonomous execution, or unattended AI orchestration.

## Contributing

Community contributions are welcome.

Useful contribution areas will include:

- NVIDIA, AMD, Intel, Apple Silicon, and CPU hardware support;
- Ollama, llama.cpp, vLLM, and other runtime adapters;
- model metadata and compatibility data;
- quantization guidance;
- benchmark definitions and validators;
- recommendation heuristics;
- UI and accessibility;
- themes and translations;
- documentation.

See [CONTRIBUTING.md](CONTRIBUTING.md) before starting a substantial change.

## Relationship to WorkRunner

Model Advisor is a separate public LionGateOS project.

It focuses on understanding hardware, models, compatibility, recommendations, and benchmarking.

LionGateOS WorkRunner remains the private execution and orchestration system responsible for controlled AI work, approvals, policy, recovery, and execution authority.

## License

Licensed under the [Apache License 2.0](LICENSE).
