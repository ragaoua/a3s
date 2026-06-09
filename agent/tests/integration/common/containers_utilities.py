import io
import socket
import tarfile
import time
from pathlib import Path

import docker
import httpx
from testcontainers.core.container import DockerContainer


def build_image(*, context_dir: Path, tag: str, labels: dict[str, str]) -> None:
    """Build a docker image from `context_dir`.

    Streams the build context as a tar with ownership normalised to 0:0 —
    rootless podman can't map the host user's UID/GID into the build
    container's namespace (the host UID falls outside the configured
    subuid/subgid range), and an unnormalised context blows up with a
    `lchown invalid argument` error during the build.
    """
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for entry in sorted(context_dir.rglob("*")):
            if not entry.is_file():
                continue
            arcname = str(entry.relative_to(context_dir))
            info = tar.gettarinfo(str(entry), arcname=arcname)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            with entry.open("rb") as fp:
                tar.addfile(info, fp)
    buffer.seek(0)

    client = docker.from_env()
    stream = client.api.build(  # pyright: ignore[reportUnknownMemberType]
        fileobj=buffer,
        custom_context=True,
        tag=tag,
        rm=True,
        decode=True,
        labels=labels,
    )
    for chunk in stream:
        if "error" in chunk:
            raise RuntimeError(f"image build failed for {tag}: {chunk['error']}")


def reap_leaked_containers(label: str) -> None:
    """Kill any containers left over from a previous run of the suite."""
    client = docker.from_env()
    for container in client.containers.list(all=True, filters={"label": label}):
        try:
            container.remove(force=True)
        except Exception:
            pass


def with_suite_label(
    container: DockerContainer, labels: dict[str, str]
) -> DockerContainer:
    return container.with_kwargs(labels=labels)


def poll_until_ready(
    url: str,
    *,
    timeout_seconds: float,
    description: str,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code == 200:
                return
            last_error = RuntimeError(f"GET {url} returned {response.status_code}")
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(1.0)
    raise TimeoutError(
        f"{description} not ready at {url} after {timeout_seconds:.0f}s"
    ) from last_error


def wait_for_port(host: str, port: int, *, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.5)
    raise TimeoutError(
        f"{host}:{port} did not start accepting connections within {timeout_seconds:.0f}s"
    ) from last_error
