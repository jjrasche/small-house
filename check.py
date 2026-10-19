"""Check the small house world on the pinned world engine, with the standard library alone.

world.json is Jim's small house: systems that pin the physics, construction, light, thermal, structural and catalog domains by the sha256
of their bytes (the jars and the physics file are kept in domains/). The check runs the engine on it:
  the pins match the bytes on disk;
  `we expand` places 22 objects (the walls as 4 ft SIP panels) and 3 openings and carries the sketch's 630 board feet;
  `we solve` answers the daylight factor, the glazing heat balance, the design-day load, the heating season, the joist deflection and the
gravity load path (which pieces have a known self-weight, occupancy load and force, and why the rest are unknown);
  a pin changed by one digit is refused by the engine (plant domain-pin-stale).
One line a check; '<n> of <m> small house checks agree'; exit 1 on any difference, 2 when the engine cannot be used.
Usage: python3 check.py [--plant domain-pin-stale]
"""
import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

WORLD = Path(__file__).resolve().parent
WORLD_FILE = "world.json"
EXIT_REFUSED = 2
OBJECTS_PLACED = 22
WINDOWS_PLACED = 3
BOARD_FEET = 630
DAYLIGHT_FACTOR_PERCENT = 7.365
HEAT_LOSS_WATT = 332.855
SOLAR_GAIN_WATT = 1783.153
DESIGN_DAY_LOSS_BTU_PER_HOUR = 2076.43
DESIGN_DAY_SOLAR_BTU_PER_HOUR = 6084.371
SEASON = {"season_loss_btu": 9834109.401, "season_solar_btu": 6159297.136, "solar_share_percent": 62.632, "fuel_units_needed": 0.262}
DECIMALS = 3
LOAD_PATH_COUNTS = {"pieces": 25, "pieces_weight_known": 9, "pieces_force_known": 0}
FLOOR = "floor@610,2438,-114:1~2438x2438"
LOFT = "floor@610,2438,2438:1~2438x2438"
JOIST = "joist@610,2438,2438:1~38x2438"
POST = "post@610,2438,-1219"
SOUTH_PANELS = ("wall@610,2438:2~1219x114", "wall@1829,2438:2~1219x114")
NORTH_PANELS = ("wall@610,4762:2~1219x114", "wall@1829,4762:2~1219x114")
WEST_PANELS = ("wall@610,2552:2~114x1219", "wall@610,3771:2~114x991")
KNOWN_PIECE_NEWTONS = {f"{FLOOR} weight_n": 955.827, f"{FLOOR} applied_n": 8537.784, f"{LOFT} applied_n": 8537.784,
                       f"{SOUTH_PANELS[0]} weight_n": 239.153, f"{SOUTH_PANELS[1]} weight_n": 239.153,
                       f"{NORTH_PANELS[0]} weight_n": 239.153, f"{NORTH_PANELS[1]} weight_n": 717.066,
                       f"{WEST_PANELS[0]} weight_n": 717.066, f"{WEST_PANELS[1]} weight_n": 582.947}
UNKNOWN_PIECE_REASONS = {
    f"{JOIST} weight_n": "spf-no2 density not banked: the catalog solution carries no density_lb_per_ft3",
    f"{POST} reaction_n": "not measured (size-unknown): no figure for width_mm, depth_mm, above_grade_mm, section_mm",
    f"{LOFT} weight_n": "not measured (size-unknown): no figure for thickness_mm, height_mm",
}


class Refused(Exception):
    pass


def locate_engine() -> Path:
    return Path(os.environ.get("WORLD_ENGINE_DIR") or WORLD.parent / "world-engine").resolve()


def require_engine(engine: Path) -> Path:
    pin = (WORLD / "engine.pin").read_text(encoding="utf-8").strip()
    launcher = engine / "kotlin" / ("we.cmd" if os.name == "nt" else "we")
    if not launcher.is_file():
        raise Refused(f"no Kotlin launcher at {launcher}; set WORLD_ENGINE_DIR to a world-engine checkout")
    ancestry = subprocess.run(["git", "-C", str(engine), "merge-base", "--is-ancestor", pin, "HEAD"], capture_output=True)
    if ancestry.returncode != 0:
        raise Refused(f"the engine at {engine} does not contain engine.pin {pin}")
    return launcher


