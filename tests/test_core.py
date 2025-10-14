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
    with pytest.raises(ImageBuildError, match="not built"):
        SimulatedDockerClient().start(ContainerSpec(name="x", image="never/built"))


def test_simulated_build_failure_is_one_shot():
    client = SimulatedDockerClient()
    client.fail_next_build = True
    with pytest.raises(ImageBuildError):
        client.build(Path("."), "ai/flaky")
    retried = client.build(Path("."), "ai/flaky")
    assert retried.succeeded


def test_stop_unknown_container_rejected():
    with pytest.raises(Exception):
        SimulatedDockerClient().stop("phantom")


def test_run_args_ordering():
    spec = ContainerSpec(
        name="svc", image="img:tag",
        ports=((9000, 80),), env={"B": "2", "A": "1"},
        volumes=(("/data", "/data"),), command=("run", "--now"),
    )
    joined = " ".join(spec.run_args)
    assert "-p 9000:80" in joined
    for key in ("A=1", "B=2"):
        assert f"{key}" in joined
    assert "/data:/data" in joined
    assert spec.run_args[-2:] == ["run", "--now"]


def test_local_client_unavailable_raises_clean():
    client = LocalDockerClient(binary="definitely-not-a-binary-xyz")
    with pytest.raises(DockerUnavailableError):
        client.is_available()


def test_ports_env_volumes_all_present_in_args():
    spec = ContainerSpec(
        name="full", image="img",
        ports=((8080, 80),), env={"KEY": "VAL"}, volumes=(("/h", "/c"),),
    )
    joined = " ".join(spec.run_args)
    assert "-p 8080:80" in joined
    assert "KEY=VAL" in joined
