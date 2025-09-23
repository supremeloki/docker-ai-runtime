import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from docker_runtime import (
    ContainerSpec,
    DockerUnavailableError,
    ImageBuildError,
    LocalDockerClient,
    SimulatedDockerClient,
    render_compose,
    render_dockerfile,
    write_deployment_bundle,
)


def test_render_dockerfile_includes_requirements():
    dockerfile = render_dockerfile(requirements_file="requirements.txt", app_module="server")
    lines = dockerfile.splitlines()
    assert any("FROM python:3.11-slim" in line for line in lines)
    assert any("pip install" in line and "requirements.txt" in line for line in lines)
    assert any('"python"' in line and '"-m"' in line for line in lines)


def test_render_compose_groups_services():
    services = [
        ContainerSpec(name="api", image="ai/api:1.0",
                      ports=((8000, 8000),),
                      env={"MODEL": "mini"},
                      command=("serve",)),
        ContainerSpec(name="redis", image="redis:7"),
    ]
    compose = render_compose(services)
    assert set(compose["services"]) == {"api", "redis"}
    api = compose["services"]["api"]
    assert api["environment"] == {"MODEL": "mini"}
    assert api["ports"] == ["8000:8000"]
    assert api["command"] == ["serve"]


def test_bundle_writer_creates_files(tmp_path):
    target = tmp_path / "bundle"
    written = write_deployment_bundle(
        target,
        render_dockerfile(),
        [ContainerSpec(name="worker", image="ai/worker:2")],
    )
    assert written.exists()
    assert (target / "docker-compose.json").exists()


def test_simulated_build_then_start():
    client = SimulatedDockerClient()
    build = client.build(Path("."), "ai/api:1.0")
    assert build.succeeded
    spec = ContainerSpec(name="api", image="ai/api:1.0")
    container_id = client.start(spec)
    assert container_id == "api"
    assert client.running_containers()[0]["name"] == "api"


def test_start_without_build_rejected():
