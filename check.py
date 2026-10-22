"""Check the small house world on the pinned world engine, with the standard library alone.

world.json is Jim's small house: systems that pin the physics, construction, light, thermal, structural and catalog domains by the sha256
of their bytes (the jars and the physics file are kept in domains/). The check runs the engine on it:
  the pins match the bytes on disk;
  `we expand` places 24 objects (the walls as 4 ft SIP panels, the loft's joists and the ledgers under them) and 3 openings and carries the
sketch's 630 board feet;
  `we geometry` gives every piece a material, and every piece but the three openings its layers;
  `we solve` answers the daylight factor, the glazing heat balance, the design-day load, the heating season, the joist deflection, the
gravity load path (every piece's self-weight and force, and the reaction under each of the four posts), the hours and blank prices of the
measured build tasks at their published rates, the cost of everything bought over the main floor and over the main and loft floors, and the header over each opening (its load, utilisation and own weight);
  `we rank` puts the door options on cost and design-day loss (the steel prehung's simulated cost and loss, the slab-only ones unpriced);
  `we simulate` and `we evaluate` with `--use` on the SIP enclosure and on a used 20 ft standard and a new 20 ft high-cube shipping container
(its floor, walls and roof, piers to the frost depth, and the container build sequence) answer each one's cost, labour hours, the cost of
cutting and steel-framing its openings, and the container-as-dwelling zoning rule (pass for the SIP, fail where the site bars a container);
  `we simulate` on each window-wall layout of the opening grid (two stacked 4x8, one 8x8, four 4x4) answers its cost, what the cost is
missing, and its labour hours;
  `we simulate` answers the minute each piece is placed, the labour hours, the cost and the budget left and what they are missing, the skill each person ends with,
how many times each task runs (every task of the chosen sequence runs, the container's tasks none), and that each placed piece is in the places of a flow at the step it is placed;
  every piece is priced from a listed range, so no stock ends incomplete (a piece with no price would move cost_usd and budget_usd by an
unknown naming it);
  the budget is a target, not a limit: with a $1,000 target every task still runs and budget_usd ends negative by the overrun;
  with --sample, `we sample` on the one-8x8 window wall refuses the share of runs under the $20,000 target, as its 8x8 window has no listed
price, and 50 runs at seed 1 answer the quality tally of the drawn figures and the share of runs under the $20,000 target and under the
deterministic labour hours, alone and together; with --sample-full, 500 runs at seed 1 answer the same, and the median and 95th
percentile of cost and labour hours;
  a pin changed by one digit is refused by the engine (plant domain-pin-stale).
One line a check; '<n> of <m> small house checks agree'; exit 1 on any difference, 2 when the engine cannot be used.
Usage: python3 check.py [--plant domain-pin-stale] [--sample] [--sample-full]
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
ENGINE_ENV = {**os.environ, "JAVA_TOOL_OPTIONS": os.environ.get("JAVA_TOOL_OPTIONS", "-XX:MaxRAMPercentage=75")}
OBJECTS_PLACED = 24
WINDOWS_PLACED = 3
BOARD_FEET = 630
DAYLIGHT_FACTOR_PERCENT = 7.69
HEAT_LOSS_WATT = 361.133
SOLAR_GAIN_WATT = 1931.749
DESIGN_DAY_LOSS_BTU_PER_HOUR = 2338.045
DESIGN_DAY_SOLAR_BTU_PER_HOUR = 6591.402
SEASON = {"season_loss_btu": 10921786.357, "season_solar_btu": 7280153.542, "solar_share_percent": 66.657, "fuel_units_needed": 0.179}
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
                    FLOOR: 174, "wall@1829,2438:2~1219x114": 204, "wall@1829,4762:2~1219x114": 234, "wall@2934,2552:2~114x1219": 264, "wall@2934,3771:2~114x991": 291,
                    "wall@610,2438:2~1219x114": 321, "wall@610,2552:2~114x1219": 351, "wall@610,3771:2~114x991": 393, "wall@610,4762:2~1219x114": 423,
                    "roof@0,0,3658:3~3658x5486": 500, "door@610,4819": 920, "glazing@610,2495,1219": 1010, "glazing@610,2495,2438": 1100,
                    "joist@724,2552,2298:2~2210x38": 1131, "joist@724,2958,2298:2~2210x38": 1162, "joist@724,3364,2298:2~2210x38": 1193,
                    "joist@724,3770,2298:2~2210x38": 1224, "joist@724,4176,2298:2~2210x38": 1255, "joist@724,4582,2298:2~2210x38": 1286,
                    "joist@724,4724,2298:2~2210x38": 1317, LOFT: 1407}
UNPRICED_IN_ONE_8X8 = ["glazing@610,2495,1219"]
COST_BELOW_ARGUMENTS = ["--runs", "2", "--seed", "1", "--include", "simulation", "--below", "simulation.final_stocks.cost_usd=20000"]
COST_BELOW_REFUSAL = {"rule": "sample-output-incomplete",
                      "message": "simulation.final_stocks.cost_usd has contributors whose value is unknown: " + ", ".join(UNPRICED_IN_ONE_8X8), "setting": None}
SAMPLE_ARGUMENTS = ["--runs", "50", "--seed", "1", "--include", "simulation", "--below", "simulation.final_stocks.cost_usd=20000",
                    "--below", "simulation.objective_total.labour_hours=61.799397", "--joint"]
SAMPLE_ANSWER = {"runs": 50, "seed": 1, "failed": {"count": 0, "first": None},
                 "quality": {"assumed": {"inputs": 9, "draws": 450}, "inferred": {"inputs": 5, "draws": 250}, "published": {"inputs": 15, "draws": 750}},
                 "below": {"simulation.final_stocks.cost_usd": {"value": 20000.0, "fraction": 1.0, "n_with_value": 50},
                           "simulation.objective_total.labour_hours": {"value": 61.799397, "fraction": 0.06, "n_with_value": 50}},
                 "joint": {"paths": ["simulation.final_stocks.cost_usd", "simulation.objective_total.labour_hours"], "fraction": 0.06}}
FULL_SAMPLE_ARGUMENTS = ["--runs", "500", *SAMPLE_ARGUMENTS[2:]]
FULL_SAMPLE_ANSWER = {"runs": 500, "seed": 1, "failed": {"count": 0, "first": None},
                      "quality": {"assumed": {"inputs": 9, "draws": 4500}, "inferred": {"inputs": 5, "draws": 2500}, "published": {"inputs": 15, "draws": 7500}},
                      "below": {"simulation.final_stocks.cost_usd": {"value": 20000.0, "fraction": 1.0, "n_with_value": 500},
                                "simulation.objective_total.labour_hours": {"value": 61.799397, "fraction": 0.128, "n_with_value": 500}},
                      "joint": {"paths": ["simulation.final_stocks.cost_usd", "simulation.objective_total.labour_hours"], "fraction": 0.128}}
FULL_SAMPLE_PERCENTILES = {"simulation.final_stocks.cost_usd": {"p50": 15517.63, "p95": 18186.594},
                           "simulation.objective_total.labour_hours": {"p50": 68.658, "p95": 79.218}}
SMALL_TARGET_USD = 1000
OVERRUN_BUDGET_USD = -13211.387
OVERRUN_COST_USD = 13211.387
BUILD_TOTALS = {"labour_hours": 62.933, "cost_usd": 14211.387, "budget_usd": 5788.613}
INCOMPLETE_STOCKS = {}
SKILLS_FINAL = {"jim": {"sip-setting": 1.578333}, "sip_lead": {"sip-setting": 3.0}}
TASK_RUNS = {"south-sun-ledger": 0, "stove-hour": 0, "greenhouse-hour": 0, "dig-post-holes": 4, "set-posts": 4, "set-floor-panels": 1, "set-wall-panels": 8, "cut-wall-panels": 2, "set-roof-panels": 1, "cut-openings": 3, "set-windows-and-door": 3,
             "frame-loft": 7, "lay-subfloor": 1, "install-boiler": 1, "pour-piers": 0, "set-container": 0, "cut-container-openings": 0,
             "frame-container-openings": 0, "spray-foam": 0}
NOT_APPLICABLE_FLOWS = {"south-sun-ledger": "the world has no system for the role greenhouse, which south-sun-ledger needs",
                        "stove-hour": "the world has no system for the role stove, which stove-hour needs",
                        "greenhouse-hour": "the world has no system for the role greenhouse, which greenhouse-hour needs"}
WORK_AT_PUBLISHED_RATES = {"post_holes_hours": 2.0, "set_posts_hours": 2.0, "floor_hours": 1.0, "cut_panels_hours": 1.069, "walls_hours": 5.631, "roof_hours": 1.912, "cut_openings_hours": 6.0,
                           "windows_and_door_hours": 14.0, "frame_loft_hours": 7.2, "lay_subfloor_hours": 3.0, "install_boiler_hours": 16.0,
                           "measured_hours": 59.812, "listed_usd": 8263.887, "pieces_not_priced": 0,
                           "cost_usd": 14211.387, "main_floor_ft2": 63.979, "loft_floor_ft2": 52.572, "floor_ft2_total": 116.551,
                           "cost_usd_per_main_floor_ft2": 222.126, "cost_usd_per_floor_ft2": 121.933}
RIP_METHODS = {"rip_blank_lb": 161.627, "rip_piece_lb": 131.397, "rip_by_circular_saw_man_hours_low": 0.257, "rip_by_circular_saw_man_hours_likely": 0.535,
               "rip_by_circular_saw_man_hours_high": 1.084, "rip_by_circular_saw_elapsed_minutes_likely": 24.235, "rip_by_circular_saw_beginner_man_hours_low": 0.514,
               "rip_by_circular_saw_beginner_man_hours_high": 3.252, "rip_by_circular_saw_most_people": 4.0, "rip_by_beam_saw_man_hours_low": 0.162,
               "rip_by_beam_saw_man_hours_likely": 0.328, "rip_by_beam_saw_man_hours_high": 0.667, "rip_by_beam_saw_elapsed_minutes_likely": 15.035,
               "rip_by_beam_saw_beginner_man_hours_low": 0.324, "rip_by_beam_saw_beginner_man_hours_high": 2.002, "rip_by_beam_saw_most_people": 4.0}
LOWER_BAND = "glazing@610,2495,1219"
UPPER_BAND = "glazing@610,2495,2438"
NORTH_DOOR = "door@610,4819"
HEADER_COUNTS = {"headers": 3, "headers_over_one": 0, "utilisation_max": 0.407}
HEADER_FIGURES = {f"{LOWER_BAND} load_n_per_mm": 0.0, f"{LOWER_BAND} utilisation": 0.0, f"{UPPER_BAND} load_n_per_mm": 11.732,
                  f"{UPPER_BAND} utilisation": 0.407, f"{NORTH_DOOR} load_n_per_mm": 1.402, f"{NORTH_DOOR} utilisation": 0.024,
                  f"{LOWER_BAND} unsupported_load_n_per_mm": None, f"{NORTH_DOOR} unsupported_load_n_per_mm": None,
                  f"{UPPER_BAND} self_weight_n": 434.075, f"{NORTH_DOOR} self_weight_n": 217.038}
DOOR_RANKS = {"door-steel-6-panel-prehung-walker": (1, 13886.612, 2332.287, []), "door-jeldwen-steel": (2, None, None, ["door@610,4819"]),
              "door-masonite-steel": (2, None, None, ["door@610,4819"]), "door-thermatru-smooth-star": (4, 14211.387, 2338.045, [])}
WINDOW_WALL_LAYOUTS = {"two-stacked-4x8": (2, 1), "one-8x8": (1, 1), "four-4x4": (2, 2)}
WINDOW_WALL_OUTCOMES = {"two-stacked-4x8": (14211.387, [], 62.933), "one-8x8": (13244.387, ["glazing@610,2495,1219"], 57.933),
                        "four-4x4": (15116.387, [], 72.933)}
CONTAINER_USES = ["floor=container-floor", "walls=container-walls", "roof=container-roof", "foundation=piers-at-corners", "build_sequence=container-on-piers"]
ENCLOSURE_USES = {"sip": [], "container": CONTAINER_USES, "container-high-cube": CONTAINER_USES + ["container_stock=container-20-high-cube-new"]}
OPENING_FRAMING_FLOWS = {"sip": ["cut-openings"], "container": ["cut-container-openings", "frame-container-openings"],
                         "container-high-cube": ["cut-container-openings", "frame-container-openings"]}
ENCLOSURE_OUTCOMES = {"sip": (14211.387, [], 62.933, {"cut-openings": None}, "pass"),
                      "container": (21569.413, [], 100.999, {"cut-container-openings": 5399.114, "frame-container-openings": 750.0}, "fail"),
                      "container-high-cube": (24828.571, [], 101.532, {"cut-container-openings": 5399.114, "frame-container-openings": 750.0}, "fail")}
SIP_SPAN_VALUES = {'panels': 1, 'panels_over_one': 1, 'bending_utilisation': 0.899, 'shear_utilisation': 7.32, 'deflection_utilisation': 5.531, 'bearing_utilisation': 2.423, 'panel_utilisation': 7.32, 'beam_utilisation': None, 'span_mm': 2298.0, 'load_psf': 96.657, 'beams': 0, 'beam_board_feet': 0.0, 'posts_under_floor': 4, 'floor_panel_allowable_psf_8ft': 32.458, 'roof_panel_allowable_psf_8ft': 67.445, 'floor_panel_allowable_psf_10ft': 23.822, 'roof_panel_allowable_psf_10ft': 51.347, 'floor_panel_allowable_psf_12ft': 18.031, 'roof_panel_allowable_psf_12ft': 40.401}
FLOOR_SUPPORTS = ("posts-under-corners", "beams-east-west-on-two-posts", "beams-east-west-on-three-posts", "beams-north-south-on-two-posts",
                  "beams-north-south-on-three-posts", "three-beams-east-west-on-three-posts", "three-beams-north-south-on-three-posts")
FLOOR_VARIANTS = {"8x8": {}, "8x12": {"depth_mm": 3658}, "8x8 at 210 mm": {"thickness_mm": 210}}
SPAN_CHECKS = ("bending_utilisation", "shear_utilisation", "deflection_utilisation", "bearing_utilisation", "beam_utilisation")
FLOOR_SUPPORT_OUTCOMES = {
    '8x8 posts-under-corners': ('fail', 0.899, 7.32, 5.531, 2.423, None),
    '8x8 beams-east-west-on-two-posts': ('fail', 0.744, 1.071, 2.246, 0.527, 0.92),
    '8x8 beams-east-west-on-three-posts': ('fail', 0.744, 1.071, 2.246, 0.527, 0.305),
    '8x8 beams-north-south-on-two-posts': ('fail', 0.533, 0.767, 1.608, 0.511, 0.893),
    '8x8 beams-north-south-on-three-posts': ('fail', 0.533, 0.767, 1.608, 0.511, 0.296),
    '8x8 three-beams-east-west-on-three-posts': ('pass', 0.186, 0.433, 0.995, 0.388, 0.226),
    '8x8 three-beams-north-south-on-three-posts': ('pass', 0.133, 0.31, 0.713, 0.372, 0.217),
    '8x12 posts-under-corners': ('fail', 1.985, 10.346, 6.467, 3.425, None),
    '8x12 beams-east-west-on-two-posts': ('fail', 1.746, 1.765, 4.16, 0.738, 1.284),
    '8x12 beams-east-west-on-three-posts': ('fail', 1.746, 1.765, 4.16, 0.738, 0.425),
    '8x12 beams-north-south-on-two-posts': ('fail', 0.463, 0.667, 1.398, 0.482, 1.974),
    '8x12 beams-north-south-on-three-posts': ('fail', 0.463, 0.667, 1.398, 0.482, 0.493),
    '8x12 three-beams-east-west-on-three-posts': ('fail', 0.437, 0.778, 1.624, 0.6, 0.347),
    '8x12 three-beams-north-south-on-three-posts': ('pass', 0.116, 0.269, 0.619, 0.361, 0.371),
    '8x8 at 210 mm posts-under-corners': ('fail', 0.458, 5.602, 2.746, 2.494, None),
    '8x8 at 210 mm beams-east-west-on-two-posts': ('fail', 0.383, 0.746, 1.12, 0.542, 0.946),
    '8x8 at 210 mm beams-east-west-on-three-posts': ('fail', 0.383, 0.746, 1.12, 0.542, 0.313),
    '8x8 at 210 mm beams-north-south-on-two-posts': ('pass', 0.278, 0.542, 0.813, 0.526, 0.919),
    '8x8 at 210 mm beams-north-south-on-three-posts': ('pass', 0.278, 0.542, 0.813, 0.526, 0.304),
    '8x8 at 210 mm three-beams-east-west-on-three-posts': ('pass', 0.096, 0.254, 0.524, 0.403, 0.234),
    '8x8 at 210 mm three-beams-north-south-on-three-posts': ('pass', 0.069, 0.184, 0.381, 0.38, 0.221),
}
UNLAYERED_PIECES = ["door@610,4819", "glazing@610,2495,1219", "glazing@610,2495,2438"]


def floor_variant(world: Path, name: str) -> Path:
    variant = json.loads(world.read_text(encoding="utf-8"))
    variant["systems"]["floor"]["settings"].update(FLOOR_VARIANTS[name])
    path = world.with_name(f"world.floor-{name.replace(' ', '-')}.json")
    path.write_text(json.dumps(variant), encoding="utf-8")
    return path


def floor_support_outcome(launcher: Path, world: Path, support: str) -> tuple:
    flags = ("--use", f"floor_support={support}")
    values = solver_values(run_engine(launcher, "solve", world, *flags)[1], "sip-span-check")
    rule = {rule["id"]: rule["status"] for rule in run_engine(launcher, "evaluate", world, *flags)[1].get("rules", [])}.get("sip-panels-within-capacity")
    return (rule, *rounded({name: values.get(name) for name in SPAN_CHECKS}).values())


def floor_support_lines(launcher: Path, world: Path) -> list[str]:
    outcomes = {}
    for name in FLOOR_VARIANTS:
        variant = floor_variant(world, name)
        outcomes.update({f"{name} {support}": floor_support_outcome(launcher, variant, support) for support in FLOOR_SUPPORTS})
    return [state_line("we solve and evaluate each floor support on the 8x8, the 8x12 and the 8x8 laid 210 mm thick: the rule, then bending, shear, deflection, bearing and beam utilisation",
                       FLOOR_SUPPORT_OUTCOMES, outcomes)]


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


def run_engine(launcher: Path, command: str, world: Path, *flags: str) -> tuple[int, dict]:
    finished = subprocess.run([str(launcher), command, str(world), *flags], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", env=ENGINE_ENV)
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
    return {key: round(number, DECIMALS) if isinstance(number, float) else number for key, number in values.items()}


def build_totals(simulated: dict) -> dict:
    stocks = simulated.get("final_stocks", {})
    return rounded_figures({"labour_hours": simulated.get("objective_total", {}).get("labour_hours"), "cost_usd": stocks.get("cost_usd"), "budget_usd": stocks.get("budget_usd")})


def door_rank_line(launcher: Path, world: Path) -> str:
    finished = subprocess.run([str(launcher), "rank", str(world), "--system", "door_slab"], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", env=ENGINE_ENV)
    ranked = json.loads(finished.stdout).get("ranked", []) if finished.stdout.strip() else []
    observed = {entry["solution"]: (entry["rank"], *rounded_figures({name: figure["value"] for name, figure in entry["figures"].items()}).values(),
                                    entry["figures"]["final_stocks.cost_usd"].get("incomplete", [])) for entry in ranked}
    return state_line("we rank the door options on cost and design-day loss: rank, cost, loss, pieces unpriced", DOOR_RANKS, observed)


def layout_variant(world: Path, name: str) -> Path:
    variant = json.loads(world.read_text(encoding="utf-8"))
    rows, columns = WINDOW_WALL_LAYOUTS[name]
    variant["systems"]["glazing"]["settings"].update({"rows": rows, "columns": columns})
    path = world.with_name(f"world.{name}.json")
    path.write_text(json.dumps(variant), encoding="utf-8")
    return path


def layout_outcome(simulated: dict) -> tuple:
    return (rounded_figures(simulated.get("final_stocks", {})).get("cost_usd"), simulated.get("final_stocks_incomplete", {}).get("cost_usd", []),
            rounded_figures(simulated.get("objective_total", {})).get("labour_hours"))


def layout_lines(launcher: Path, world: Path) -> list[str]:
    outcomes = {name: layout_outcome(run_engine(launcher, "simulate", layout_variant(world, name))[1]) for name in WINDOW_WALL_LAYOUTS}
    return [state_line("we simulate each window-wall layout: cost, the pieces it has no price for, labour hours", WINDOW_WALL_OUTCOMES, outcomes)]


def enclosure_outcome(launcher: Path, world: Path, enclosure: str) -> tuple:
    flags = [flag for use in ENCLOSURE_USES[enclosure] for flag in ("--use", use)]
    simulated = run_engine(launcher, "simulate", world, *flags)[1]
    rules = {rule["id"]: rule["status"] for rule in run_engine(launcher, "evaluate", world, *flags)[1].get("rules", [])}
    framing = {flow: rounded_figures(simulated.get("totals", {}).get(flow, {}).get("moved", {})).get("cost_usd") for flow in OPENING_FRAMING_FLOWS[enclosure]}
    return (*layout_outcome(simulated), framing, rules.get("container-as-dwelling"))


def enclosure_lines(launcher: Path, world: Path) -> list[str]:
    outcomes = {enclosure: enclosure_outcome(launcher, world, enclosure) for enclosure in ENCLOSURE_USES}
    return [state_line("we simulate the SIP, used 20 ft and new high-cube container enclosures: cost, pieces unpriced, labour hours, the openings' framing cost, the zoning rule",
                       ENCLOSURE_OUTCOMES, outcomes)]


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
    small_target["optimizing"]["targets"]["cost_usd"]["at_most"] = SMALL_TARGET_USD
    variant = world.with_name("world.small-target.json")
    variant.write_text(json.dumps(small_target), encoding="utf-8")
    _, simulated = run_engine(launcher, "simulate", variant)
    return [state_line(f"we simulate with a ${SMALL_TARGET_USD} target: every task still runs, and budget_usd goes below zero by the overrun, which objective_total names and scores",
                       (TASK_RUNS, OVERRUN_BUDGET_USD, OVERRUN_COST_USD),
                       ({flow: total.get("runs") for flow, total in simulated.get("totals", {}).items()}, rounded_figures(simulated.get("final_stocks", {})).get("budget_usd"),
                        rounded_figures(simulated.get("objective_total", {})).get("overrun.cost_usd")))]


def run_sample(launcher: Path, world: Path, arguments: list[str]) -> tuple[int, dict]:
    finished = subprocess.run([str(launcher), "sample", str(world), *arguments], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", env=ENGINE_ENV)
    return finished.returncode, json.loads(finished.stdout) if finished.stdout.strip() else {}


def incomplete_outputs(answer: dict) -> dict:
    return {output: statistics["incomplete"] for output, statistics in answer.get("outputs", {}).items() if "incomplete" in statistics}


def sample_lines(launcher: Path, world: Path) -> list[str]:
    refused_exit, refused = run_sample(launcher, layout_variant(world, "one-8x8"), COST_BELOW_ARGUMENTS)
    _, answer = run_sample(launcher, world, SAMPLE_ARGUMENTS)
    return [state_line("we sample on one-8x8 refuses the share of runs under $20,000, naming the window with no listed price", (1, COST_BELOW_REFUSAL), (refused_exit, refused.get("refused"))),
            state_line("we sample 50 runs at seed 1: failures, quality tally, share under $20,000 and under the deterministic labour hours, and both",
                       SAMPLE_ANSWER, {key: answer.get(key) for key in SAMPLE_ANSWER}),
            state_line("we sample outputs marked incomplete", {}, incomplete_outputs(answer))]


def not_applicable_flows(simulated: dict) -> dict:
    flows = simulated.get("steps", [{}])[0].get("flows", {})
    return {flow: record["not_applicable"] for flow, record in flows.items() if "not_applicable" in record}


def simulate_lines(launcher: Path, world: Path) -> list[str]:
    simulate_exit, simulated = run_engine(launcher, "simulate", world)
    totals = simulated.get("totals", {})
    return [
        state_line("we simulate exit, end and the minute each piece is placed", (0, "quiescent", PLACED_AT_MINUTE),
                   (simulate_exit, simulated.get("ended"), simulated.get("placed_at"))),
        state_line("we simulate labour hours, cost and budget left, each a partial sum where incomplete", BUILD_TOTALS, build_totals(simulated)),
        state_line("we simulate stocks incomplete, with the pieces that have no price", INCOMPLETE_STOCKS, simulated.get("final_stocks_incomplete", {})),
        state_line("we simulate the skill each person ends with", SKILLS_FINAL, simulated.get("skills_final")),
        state_line("we simulate runs of every task, none skipped", TASK_RUNS, {flow: total.get("runs") for flow, total in totals.items()}),
        state_line("we simulate flows of a greenhouse the world lacks are not applicable, with the role missing", NOT_APPLICABLE_FLOWS, not_applicable_flows(simulated)),
        state_line("we simulate pieces whose placed_at step has no flow placing them there", [], pieces_placed_by_no_flow(simulated)),
    ]


def percentiles_of(answer: dict) -> dict:
    return {output: rounded({name: answer.get("outputs", {}).get(output, {}).get(name) for name in names}) for output, names in FULL_SAMPLE_PERCENTILES.items()}


def full_sample_lines(answer: dict) -> list[str]:
    return [state_line("we sample 500 runs at seed 1: failures, quality tally, share under $20,000 and under the deterministic labour hours, and both",
                       FULL_SAMPLE_ANSWER, {key: answer.get(key) for key in FULL_SAMPLE_ANSWER}),
            state_line("we sample 500 runs: median and 95th percentile of cost and labour hours", FULL_SAMPLE_PERCENTILES, percentiles_of(answer)),
            state_line("we sample 500 runs: outputs marked incomplete", {}, incomplete_outputs(answer))]


def engine_lines(launcher: Path, world: Path, is_sampling: bool, is_sampling_fully: bool) -> list[str]:
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
        state_line("we evaluate rules", {"egress-door-size": "pass", "posts-below-frost-line": "pass", "roof-covers-floor": "pass", "posts-under-floor": "pass", "walls-enclose-floor": "pass", "roof-is-over-floor": "pass", "joists-span-the-deck": "pass", "headers-within-capacity": "pass", "container-as-dwelling": "pass", "skirt-meets-frost-protected-footing-table": "not_applicable", "sip-panels-within-capacity": "fail"}, rule_statuses(launcher, world)),
        state_line("we solve joist deflection and stress", {"deflection_mm": 2.88, "span_over_deflection": 767.494, "bending_stress_mpa": 3.824}, rounded(solver_values(solved, "joist-deflection"))),
        state_line("we solve design day BTU per hour", {"loss_btu_per_hour": DESIGN_DAY_LOSS_BTU_PER_HOUR, "solar_gain_btu_per_hour": DESIGN_DAY_SOLAR_BTU_PER_HOUR},
                   rounded(solver_values(solved, "design-day-load"))),
        state_line("we solve heating season BTU and cords", SEASON, rounded(solver_values(solved, "heating-season"))),
        state_line("we solve gravity load path status, piece counts and the ground reaction", ("known", LOAD_PATH_COUNTS),
                   (solver_answer(solved, "gravity-load-path").get("status"), rounded(solver_values(solved, "gravity-load-path")))),
        state_line("we solve gravity load path newtons on the floor, the loft, the wall panels less their openings, a joist, a ledger, the roof, the door and a window",
                   KNOWN_PIECE_NEWTONS, rounded_figures(piece_figures(solved, "gravity-load-path", list(KNOWN_PIECE_NEWTONS)))),
        state_line("we solve gravity load path reaction under each of the four posts", {f"{post} reaction_n": POST_REACTION_N for post in POSTS},
                   rounded_figures(piece_figures(solved, "gravity-load-path", [f"{post} reaction_n" for post in POSTS]))),
        state_line("we solve build task hours at published rates and the panel blanks' price", WORK_AT_PUBLISHED_RATES,
                   rounded_figures({name: value for name, value in solver_values(solved, "work-at-published-rates").items() if name in WORK_AT_PUBLISHED_RATES})),
        state_line("we solve each rip method's man-hours low, likely and high, a beginner's, its largest crew and the blank's and piece's weight", ("known", RIP_METHODS),
                   (solver_answer(solved, "task-methods").get("status"), rounded(solver_values(solved, "task-methods")))),
        state_line("we solve header check counts and the largest utilisation", ("known", HEADER_COUNTS),
                   (solver_answer(solved, "header-check").get("status"), rounded(solver_values(solved, "header-check")))),
        state_line("we solve header load and utilisation over the two south bands and the north door", HEADER_FIGURES,
                   rounded_figures(piece_figures(solved, "header-check", list(HEADER_FIGURES)))),
        state_line("we solve the SIP floor panel on its four corner posts: utilisations, span, load, beams, posts and the allowable loads at 8, 10 and 12 ft",
                   ("known", SIP_SPAN_VALUES), (solver_answer(solved, "sip-span-check").get("status"), rounded(solver_values(solved, "sip-span-check")))),
        door_rank_line(launcher, world),
    ] + floor_support_lines(launcher, world) + layout_lines(launcher, world) + enclosure_lines(launcher, world) + geometry_lines(launcher, world) + simulate_lines(launcher, world) + target_lines(launcher, world) + (sample_lines(launcher, world) if is_sampling else []) + (full_sample_lines(run_sample(launcher, world, FULL_SAMPLE_ARGUMENTS)[1]) if is_sampling_fully else [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plant", choices=sorted(PLANTS), help="run on a copy carrying this defect; the check must exit 1")
    parser.add_argument("--sample", action="store_true", help="also run the refusal and the seeded 50-run sample (about 11 minutes)")
    parser.add_argument("--sample-full", action="store_true", help="also run the seeded 500-run sample (about 110 minutes)")
    options = parser.parse_args()
    engine = locate_engine()
    try:
        launcher = require_engine(engine)
        world = read_world()
        if options.plant:
            PLANTS[options.plant](world)
        with tempfile.TemporaryDirectory() as scratch:
            lines = pin_lines(world)
            lines += engine_lines(launcher, write_world_copy(copy.deepcopy(world), Path(scratch)), options.sample, options.sample_full)
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