def run_engine(launcher: Path, command: str, world: Path) -> tuple[int, dict]:
    finished = subprocess.run([str(launcher), command, str(world)], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    if not finished.stdout.strip():
        raise Refused(f"`we {command}` answered nothing (exit {finished.returncode}): {finished.stderr.strip()}")
    return finished.returncode, json.loads(finished.stdout)


def read_world() -> dict:
    return json.loads((WORLD / WORLD_FILE).read_text(encoding="utf-8"))


def stale_pin(sha: str) -> str:
    return ("1" if sha[0] == "0" else "0") + sha[1:]


def plant_domain_pin_stale(world: dict) -> None:
    world["uses"][0]["sha256"] = stale_pin(world["uses"][0]["sha256"])


PLANTS = {"domain-pin-stale": plant_domain_pin_stale}


def write_world_copy(world: dict, scratch: Path) -> Path:
    shutil.copytree(WORLD / "domains", scratch / "domains")
    path = scratch / WORLD_FILE
    path.write_text(json.dumps(world), encoding="utf-8")
    return path


def judge(expected, observed) -> str:
    return "agrees" if expected == observed else "differs"


def state_line(what: str, expected, observed) -> str:
    return f"{what}: {expected} against {observed}: {judge(expected, observed)}"


def pin_lines(world: dict) -> list[str]:
    return [state_line(f"{entry['file']} pinned by its bytes", entry["sha256"], hashlib.sha256((WORLD / entry["file"]).read_bytes()).hexdigest())
            for entry in world["uses"]]


def solver_values(solved: dict, function: str) -> dict:
    return next((s["values"] for s in solved.get("solvers", []) if s["function"] == function), {})


def solver_answer(solved: dict, function: str) -> dict:
    return next((s for s in solved.get("solvers", []) if s["function"] == function), {})


def piece_figures(solved: dict, function: str, names: list[str]) -> dict:
    pieces = solver_answer(solved, function).get("objects", {})
    return {name: pieces.get(name.split(" ")[0], {}).get(name.split(" ")[1]) for name in names}


def rounded_figures(figures: dict) -> dict:
    return {name: round(value, DECIMALS) if isinstance(value, float) else value for name, value in figures.items()}


def unknown_reasons(figures: dict) -> dict:
    return {name: value.get("unknown") if isinstance(value, dict) else value for name, value in figures.items()}


def rule_statuses(launcher: Path, world: Path) -> dict:
    _, evaluated = run_engine(launcher, "evaluate", world)
    return {rule["id"]: rule["status"] for rule in evaluated.get("rules", [])}


def rounded(values: dict) -> dict:
    return {key: round(number, DECIMALS) for key, number in values.items()}


def engine_lines(launcher: Path, world: Path) -> list[str]:
    expand_exit, expanded = run_engine(launcher, "expand", world)
    solve_exit, solved = run_engine(launcher, "solve", world)
    return [
        state_line("we expand exit, objects, windows, board feet", (0, OBJECTS_PLACED, WINDOWS_PLACED, BOARD_FEET),
                   (expand_exit, len(expanded.get("objects", [])), len(expanded.get("instances", [])),
                    expanded.get("supplied", {}).get("board_feet", {}).get("value"))),
        state_line("we solve daylight factor percent", {"daylight_factor_percent": DAYLIGHT_FACTOR_PERCENT},
                   rounded(solver_values(solved, "average-daylight-factor"))),
        state_line("we solve heat watts through the glass", {"heat_loss_watt": HEAT_LOSS_WATT, "solar_gain_watt": SOLAR_GAIN_WATT},
                   rounded(solver_values(solved, "glazing-balance"))),
        state_line("we evaluate rules", {"egress-door-size": "pass", "posts-below-frost-line": "pass", "roof-covers-floor": "pass", "posts-under-floor": "pass", "walls-enclose-floor": "pass", "roof-is-over-floor": "pass", "joists-span-the-deck": "pass"}, rule_statuses(launcher, world)),
        state_line("we solve joist deflection and stress", {"deflection_mm": 4.264, "span_over_deflection": 571.697, "bending_stress_mpa": 4.654}, rounded(solver_values(solved, "joist-deflection"))),
        state_line("we solve design day BTU per hour", {"loss_btu_per_hour": DESIGN_DAY_LOSS_BTU_PER_HOUR, "solar_gain_btu_per_hour": DESIGN_DAY_SOLAR_BTU_PER_HOUR},
                   rounded(solver_values(solved, "design-day-load"))),
        state_line("we solve heating season BTU and trees", SEASON, rounded(solver_values(solved, "heating-season"))),
        state_line("we solve gravity load path status and piece counts", ("unknown", LOAD_PATH_COUNTS),
                   (solver_answer(solved, "gravity-load-path").get("status"), solver_values(solved, "gravity-load-path"))),
        state_line("we solve gravity load path newtons on the floor, the loft and the wall panels less their openings", KNOWN_PIECE_NEWTONS,
                   rounded_figures(piece_figures(solved, "gravity-load-path", list(KNOWN_PIECE_NEWTONS)))),
        state_line("we solve gravity load path pieces unknown and why", UNKNOWN_PIECE_REASONS,
                   unknown_reasons(piece_figures(solved, "gravity-load-path", list(UNKNOWN_PIECE_REASONS)))),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plant", choices=sorted(PLANTS), help="run on a copy carrying this defect; the check must exit 1")
    options = parser.parse_args()
    engine = locate_engine()
    try:
        launcher = require_engine(engine)
        world = read_world()
        if options.plant:
            PLANTS[options.plant](world)
        with tempfile.TemporaryDirectory() as scratch:
            lines = pin_lines(world)
            lines += engine_lines(launcher, write_world_copy(copy.deepcopy(world), Path(scratch)))
    except Refused as refusal:
        print(f"refused: {refusal}")
        return EXIT_REFUSED
    print(f"engine {engine} contains engine.pin")
    for line in lines:
        print(line)
    agreed = sum(line.endswith(": agrees") for line in lines)
    print(f"{agreed} of {len(lines)} small house checks agree")
    return 0 if agreed == len(lines) else 1


if __name__ == "__main__":
    sys.exit(main())
