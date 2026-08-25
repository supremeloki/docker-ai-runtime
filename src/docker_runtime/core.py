from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


class DockerRuntimeError(Exception):
    pass


class ImageBuildError(DockerRuntimeError):
    def __init__(self, image: str, detail: str) -> None:
        super().__init__(f"build failed for {image!r}: {detail}")
        self.image = image


class ContainerNotFoundError(DockerRuntimeError):
    def __init__(self, name: str) -> None:
        super().__init__(f"container not found: {name!r}")


class DockerUnavailableError(DockerRuntimeError):
    pass


@dataclass(frozen=True)
class ContainerSpec:
    name: str
    image: str
    ports: tuple[tuple[int, int], ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    volumes: tuple[tuple[str, str], ...] = ()
    command: tuple[str, ...] = ()

    @property
    def run_args(self) -> list[str]:
        args = ["run", "-d", "--name", self.name]
        for host_port, container_port in self.ports:
            args += ["-p", f"{host_port}:{container_port}"]
        for key, value in sorted(self.env.items()):
            args += ["-e", f"{key}={value}"]
        for host_path, container_path in self.volumes:
            args += ["-v", f"{host_path}:{container_path}"]
        args.append(self.image)
        if self.command:
            args += list(self.command)
        return args


@dataclass(frozen=True)
class BuildResult:
    image_tag: str
    layers_cached: bool
    duration_seconds: float

    @property
    def succeeded(self) -> bool:
        return True


DEFAULT_BASE_IMAGE = "python:3.11-slim"


def render_dockerfile(base_image: str = DEFAULT_BASE_IMAGE,
                      requirements_file: str | None = None,
                      app_module: str = "main") -> str:
    lines = [f"FROM {base_image}", "WORKDIR /app"]
    if requirements_file:
        lines += [f"COPY {requirements_file} .", "RUN pip install --no-cache-dir -r " + requirements_file]
    lines += [
        "COPY . .",
        f"CMD [\"python\", \"-m\", \"{app_module}\"]",
    ]
    return "\n".join(lines) + "\n"


def render_compose(services: Sequence[ContainerSpec]) -> dict[str, Any]:
    compose: dict[str, Any] = {"services": {}}
    for spec in services:
        entry: dict[str, Any] = {"image": spec.image}
        if spec.ports:
            entry["ports"] = [f"{h}:{c}" for h, c in spec.ports]
        if spec.env:
            entry["environment"] = {k: v for k, v in sorted(spec.env.items())}
        if spec.volumes:
            entry["volumes"] = [f"{h}:{c}" for h, c in spec.volumes]
        if spec.command:
            entry["command"] = list(spec.command)
        compose["services"][spec.name] = entry
    return compose


def write_deployment_bundle(directory: Path, dockerfile: str,
                            services: Sequence[ContainerSpec]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    (directory / "docker-compose.json").write_text(
        json.dumps(render_compose(services), indent=2), encoding="utf-8",
    )
    return directory / "Dockerfile"


class LocalDockerClient:
    backend_name = "local-docker"

    def __init__(self, binary: str = "docker") -> None:
        self._binary = binary

    def _run(self, *args: str) -> str:
        try:
            completed = subprocess.run(
                [self._binary, *args],
                capture_output=True, text=True, timeout=120,
            )
        except FileNotFoundError as exc:
            raise DockerUnavailableError(f"{self._binary} not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerRuntimeError(f"command timed out: {args}") from exc
        if completed.returncode != 0:
            raise DockerRuntimeError(completed.stderr.strip() or f"exit {completed.returncode}")
        return completed.stdout.strip()

    def is_available(self) -> bool:
        try:
            self._run("version", "--format", "{{.Server.Version}}")
            return True
        except DockerUnavailableError:
            raise
        except DockerRuntimeError:
            return False

    def build(self, context_dir: Path, tag: str) -> BuildResult:
        started = time.monotonic()
        try:
            self._run("build", "-t", tag, str(context_dir))
        except DockerRuntimeError as exc:
            raise ImageBuildError(tag, str(exc)) from exc
        duration = time.monotonic() - started
        return BuildResult(image_tag=tag, layers_cached=False,
                           duration_seconds=round(duration, 2))

    def start(self, spec: ContainerSpec) -> str:
        return self._run(*spec.run_args)[:12]

    def stop(self, name: str) -> None:
        self._run("stop", name)

    def logs(self, name: str, tail_lines: int = 100) -> str:
        return self._run("logs", "--tail", str(tail_lines), name)

    def running_containers(self) -> list[dict[str, Any]]:
        output = self._run(
            "ps", "--format", "{{json .}}",
        )
        containers: list[dict[str, Any]] = []
        for line in output.splitlines():
            if line.strip():
                containers.append(json.loads(line))
        return containers


class SimulatedDockerClient(LocalDockerClient):
    backend_name = "simulated"

    def __init__(self) -> None:
        super().__init__()
        self._running: dict[str, ContainerSpec] = {}
        self._built_tags: set[str] = set()
        self.fail_next_build = False

    def is_available(self) -> bool:
        return True

    def build(self, context_dir: Path, tag: str) -> BuildResult:
        if self.fail_next_build:
            self.fail_next_build = False
            raise ImageBuildError(tag, "simulated build failure")
        self._built_tags.add(tag)
        return BuildResult(image_tag=tag, layers_cached=True, duration_seconds=0.1)

    def start(self, spec: ContainerSpec) -> str:
        if spec.image not in self._built_tags:
            raise ImageBuildError(spec.image, "image not built yet")
        self._running[spec.name] = spec
        return spec.name[:12]

    def stop(self, name: str) -> None:
        if name not in self._running:
            raise ContainerNotFoundError(name)
        del self._running[name]

    def running_containers(self) -> list[dict[str, Any]]:
        return [
            {"name": spec.name, "image": spec.image}
            for spec in self._running.values()
        ]


__all__ = [
    "BuildResult",
    "ContainerNotFoundError",
    "ContainerSpec",
    "DockerRuntimeError",
    "DockerUnavailableError",
    "ImageBuildError",
    "LocalDockerClient",
    "SimulatedDockerClient",
    "render_compose",
    "render_dockerfile",
    "write_deployment_bundle",
]
