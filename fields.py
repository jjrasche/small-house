"""Print every field the engine returns for a world config: what `we expand` places, what `we geometry` says each piece is made of, what each solver in `we solve` says, each rule `we evaluate`
judges, the roof snow load and each post's reaction with and without it, and what `we simulate` answers over the clock (when each piece is placed, the stocks, hours and skills at the end and each stock's unknown contributors, each task's runs), how each option of a ranked system scores on the config's ranking weights, and, for the SIP and the shipping-container enclosure side by side (`--use`, never an edit of the config), first cost, labour hours, each face's R, the openings' framing and the zoning rule.

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
ENGINE_ENV = {**os.environ, "JAVA_TOOL_OPTIONS": os.environ.get("JAVA_TOOL_OPTIONS", "-XX:MaxRAMPercentage=75")}
RANKED_SYSTEMS = ("door_slab",)
WINDOW_WALL_LAYOUTS = {"two-stacked-4x8": (2, 1), "one-8x8": (1, 1), "four-4x4": (2, 2)}
ENCLOSURES = {"sip": (), "container": ("floor=container-floor", "walls=container-walls", "roof=container-roof", "foundation=piers-at-corners",
                                       "build_sequence=container-on-piers")}
ENCLOSURES["container-high-cube"] = ENCLOSURES["container"] + ("container_stock=container-20-high-cube-new",)
CONTAINER_FRAMING = {"cut-container-openings": "cut_container_openings_hours", "frame-container-openings": "frame_container_openings_hours"}
OPENING_FRAMING = {"sip": {"cut-openings": "cut_openings_hours"}, "container": CONTAINER_FRAMING, "container-high-cube": CONTAINER_FRAMING}
FLOOR_SUPPORTS = ("posts-under-corners", "beams-east-west-on-two-posts", "beams-east-west-on-three-posts", "beams-north-south-on-two-posts",
                  "beams-north-south-on-three-posts", "three-beams-east-west-on-three-posts", "three-beams-north-south-on-three-posts")
FLOORS = {"8x8": None, "8x12": 3658}
SPAN_CHECKS = ("bending_utilisation", "shear_utilisation", "deflection_utilisation", "bearing_utilisation", "beam_utilisation")
CONVENTIONAL_FLOOR_MM = 210
FLOOR_THICKNESSES = (None, CONVENTIONAL_FLOOR_MM)
THINNER_FLOORS_MM = (165, 114)
ENVELOPE_R = ("walls_r", "roof_r", "floor_r", "walls_foam_in", "roof_foam_in", "floor_foam_in", "thermal_bridging")


def run_engine(command: str, config: Path, *flags: str) -> dict:
    finished = subprocess.run(["sh", str(ENGINE / "kotlin" / "we"), command, str(config), *flags], capture_output=True, text=True, stdin=subprocess.DEVNULL, env=ENGINE_ENV)
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


def print_roof_snow(solved: dict) -> None:
    path = next((solver for solver in solved["solvers"] if solver["function"] == "gravity-load-path"), None)
    if path is None:
        print("roof snow: the pinned domains have no gravity-load-path solver")
        return
    values = path["values"]
    print(f"roof snow load {path['status']} roof_snow_psf={values.get('roof_snow_psf')} roof_snow_n={values.get('roof_snow_n')} "
          f"ground_reaction_n={values.get('ground_reaction_n')} ground_reaction_without_snow_n={values.get('ground_reaction_without_snow_n')}")
    for piece, figures in path.get("objects", {}).items():
        if figures.get("reaction_n") is not None:
            print(f"roof snow reaction {piece} with_roof_snow_n={figures['reaction_n']} without_roof_snow_n={figures.get('reaction_without_snow_n')}")


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


def use_flags(enclosure: str) -> list[str]:
    return [flag for use in ENCLOSURES[enclosure] for flag in ("--use", use)]


def print_enclosure(config: Path, enclosure: str) -> None:
    flags = use_flags(enclosure)
    simulated = run_engine("simulate", config, *flags)
    solved = {solver["function"]: solver for solver in run_engine("solve", config, *flags)["solvers"]}
    rules = {rule["id"]: rule for rule in run_engine("evaluate", config, *flags)["rules"]}
    incomplete = simulated.get("final_stocks_incomplete", {}).get("cost_usd", [])
    print(f"enclosure {enclosure} first_cost_usd={simulated['final_stocks'].get('cost_usd')} unknown=[{', '.join(incomplete)}] "
          f"labour_hours={simulated['objective_total'].get('labour_hours')}")
    envelope = solved.get("envelope-r-by-face")
    if envelope is None:
        print(f"enclosure {enclosure} envelope_r: the pinned domains have no envelope-r-by-face solver")
    else:
        print(f"enclosure {enclosure} envelope_r {envelope['status']} {envelope['detail']} " + ", ".join(f"{name}={envelope['values'].get(name)}" for name in ENVELOPE_R))
    work = solved["work-at-published-rates"]["values"]
    for flow, hours in OPENING_FRAMING[enclosure].items():
        print(f"enclosure {enclosure} openings_framing {flow} runs={simulated['totals'][flow]['runs']} cost_usd={simulated['totals'][flow]['moved'].get('cost_usd')} {hours}={work.get(hours)}")
    zoning = rules.get("container-as-dwelling", {})
    print(f"enclosure {enclosure} zoning container-as-dwelling {zoning.get('status')} {zoning.get('detail')}")


def floor_variant(config: Path, depth_mm, thickness_mm=None) -> Path:
    world = json.loads(config.read_text(encoding="utf-8"))
    if depth_mm is not None:
        world["systems"]["floor"]["settings"]["depth_mm"] = depth_mm
    if thickness_mm is not None:
        world["systems"]["floor"]["settings"]["thickness_mm"] = thickness_mm
    with tempfile.NamedTemporaryFile("w", suffix=".json", dir=config.parent, delete=False) as variant:
        json.dump(world, variant)
    return Path(variant.name)


def support_outcome(config: Path, support: str) -> dict:
    flags = ("--use", f"floor_support={support}")
    check = next(solver for solver in run_engine("solve", config, *flags)["solvers"] if solver["function"] == "sip-span-check")
    rule = next(rule for rule in run_engine("evaluate", config, *flags)["rules"] if rule["id"] == "sip-panels-within-capacity")
    simulated = run_engine("simulate", config, *flags)
    return {"values": check["values"], "status": check["status"], "detail": check["detail"], "rule": rule["status"],
            "cost_usd": simulated["final_stocks"].get("cost_usd"), "unknown": simulated.get("final_stocks_incomplete", {}).get("cost_usd", []),
            "labour_hours": simulated["objective_total"].get("labour_hours")}


def thickness_label(thickness_mm) -> str:
    return "the panel's own thickness" if thickness_mm is None else f"{thickness_mm} mm"


def support_line(label: str, support: str, outcome: dict) -> str:
    values = outcome["values"]
    checks = " ".join(f"{name.removesuffix('_utilisation')}={values.get(name)}" for name in SPAN_CHECKS)
    return (f"{label} {support} {outcome['rule']} {checks} span_mm={values.get('span_mm')} load_psf={values.get('load_psf')} beams={values.get('beams')} "
            f"beam_board_feet={values.get('beam_board_feet')} posts={values.get('posts_under_floor')} cost_usd={outcome['cost_usd']} unknown=[{', '.join(outcome['unknown'])}] "
            f"labour_hours={outcome['labour_hours']}")


def floor_support_outcomes(config: Path) -> dict:
    outcomes = {}
    for floor, depth in FLOORS.items():
        for thickness in FLOOR_THICKNESSES:
            variant = floor_variant(config, depth, thickness)
            for support in FLOOR_SUPPORTS:
                outcomes[(floor, thickness, support)] = support_outcome(variant, support)
                print(support_line(f"floor support option {floor} at {thickness_label(thickness)}", support, outcomes[(floor, thickness, support)]))
            variant.unlink()
    return outcomes


def binding_check(values: dict) -> tuple:
    measured = {name: values[name] for name in SPAN_CHECKS if values.get(name) is not None}
    name = max(measured, key=measured.get)
    return name.removesuffix("_utilisation"), measured[name]


def outcome_at(config: Path, outcomes: dict, floor: str, thickness, support: str) -> dict:
    if (floor, thickness, support) not in outcomes:
        variant = floor_variant(config, FLOORS[floor], thickness)
        outcomes[(floor, thickness, support)] = support_outcome(variant, support)
        variant.unlink()
    return outcomes[(floor, thickness, support)]


def print_take_till_it_breaks(config: Path, outcomes: dict, floor: str) -> None:
    three_posts = [support for support in FLOOR_SUPPORTS if support.startswith("beams-") and support.endswith("three-posts")]
    baseline = min(three_posts, key=lambda support: binding_check(outcomes[(floor, CONVENTIONAL_FLOOR_MM, support)]["values"])[1])
    steps = [("baseline", baseline, CONVENTIONAL_FLOOR_MM), ("less the middle posts", baseline.replace("three-posts", "two-posts"), CONVENTIONAL_FLOOR_MM),
             ("less the beams", "posts-under-corners", CONVENTIONAL_FLOOR_MM)]
    steps += [(f"thinner panel {thickness} mm", "posts-under-corners", thickness) for thickness in THINNER_FLOORS_MM]
    last_green = None
    for label, support, thickness in steps:
        outcome = outcome_at(config, outcomes, floor, thickness, support)
        print(support_line(f"take till it breaks {floor} floor {thickness} mm {label}:", support, outcome))
        if outcome["rule"] != "pass":
            check, at = binding_check(outcome["values"])
            print(f"take till it breaks {floor} first red: {label}, {check} at {at}" if last_green else f"take till it breaks {floor} baseline red: {check} at {at}; a fault, no frontier")
            break
        last_green = (label, support, thickness, outcome)
    if last_green:
        label, support, thickness, outcome = last_green
        check, at = binding_check(outcome["values"])
        print(f"take till it breaks {floor} least that stays green: {support} under a {thickness} mm floor ({label}); binding check: {check} at {at}")


def print_cost_frontier(outcomes: dict, floor: str) -> None:
    green = {(thickness, support): outcome for (each, thickness, support), outcome in outcomes.items()
             if each == floor and thickness in FLOOR_THICKNESSES and outcome["rule"] == "pass"}
    unranked = {key: outcome for key, outcome in green.items() if outcome["unknown"] or outcome["cost_usd"] is None}
    for (thickness, support), outcome in unranked.items():
        print(f"frontier {floor} not ranked: {support} at {thickness_label(thickness)} has a cost unknown in [{', '.join(outcome['unknown'])}]")
    ranked = sorted((key for key in green if key not in unranked), key=lambda key: (green[key]["cost_usd"], green[key]["labour_hours"]))
    if not ranked:
        print(f"frontier {floor}: no option stays green with every price known")
        return
    (thickness, support), *others = ranked
    best = green[(thickness, support)]
    check, at = binding_check(best["values"])
    line = (f"frontier {floor} least that stays green by cost: {support} at {thickness_label(thickness)}, cost_usd={best['cost_usd']} labour_hours={best['labour_hours']} "
            f"beam_board_feet={best['values'].get('beam_board_feet')}; binding check: {check} at {at}")
    if others:
        runner_thickness, runner_support = others[0]
        runner = green[others[0]]
        line += (f"; runner-up {runner_support} at {thickness_label(runner_thickness)}, cost_usd={runner['cost_usd']} labour_hours={runner['labour_hours']} "
                 f"beam_board_feet={runner['values'].get('beam_board_feet')}, the least less the runner-up: cost_usd={best['cost_usd'] - runner['cost_usd']:.3f} "
                 f"labour_hours={best['labour_hours'] - runner['labour_hours']:.3f}")
    print(line)


def main() -> int:
    config = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else WORLD / "world.json"
    expansion = run_engine("expand", config)
    if "refused" in expansion:
        print("refused:", expansion["refused"])
        return 1
    print_placed(expansion)
    print_materials(run_engine("geometry", config))
    solved = run_engine("solve", config)
    print_solvers(solved)
    print_roof_snow(solved)
    for rule in run_engine("evaluate", config)["rules"]:
        print(f"rule {rule['id']} ({rule['domain']}) {rule['status']} {rule['detail']}")
    if "clock" in json.loads(config.read_text(encoding="utf-8")):
        print_simulation(run_engine("simulate", config))
        print_layouts(config)
    for enclosure in ENCLOSURES:
        print_enclosure(config, enclosure)
    outcomes = floor_support_outcomes(config)
    for floor in FLOORS:
        print_take_till_it_breaks(config, outcomes, floor)
        print_cost_frontier(outcomes, floor)
    for system in RANKED_SYSTEMS:
        print_ranking(run_engine("rank", config, "--system", system))
    return 0


if __name__ == "__main__":
    sys.exit(main())
