"""Print every field the engine returns for a world config: what `we expand` places, what each solver in `we solve` says, each rule `we evaluate`
judges, and what `we simulate` answers over the clock (when each piece is placed, the stocks, hours and skills at the end, each task's runs).

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
        for piece, figures in solver.get("objects", {}).items():
            print(f"  piece {piece} " + ", ".join(f"{name}={value}" for name, value in figures.items()))
        for source in solver.get("sources", []):
            print(f"  source {source['solution']}.{source['field']} {source['source']} ({source['evidence']})")


def print_simulation(simulated: dict) -> None:
    if "refused" in simulated:
        print("simulate refused:", simulated["refused"])
        return
    clock = simulated["clock"]
    print(f"simulate clock step={clock['step']} unit={clock['unit']} until={clock['until']} ended={simulated['ended']} steps={len(simulated['steps'])}")
    for piece, step in simulated["placed_at"].items():
        print(f"simulate placed_at {piece} {clock['unit']}={step}")
    for flow, total in simulated["totals"].items():
        moved = ", ".join(f"{stock}={amount}" for stock, amount in total["moved"].items())
        print(f"simulate flow {flow} runs={total['runs']} {moved}")
    print("simulate final_stocks " + ", ".join(f"{stock}={amount}" for stock, amount in simulated["final_stocks"].items()))
    if "objective_total" in simulated:
        print("simulate objective_total " + ", ".join(f"{name}={value}" for name, value in simulated["objective_total"].items()))
        for person, skills in simulated["skills_final"].items():
            print(f"simulate skills_final {person} " + ", ".join(f"{skill}={level}" for skill, level in skills.items()))


def main() -> int:
    config = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else WORLD / "world.json"
    expansion = run_engine("expand", config)
    if "refused" in expansion:
        print("refused:", expansion["refused"])
        return 1
    print_placed(expansion)
    print_solvers(run_engine("solve", config))
    for rule in run_engine("evaluate", config)["rules"]:
        print(f"rule {rule['id']} ({rule['domain']}) {rule['status']} {rule['detail']}")
    if "clock" in json.loads(config.read_text(encoding="utf-8")):
        print_simulation(run_engine("simulate", config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
