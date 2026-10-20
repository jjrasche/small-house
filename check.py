"""Check the small house world on the pinned world engine, with the standard library alone.

world.json is Jim's small house: systems that pin the physics, construction, light, thermal, structural and catalog domains by the sha256
of their bytes (the jars and the physics file are kept in domains/). The check runs the engine on it:
  the pins match the bytes on disk;
  `we expand` places 24 objects (the walls as 4 ft SIP panels, the loft's joists and the ledgers under them) and 3 openings and carries the
sketch's 630 board feet;
  `we geometry` gives every piece a material, and every piece but the three openings its layers;
  `we solve` answers the daylight factor, the glazing heat balance, the design-day load, the heating season, the joist deflection, the
gravity load path (every piece's self-weight and force, and the reaction under each of the four posts), the hours and blank prices of the
measured build tasks at their published rates, and the header over each opening (its load, utilisation and own weight);
  `we rank` puts the window-wall options on first cost and build hours, both gaps;
  `we simulate` answers the minute each piece is placed, the labour hours, the cost and the budget left, the skill each person ends with,
how many times each task runs (every task runs), and that each placed piece is in the places of a flow at the step it is placed;
  the budget is a target, not a limit: with a $1,000 target every task still runs and budget_usd ends negative by the overrun;
  with --sample, `we sample` 500 runs at seed 1 answers the quality tally of the drawn figures and the share of runs under the $20,000
target and under the deterministic labour hours, alone and together;
  a pin changed by one digit is refused by the engine (plant domain-pin-stale).
One line a check; '<n> of <m> small house checks agree'; exit 1 on any difference, 2 when the engine cannot be used.
Usage: python3 check.py [--plant domain-pin-stale] [--sample]
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
OBJECTS_PLACED = 24
WINDOWS_PLACED = 3
BOARD_FEET = 630
DAYLIGHT_FACTOR_PERCENT = 7.365
HEAT_LOSS_WATT = 332.855
SOLAR_GAIN_WATT = 1783.153
DESIGN_DAY_LOSS_BTU_PER_HOUR = 2076.43
DESIGN_DAY_SOLAR_BTU_PER_HOUR = 6084.371
SEASON = {"season_loss_btu": 9834109.401, "season_solar_btu": 6159297.136, "solar_share_percent": 62.632, "fuel_units_needed": 0.262}
DECIMALS = 3
LOAD_PATH_COUNTS = {"pieces": 27, "pieces_weight_known": 27, "pieces_force_known": 27, "ground_reaction_n": 28007.326}
FLOOR = "floor@610,2438,-114:1~2438x2438"
LOFT = "floor@724,2552,2438:2~2210x2210"
JOIST = "joist@724,2552,2298:2~2210x38"
LEDGER = "ledger@724,2552,2158:2~38x2210"
POSTS = ("post@610,2438,-1219~140x140", "post@2908,2438,-1219~140x140", "post@610,4736,-1219~140x140", "post@2908,4736,-1219~140x140")
POST_REACTION_N = 7001.831
SOUTH_PANELS = ("wall@610,2438:2~1219x114", "wall@1829,2438:2~1219x114")
NORTH_PANELS = ("wall@610,4762:2~1219x114", "wall@1829,4762:2~1219x114")
WEST_PANELS = ("wall@610,2552:2~114x1219", "wall@610,3771:2~114x991")
KNOWN_PIECE_NEWTONS = {f"{FLOOR} weight_n": 956.75, f"{FLOOR} applied_n": 8537.784, f"{LOFT} weight_n": 555.398, f"{LOFT} applied_n": 7015.559,
                       f"{SOUTH_PANELS[0]} weight_n": 239.384, f"{SOUTH_PANELS[1]} weight_n": 239.384,
                       f"{NORTH_PANELS[0]} weight_n": 239.384, f"{NORTH_PANELS[1]} weight_n": 717.758,
                       f"{WEST_PANELS[0]} weight_n": 717.758, f"{WEST_PANELS[1]} weight_n": 583.51,
                       f"{JOIST} weight_n": 52.637, f"{JOIST} force_n": 1134.202, f"{LEDGER} force_n": 4022.345,
                       "roof@0,0,3658:3~3658x5486 weight_n": 3546.574, "door@610,4819 weight_n": 533.787, "glazing@610,2495,1219 weight_n": 924.927}
PLACED_AT_MINUTE = {POSTS[1]: 29, POSTS[3]: 59, POSTS[0]: 89, POSTS[2]: 119,
                    FLOOR: 174, "wall@1829,2438:2~1219x114": 204, "wall@1829,4762:2~1219x114": 234, "wall@2934,2552:2~114x1219": 264, "wall@2934,3771:2~114x991": 289,
                    "wall@610,2438:2~1219x114": 319, "wall@610,2552:2~114x1219": 349, "wall@610,3771:2~114x991": 374, "wall@610,4762:2~1219x114": 404,
                    "roof@0,0,3658:3~3658x5486": 481, "door@610,4819": 901, "glazing@610,2495,1219": 991, "glazing@610,2495,2438": 1081,
                    "joist@724,2552,2298:2~2210x38": 1103, "joist@724,2958,2298:2~2210x38": 1125, "joist@724,3364,2298:2~2210x38": 1147,
                    "joist@724,3770,2298:2~2210x38": 1169, "joist@724,4176,2298:2~2210x38": 1191, "joist@724,4582,2298:2~2210x38": 1213,
                    "joist@724,4724,2298:2~2210x38": 1235, LOFT: 1325}
SAMPLE_ARGUMENTS = ["--runs", "500", "--seed", "1", "--include", "simulation", "--below", "simulation.final_stocks.cost_usd=20000",
                    "--below", "simulation.objective_total.labour_hours=59.699418", "--joint"]
SAMPLE_ANSWER = {"runs": 500, "seed": 1, "failed": {"count": 0, "first": None},
                 "quality": {"assumed": {"inputs": 11, "draws": 5500}, "inferred": {"inputs": 4, "draws": 2000}, "published": {"inputs": 2, "draws": 1000}},
                 "below": {"simulation.final_stocks.cost_usd": {"value": 20000.0, "fraction": 1.0, "n_with_value": 500},
                           "simulation.objective_total.labour_hours": {"value": 59.699418, "fraction": 0.102, "n_with_value": 500}},
                 "joint": {"paths": ["simulation.final_stocks.cost_usd", "simulation.objective_total.labour_hours"], "fraction": 0.102}}
SMALL_TARGET_USD = 1000
OVERRUN_BUDGET_USD = -5445.356
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
                  f"{LOWER_BAND} unsupported_load_n_per_mm": None, f"{NORTH_DOOR} unsupported_load_n_per_mm": None,
                  f"{UPPER_BAND} self_weight_n": 434.075, f"{NORTH_DOOR} self_weight_n": 217.038}
WINDOW_WALL_RANKS = {"four-4x4": (1, []), "one-8x8": (2, ["first_cost_usd"]), "two-stacked-4x8": (3, ["first_cost_usd"])}
UNLAYERED_PIECES = ["door@610,4819", "glazing@610,2495,1219", "glazing@610,2495,2438"]


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


def geometry_lines(launcher: Path, world: Path) -> list[str]:
    geometry_exit, geometry = run_engine(launcher, "geometry", world)
    pieces = geometry.get("pieces", [])
    return [
        state_line("we geometry exit and pieces with no material", (0, []), (geometry_exit, sorted(p["id"] for p in pieces if not p.get("material")))),
        state_line("we geometry pieces with no layers (the openings: no banked build-up across the wall)", UNLAYERED_PIECES, sorted(p["id"] for p in pieces if not p.get("layers"))),
    ]


def target_lines(launcher: Path, world: Path) -> list[str]:
    small_target = json.loads(world.read_text(encoding="utf-8"))
    small_target["stocks"]["budget_usd"] = SMALL_TARGET_USD
    variant = world.with_name("world.small-target.json")
    variant.write_text(json.dumps(small_target), encoding="utf-8")
    _, simulated = run_engine(launcher, "simulate", variant)
    return [state_line(f"we simulate with a ${SMALL_TARGET_USD} target: every task still runs, and budget_usd goes below zero by the overrun",
                       (TASK_RUNS, OVERRUN_BUDGET_USD),
                       ({flow: total.get("runs") for flow, total in simulated.get("totals", {}).items()}, round(simulated.get("final_stocks", {}).get("budget_usd", 0.0), DECIMALS)))]


def sample_lines(launcher: Path, world: Path) -> list[str]:
    finished = subprocess.run([str(launcher), "sample", str(world), *SAMPLE_ARGUMENTS], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    answer = json.loads(finished.stdout) if finished.stdout.strip() else {}
    return [state_line("we sample 500 runs at seed 1: failures, quality tally, share under $20,000 and under the deterministic labour hours, and both",
                       SAMPLE_ANSWER, {key: answer.get(key) for key in SAMPLE_ANSWER})]


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


def engine_lines(launcher: Path, world: Path, is_sampling: bool) -> list[str]:
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
        state_line("we solve joist deflection and stress", {"deflection_mm": 2.879, "span_over_deflection": 767.521, "bending_stress_mpa": 3.824}, rounded(solver_values(solved, "joist-deflection"))),
        state_line("we solve design day BTU per hour", {"loss_btu_per_hour": DESIGN_DAY_LOSS_BTU_PER_HOUR, "solar_gain_btu_per_hour": DESIGN_DAY_SOLAR_BTU_PER_HOUR},
                   rounded(solver_values(solved, "design-day-load"))),
        state_line("we solve heating season BTU and trees", SEASON, rounded(solver_values(solved, "heating-season"))),
        state_line("we solve gravity load path status, piece counts and the ground reaction", ("known", LOAD_PATH_COUNTS),
                   (solver_answer(solved, "gravity-load-path").get("status"), rounded(solver_values(solved, "gravity-load-path")))),
        state_line("we solve gravity load path newtons on the floor, the loft, the wall panels less their openings, a joist, a ledger, the roof, the door and a window",
                   KNOWN_PIECE_NEWTONS, rounded_figures(piece_figures(solved, "gravity-load-path", list(KNOWN_PIECE_NEWTONS)))),
        state_line("we solve gravity load path reaction under each of the four posts", {f"{post} reaction_n": POST_REACTION_N for post in POSTS},
                   rounded_figures(piece_figures(solved, "gravity-load-path", [f"{post} reaction_n" for post in POSTS]))),
        state_line("we solve build task hours at published rates and the panel blanks' price", WORK_AT_PUBLISHED_RATES,
                   rounded_figures({name: value for name, value in solver_values(solved, "work-at-published-rates").items() if name in WORK_AT_PUBLISHED_RATES})),
        state_line("we solve header check counts and the largest utilisation", ("known", HEADER_COUNTS),
                   (solver_answer(solved, "header-check").get("status"), rounded(solver_values(solved, "header-check")))),
        state_line("we solve header load and utilisation over the two south bands and the north door", HEADER_FIGURES,
                   rounded_figures(piece_figures(solved, "header-check", list(HEADER_FIGURES)))),
        rank_line(launcher, world),
    ] + geometry_lines(launcher, world) + simulate_lines(launcher, world) + target_lines(launcher, world) + (sample_lines(launcher, world) if is_sampling else [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plant", choices=sorted(PLANTS), help="run on a copy carrying this defect; the check must exit 1")
    parser.add_argument("--sample", action="store_true", help="also run the seeded 500-run sample (about 50 minutes)")
    options = parser.parse_args()
    engine = locate_engine()
    try:
        launcher = require_engine(engine)
        world = read_world()
        if options.plant:
            PLANTS[options.plant](world)
        with tempfile.TemporaryDirectory() as scratch:
            lines = pin_lines(world)
            lines += engine_lines(launcher, write_world_copy(copy.deepcopy(world), Path(scratch)), options.sample)
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
