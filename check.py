"""Check the small house world on the pinned world engine, with the standard library alone.

world.json is Jim's small house: systems that pin the physics, construction, light, thermal, structural and catalog domains by the sha256
of their bytes (the jars and the physics file are kept in domains/). The check runs the engine on it:
  the pins match the bytes on disk;
  `we expand` places 22 objects (the walls as 4 ft SIP panels) and 3 openings and carries the sketch's 630 board feet;
  `we solve` answers the daylight factor, the glazing heat balance, the design-day load, the heating season, the joist deflection and the
gravity load path (which pieces have a known self-weight, occupancy load and force, and why the rest are unknown), the hours and
blank prices of the measured build tasks at their published rates, and the header over each opening (its load and utilisation, and why
its own weight is unknown);
  `we rank` puts the window-wall options on first cost and build hours, both gaps;
  `we simulate` answers the minute each piece is placed, the labour hours, the cost and the budget left, the skill each person ends with,
how many times each task runs (every task runs), and that each placed piece is in the places of a flow at the step it is placed;
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
JOIST = "joist@610,2438,2298:1~38x2438"
POST = "post@610,2438,-1219~140x140"
SOUTH_PANELS = ("wall@610,2438:2~1219x114", "wall@1829,2438:2~1219x114")
NORTH_PANELS = ("wall@610,4762:2~1219x114", "wall@1829,4762:2~1219x114")
WEST_PANELS = ("wall@610,2552:2~114x1219", "wall@610,3771:2~114x991")
KNOWN_PIECE_NEWTONS = {f"{FLOOR} weight_n": 955.827, f"{FLOOR} applied_n": 8537.784, f"{LOFT} applied_n": 8537.784,
                       f"{SOUTH_PANELS[0]} weight_n": 239.153, f"{SOUTH_PANELS[1]} weight_n": 239.153,
                       f"{NORTH_PANELS[0]} weight_n": 239.153, f"{NORTH_PANELS[1]} weight_n": 717.066,
                       f"{WEST_PANELS[0]} weight_n": 717.066, f"{WEST_PANELS[1]} weight_n": 582.947}
PLACED_AT_MINUTE = {"post@3048,2438,-1219~140x140": 29, "post@3048,4876,-1219~140x140": 59, "post@610,2438,-1219~140x140": 89, "post@610,4876,-1219~140x140": 119,
                    FLOOR: 174, "wall@1829,2438:2~1219x114": 204, "wall@1829,4762:2~1219x114": 234, "wall@2934,2552:2~114x1219": 264, "wall@2934,3771:2~114x991": 289,
                    "wall@610,2438:2~1219x114": 319, "wall@610,2552:2~114x1219": 349, "wall@610,3771:2~114x991": 374, "wall@610,4762:2~1219x114": 404,
                    "roof@0,0,3658:3~3658x5486": 481, "door@610,4819": 901, "glazing@610,2495,1219": 991, "glazing@610,2495,2438": 1081,
                    "joist@1016,2438,2298:1~38x2438": 1103, "joist@1422,2438,2298:1~38x2438": 1125, "joist@1828,2438,2298:1~38x2438": 1147,
                    "joist@2234,2438,2298:1~38x2438": 1169, "joist@2640,2438,2298:1~38x2438": 1191, "joist@3010,2438,2298:1~38x2438": 1213,
                    "joist@610,2438,2298:1~38x2438": 1235, LOFT: 1325}
BUILD_TOTALS = {"labour_hours": 59.699, "cost_usd": 6445.356, "budget_usd": 13554.644, "pieces_not_priced": 11.0}
SKILLS_FINAL = {"jim": {"sip-setting": 1.578333}, "sip_lead": {"sip-setting": 3.0}}
TASK_RUNS = {"dig-post-holes": 4, "set-posts": 4, "set-floor-panels": 1, "set-wall-panels": 8, "set-roof-panels": 1, "cut-openings": 3, "set-windows-and-door": 3,
             "frame-loft": 7, "lay-subfloor": 1, "install-boiler": 1}
WORK_AT_PUBLISHED_RATES = {"post_holes_hours": 2.0, "set_posts_hours": 2.0, "floor_hours": 1.0, "walls_hours": 5.631, "roof_hours": 1.912, "cut_openings_hours": 6.0,
                           "windows_and_door_hours": 14.0, "frame_loft_hours": 5.0, "lay_subfloor_hours": 3.0, "install_boiler_hours": 16.0,
                           "measured_hours": 56.542, "listed_usd": 6445.356, "pieces_not_priced": 11}
LOWER_BAND = "glazing@610,2495,1219"
UPPER_BAND = "glazing@610,2495,2438"
NORTH_DOOR = "door@610,4819"
HEADER_COUNTS = {"headers": 3, "headers_over_one": 0, "utilisation_max": 0.611}
HEADER_FIGURES = {f"{LOWER_BAND} load_n_per_mm": 0.0, f"{LOWER_BAND} utilisation": 0.0, f"{UPPER_BAND} load_n_per_mm": 17.598,
                  f"{UPPER_BAND} utilisation": 0.611, f"{NORTH_DOOR} load_n_per_mm": 2.102, f"{NORTH_DOOR} utilisation": 0.036,
                  f"{LOWER_BAND} unsupported_load_n_per_mm": 2.335, f"{NORTH_DOOR} unsupported_load_n_per_mm": 2.335}
HEADER_WEIGHT_UNKNOWN = {f"{UPPER_BAND} self_weight_n": "header-lvl-11-7-8 carries no density_lb_per_ft3 (gl.prop.lvl_density_unpublished)"}
WINDOW_WALL_RANKS = {"four-4x4": (1, []), "one-8x8": (2, ["first_cost_usd"]), "two-stacked-4x8": (3, ["first_cost_usd"])}
UNKNOWN_PIECE_REASONS = {
    f"{JOIST} weight_n": "spf-no2 density not banked: the catalog solution carries no density_lb_per_ft3",
    f"{POST} reaction_n": "roof@0,0,3658:3~3658x5486 may rest on it: it is in none of the roles panel_pieces, lumber_pieces, occupied_floors, ground and openings, so the load path is given no size or material for it",
    f"{LOFT} weight_n": "no material is bound to its system",
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


def build_totals(simulated: dict) -> dict:
    stocks = simulated.get("final_stocks", {})
    return rounded({"labour_hours": simulated.get("objective_total", {}).get("labour_hours", 0.0), "cost_usd": stocks.get("cost_usd", 0.0),
                    "budget_usd": stocks.get("budget_usd", 0.0), "pieces_not_priced": stocks.get("pieces_not_priced", 0.0)})


def rank_line(launcher: Path, world: Path) -> str:
    finished = subprocess.run([str(launcher), "rank", str(world), "--system", "glazing"], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    ranked = json.loads(finished.stdout).get("ranked", []) if finished.stdout.strip() else []
    return state_line("we rank the window-wall options: rank and the figures missing", WINDOW_WALL_RANKS,
                      {entry["solution"]: (entry["rank"], entry["missing"]) for entry in ranked})


def pieces_placed_by_no_flow(simulated: dict) -> list:
    steps = simulated.get("steps", [])
    return sorted(piece for piece, step in simulated.get("placed_at", {}).items()
                  if not any(piece in flow.get("places", []) for flow in steps[step].get("flows", {}).values()))


def simulate_lines(launcher: Path, world: Path) -> list[str]:
    simulate_exit, simulated = run_engine(launcher, "simulate", world)
    totals = simulated.get("totals", {})
    return [
        state_line("we simulate exit, end and the minute each piece is placed", (0, "quiescent", PLACED_AT_MINUTE),
                   (simulate_exit, simulated.get("ended"), simulated.get("placed_at"))),
        state_line("we simulate labour hours, cost, budget left and pieces placed with no price", BUILD_TOTALS, build_totals(simulated)),
        state_line("we simulate the skill each person ends with", SKILLS_FINAL, simulated.get("skills_final")),
        state_line("we simulate runs of every task, none skipped", TASK_RUNS, {flow: total.get("runs") for flow, total in totals.items()}),
        state_line("we simulate pieces whose placed_at step has no flow placing them there", [], pieces_placed_by_no_flow(simulated)),
    ]


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
        state_line("we evaluate rules", {"egress-door-size": "pass", "posts-below-frost-line": "pass", "roof-covers-floor": "pass", "posts-under-floor": "pass", "walls-enclose-floor": "pass", "roof-is-over-floor": "pass", "joists-span-the-deck": "pass", "headers-within-capacity": "pass"}, rule_statuses(launcher, world)),
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
        state_line("we solve build task hours at published rates and the panel blanks' price", WORK_AT_PUBLISHED_RATES,
                   rounded_figures({name: value for name, value in solver_values(solved, "work-at-published-rates").items() if name in WORK_AT_PUBLISHED_RATES})),
        state_line("we solve header check counts and the largest utilisation", ("known", HEADER_COUNTS),
                   (solver_answer(solved, "header-check").get("status"), rounded(solver_values(solved, "header-check")))),
        state_line("we solve header load and utilisation over the two south bands and the north door", HEADER_FIGURES,
                   rounded_figures(piece_figures(solved, "header-check", list(HEADER_FIGURES)))),
        state_line("we solve header self-weight unknown and why", HEADER_WEIGHT_UNKNOWN,
                   unknown_reasons(piece_figures(solved, "header-check", list(HEADER_WEIGHT_UNKNOWN)))),
        rank_line(launcher, world),
    ] + simulate_lines(launcher, world)


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
