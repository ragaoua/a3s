import fnmatch
import io
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

    Honours `<context_dir>/.dockerignore` (simple subset — comments, blank
    lines, fnmatch-style patterns; no negation, no `**`, no path-rooted
    patterns). Without this, dragging `.venv`/build caches into the tar
    would balloon the context for projects with a real virtualenv.
    """
    ignore_patterns = _read_dockerignore(context_dir)

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for entry in sorted(context_dir.rglob("*")):
            if not entry.is_file():
                continue
            rel_path = entry.relative_to(context_dir)
            if _matches_any(rel_path, ignore_patterns):
                continue
            info = tar.gettarinfo(str(entry), arcname=str(rel_path))
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


def _read_dockerignore(context_dir: Path) -> list[str]:
    dockerignore = context_dir / ".dockerignore"
    if not dockerignore.exists():
        return []
    patterns: list[str] = []
    for raw_line in dockerignore.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def _matches_any(rel_path: Path, patterns: list[str]) -> bool:
    """Return True if any component of `rel_path` matches any of the
    fnmatch-style patterns. Permissive vs the real .dockerignore spec
    (which is path-rooted) but a superset for the simple bare-name and
    `*.ext` patterns the suite's .dockerignores use today."""
    for pattern in patterns:
        for component in rel_path.parts:
            if fnmatch.fnmatch(component, pattern):
                return True
    return False


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
