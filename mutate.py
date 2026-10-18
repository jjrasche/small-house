"""World mutation test: remove one system at a time and see what the engine says.

Usage: python3 mutate.py [world.json]
For each system the config names, a copy of the config without that system (and without it in `binds`) goes to `we expand`, `we solve` and `we evaluate`.
A removal is CAUGHT when the engine refuses it, a solver's answer changes or turns unknown, or the placed objects change.
It SURVIVES when nothing the engine prints differs from the unmutated world: nothing in the domains noticed that the part was gone.
The real world.json is never changed; the mutants are throwaway copies in a temp folder.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WORLD = Path(__file__).resolve().parent
ENGINE = Path(os.environ.get("WORLD_ENGINE_DIR") or WORLD.parent / "world-engine").resolve()


def run_engine(command: str, config: Path) -> dict:
    finished = subprocess.run(["sh", str(ENGINE / "kotlin" / "we"), command, str(config)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return json.loads(finished.stdout)


def read_fields(config: Path) -> dict:
    expanded = run_engine("expand", config)
    if "refused" in expanded:
        return {"refused": expanded["refused"]["rule"]}
    placed = sorted(f"{p['system']}:{p['id']}" for kind in ("objects", "instances") for p in expanded[kind])
    solved = {s["function"]: (s["status"], s["detail"], s["values"]) for s in run_engine("solve", config)["solvers"]}
    rules = {r["id"]: (r["status"], r["detail"]) for r in run_engine("evaluate", config)["rules"]}
    return {"placed": placed, "solvers": solved, "rules": rules}


def without_system(world: dict, name: str) -> dict:
    mutant = copy.deepcopy(world)
    del mutant["systems"][name]
    for role, bound in list(mutant.get("binds", {}).items()):
        kept = [b for b in ([bound] if isinstance(bound, str) else bound) if b != name]
        if kept:
            mutant["binds"][role] = kept if isinstance(bound, list) else kept[0]
        else:
            del mutant["binds"][role]
    return mutant


def judge_mutant(baseline: dict, mutant: dict) -> str:
    if "refused" in mutant:
        return f"CAUGHT  refused by rule {mutant['refused']}"
    changes = []
    lost = len(baseline["placed"]) - len(mutant["placed"])
    if lost:
        changes.append(f"{lost} placed items gone")
    for function, answer in mutant["solvers"].items():
        before = baseline["solvers"].get(function)
        if before != answer:
            changes.append(f"{function}: {before[0]} -> {answer[0]}" + (f" ({answer[1]})" if answer[0] == "unknown" else ""))
    for rule, answer in mutant["rules"].items():
        if baseline["rules"].get(rule) != answer:
            changes.append(f"rule {rule}: {baseline['rules'].get(rule, ('absent',))[0]} -> {answer[0]} ({answer[1]})")
    for rule in set(baseline["rules"]) - set(mutant["rules"]):
        changes.append(f"rule {rule} no longer runs")
    return "CAUGHT  " + "; ".join(changes) if changes else "SURVIVED  nothing the engine prints changed"


def main() -> int:
    config = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else WORLD / "world.json"
    world = json.loads(config.read_text(encoding="utf-8"))
    baseline = read_fields(config)
    survivors = 0
    with tempfile.TemporaryDirectory() as scratch:
        shutil.copytree(config.parent / "domains", Path(scratch) / "domains")
        for name in world["systems"]:
            path = Path(scratch) / "mutant.json"
            path.write_text(json.dumps(without_system(world, name)), encoding="utf-8")
            verdict = judge_mutant(baseline, read_fields(path))
            survivors += verdict.startswith("SURVIVED")
            print(f"remove {name}: {verdict}")
    print(f"{len(world['systems']) - survivors} of {len(world['systems'])} removals caught, {survivors} survived")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
