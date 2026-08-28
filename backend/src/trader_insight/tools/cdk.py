"""Expose the pinned, backend-local AWS CDK CLI through ``uv run cdk``."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Delegate arguments to the checked-in-lockfile AWS CDK CLI installation."""
    backend_directory = Path(__file__).resolve().parents[3]
    cli_entry_point = backend_directory / "node_modules" / "aws-cdk" / "bin" / "cdk"
    node_executable = shutil.which("node")

    if node_executable is None:
        message = "Node.js is required to run the local AWS CDK CLI."
        raise RuntimeError(message)
    if not cli_entry_point.is_file():
        message = "Install the pinned AWS CDK CLI with `npm --prefix backend ci` before synthesis."
        raise RuntimeError(message)

    return subprocess.run(
        [node_executable, str(cli_entry_point), *sys.argv[1:]], check=False
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
