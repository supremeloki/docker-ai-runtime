# docker-runtime

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A containerized AI runtime layer: declarative container specs, Dockerfile/compose generation, and a dual client — real Docker CLI when present, deterministic simulation everywhere else.

## 🚀 Overview

AI services ship in containers; the packaging code shouldn't be string soup. `docker-runtime` declares containers as frozen `ContainerSpec` dataclasses (ports/env/volumes/command) that render themselves into CLI args, generates clean `Dockerfile`s and compose manifests, and talks to Docker through one `LocalDockerClient`. The `SimulatedDockerClient` mirrors the same interface for CI and tests — build-before-start enforced, failures injectable one-shot — so deployment logic is testable without a daemon.

## ✨ Features

- **Declarative specs:** `ContainerSpec(name, image, ports, env, volumes, command)` → ordered `run_args`
- **Dockerfile generation:** slim base image, optional requirements install, module entrypoint
- **Compose manifest:** JSON compose grouped per service with sorted environment
- **Dual clients:** `LocalDockerClient` shells out to the real CLI; `SimulatedDockerClient` enforces the same contract offline
- **Build gating:** starting an unbuilt image rejected; simulated build failure is one-shot (retry succeeds)
- **Typed errors:** `ImageBuildError(image)` / `ContainerNotFoundError` / `DockerUnavailableError`
- **Zero dependencies**

## 🚧 Structure

```
docker-ai-runtime/
├── src/docker_runtime/
│   ├── __init__.py
│   └── core.py
├── tests/
│   └── test_core.py
├── README.md
└── pyproject.toml
```

## 📦 Installation

```bash
git clone https://github.com/supremeloki/docker-ai-runtime.git
cd docker-ai-runtime
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## 📋 Requirements

- Python 3.11+
- Optional: Docker CLI for live operation

## 🏃 Quick Start

```python
from pathlib import Path
from docker_runtime import (
    ContainerSpec, SimulatedDockerClient,
    render_dockerfile, write_deployment_bundle,
)

client = SimulatedDockerClient()
client.build(Path("."), "ai/inference:1.4")
client.start(ContainerSpec(
    name="inference",
    image="ai/inference:1.4",
    ports=((8000, 8000),),
    env={"MODEL": "mini-7b"},
))

write_deployment_bundle(Path("deploy"), render_dockerfile(requirements_file="requirements.txt"),
                        [ContainerSpec(name="inference", image="ai/inference:1.4")])
```

## 🔧 Error Handling

```text
DockerRuntimeError
├── ImageBuildError           # .image names the failed tag
├── ContainerNotFoundError    # stop/logs on unknown container
└── DockerUnavailableError    # docker binary missing
```

## 🧪 Testing

```bash
pytest tests/ -v
```

## 📝 Code Quality

- Full type hints (`X | None` style), frozen specs/results
- Zero comments — names carry the meaning
- Simulation contract tested: build gate, one-shot failure, container registry

## 📄 License

MIT — see [LICENSE](LICENSE).

## 👤 Author

**Kooroush Masoumi** - [kooroushmasoumi@gmail.com](mailto:kooroushmasoumi@gmail.com)

---

⭐ Star this repo if you find it useful!
