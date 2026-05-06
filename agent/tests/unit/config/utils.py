from pathlib import Path
from textwrap import dedent


def write_config(path: Path, body: str) -> None:
    _ = path.write_text(dedent(body), encoding="utf-8")
