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
