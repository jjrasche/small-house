"""Print every field the engine returns for a world config: what `we expand` places, what `we geometry` says each piece is made of, what each solver in `we solve` says, each rule `we evaluate`
judges, and what `we simulate` answers over the clock (when each piece is placed, the stocks, hours and skills at the end and each stock's unknown contributors, each task's runs), and how each option of a ranked system scores on the config's ranking weights.

Usage: python3 fields.py [world.json]   (default: this folder's world.json)
Nothing here computes anything; every line is a value the engine printed.
"""
import json
import os
import tempfile
import subprocess
import sys
from pathlib import Path

WORLD = Path(__file__).resolve().parent
ENGINE = Path(os.environ.get("WORLD_ENGINE_DIR") or WORLD.parent / "world-engine").resolve()
RANKED_SYSTEMS = ("door_slab",)
WINDOW_WALL_LAYOUTS = {"two-stacked-4x8": (2, 1), "one-8x8": (1, 1), "four-4x4": (2, 2)}


def run_engine(command: str, config: Path, *flags: str) -> dict:
    finished = subprocess.run(["sh", str(ENGINE / "kotlin" / "we"), command, str(config), *flags], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return json.loads(finished.stdout)


def print_placed(expansion: dict) -> None:
    for kind in ("objects", "instances"):
        for placed in expansion.get(kind, []):
            fields = ", ".join(f"{name}={value}" for name, value in placed.get("fields", {}).items())
            print(f"{kind[:-1]} {placed['id']} [{placed['system']}] elevation_mm={placed.get('elevation_mm')} {fields}")
    print(f"supplied {expansion.get('supplied')}")


def print_materials(geometry: dict) -> None:
    for piece in geometry.get("pieces", []):
        layers = ", ".join(f"{layer['name']} {layer['material']} {layer['thickness_mm']} mm ({layer['source']})" for layer in piece.get("layers") or [])
        print(f"geometry {piece['id']} material={piece['material']} material_source={piece['material_source']} layers=[{layers}]")


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
    for stock, contributors in simulated.get("final_stocks_incomplete", {}).items():
        print(f"simulate final_stocks_incomplete {stock} unknown=[{', '.join(contributors)}]")
    if "objective_total" in simulated:
        print("simulate objective_total " + ", ".join(f"{name}={value}" for name, value in simulated["objective_total"].items()))
        for person, skills in simulated["skills_final"].items():
            print(f"simulate skills_final {person} " + ", ".join(f"{skill}={level}" for skill, level in skills.items()))


def print_ranking(ranked: dict) -> None:
    if "refused" in ranked:
        print("rank refused:", ranked["refused"])
        return
    for entry in ranked["ranked"]:
        figures = ", ".join(f"{name}={figure['value']}" + (f" incomplete=[{', '.join(figure['incomplete'])}]" if figure.get("incomplete") else "")
                            for name, figure in entry["figures"].items())
        print(f"rank {ranked['system']} {entry['rank']} {entry['solution']}{' (chosen)' if entry['chosen'] else ''} settled={entry['settled']} {figures}")


def print_layouts(config: Path) -> None:
    world = json.loads(config.read_text(encoding="utf-8"))
    for name, (rows, columns) in WINDOW_WALL_LAYOUTS.items():
        world["systems"]["glazing"]["settings"].update({"rows": rows, "columns": columns})
        with tempfile.NamedTemporaryFile("w", suffix=".json", dir=config.parent, delete=False) as variant:
            json.dump(world, variant)
        simulated = run_engine("simulate", Path(variant.name))
        Path(variant.name).unlink()
        incomplete = simulated.get("final_stocks_incomplete", {}).get("cost_usd", [])
        print(f"layout glazing rows={rows} columns={columns} ({name}) cost_usd={simulated['final_stocks'].get('cost_usd')} unknown=[{', '.join(incomplete)}] "
              f"labour_hours={simulated['objective_total'].get('labour_hours')}")


def main() -> int:
    config = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else WORLD / "world.json"
    expansion = run_engine("expand", config)
    if "refused" in expansion:
        print("refused:", expansion["refused"])
        return 1
    print_placed(expansion)
    print_materials(run_engine("geometry", config))
    print_solvers(run_engine("solve", config))
    for rule in run_engine("evaluate", config)["rules"]:
        print(f"rule {rule['id']} ({rule['domain']}) {rule['status']} {rule['detail']}")
    if "clock" in json.loads(config.read_text(encoding="utf-8")):
        print_simulation(run_engine("simulate", config))
        print_layouts(config)
    for system in RANKED_SYSTEMS:
        print_ranking(run_engine("rank", config, "--system", system))
    return 0


if __name__ == "__main__":
    sys.exit(main())
