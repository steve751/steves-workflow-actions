"""Build the wheel and add the site hook that registers the engine steps."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PTH_NAME = "data_product_actions.pth"
PTH_BODY = "import data_product_actions\n"


def main() -> None:
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    for old in dist.glob("*.whl"):
        old.unlink()
    subprocess.check_call(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", "dist"],
        cwd=ROOT,
    )
    wheels = sorted(dist.glob("data_product_actions-*.whl"))
    if not wheels:
        raise SystemExit("wheel was not written to dist/")
    wheel = wheels[-1]
    with zipfile.ZipFile(wheel, "a") as archive:
        if PTH_NAME not in archive.namelist():
            archive.writestr(PTH_NAME, PTH_BODY)
    print(wheel)


if __name__ == "__main__":
    main()
