"""Print every field the engine returns for a world config: what `we expand` places and what each solver in `we solve` says.

Usage: python3 fields.py [world.json]   (default: this folder's world.json)
Nothing here computes anything; every line is a value the engine printed.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

WORLD = Path(__file__).resolve().parent
ENGINE = Path(os.environ.get("WORLD_ENGINE_DIR") or WORLD.parent / "world-engine").resolve()


def run_engine(command: str, config: Path) -> dict:
    finished = subprocess.run(["sh", str(ENGINE / "kotlin" / "we"), command, str(config)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return json.loads(finished.stdout)


def print_placed(expansion: dict) -> None:
    for kind in ("objects", "instances"):
        for placed in expansion.get(kind, []):
            fields = ", ".join(f"{name}={value}" for name, value in placed.get("fields", {}).items())
            print(f"{kind[:-1]} {placed['id']} [{placed['system']}] elevation_mm={placed.get('elevation_mm', 0)} {fields}")
    print(f"supplied {expansion.get('supplied')}")


def print_solvers(solved: dict) -> None:
    for solver in solved["solvers"]:
        values = ", ".join(f"{name}={value}" for name, value in solver["values"].items())
        print(f"solver {solver['function']} ({solver['domain']}) {solver['status']} {solver['detail']} {values}")


def main() -> int:
    config = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else WORLD / "world.json"
    expansion = run_engine("expand", config)
    if "refused" in expansion:
        print("refused:", expansion["refused"])
        return 1
    print_placed(expansion)
    print_solvers(run_engine("solve", config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
