"""Check the small-house world, Jim's pencil sketch as plain data, against figures stated by hand in this file and never read from the engine.

The Kotlin engine at ../world-engine (or WORLD_ENGINE_DIR), which must contain engine.pin, loads this directory through `we run` and replays
its seed; the check compares the object counts, the type footprints in tiles, the overhang as roof minus floor, every equation against its
hand calculation, that no figure the sketch does not give was invented, that the engine still refuses the three things this world waits on
(a null field, a square floor on four corner posts, a roof past its walls), and the world's embedded cases through `we judge --embedded`.
One line a check, '<what>: <expected> against <observed>: agrees' or 'differs', then '<n> of <m> small house checks agree'.
--plant roof-smaller-than-floor runs the same checks on a scratch copy whose roof is 6 by 6 ft, and must exit 1.
Usage: python check.py [--plant roof-smaller-than-floor]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WORLD = Path(__file__).resolve().parent
WORLD_NAME = "small-house"
PART_FILES = ("world.json", "types.json", "equations.json", "rules.json", "people.json", "placements.json", "cases.json")
EXIT_REFUSED_ENGINE = 2

MM_PER_FOOT = 304.8
CUBIC_MM_PER_BOARD_FOOT = 144 * 25.4 ** 3
CUBIC_MM_PER_CUBIC_METRE = 1e9
SQUARE_MM_PER_SQUARE_METRE = 1e6
RELATIVE_TOLERANCE = 1e-9
PLANTED_ROOF_FT = 6

SKETCH_FT = {"floor": 8, "roof_width": 12, "roof_depth": 18, "wall_height": 12, "eave": 2, "embedment": 4, "board_feet": 630}
EXPECTED_COUNTS = {"post": 4, "floor": 0, "wall": 0, "roof": 0, "glazing": 0}
EXPECTED_FOOTPRINTS = {"post": [1, 1], "floor": [8, 8], "wall": [8, 1], "roof": [12, 18], "glazing": [8, 1]}
EXPECTED_OVERHANG_TILES = [4, 10]
EXPECTED_FIELDS = {
    "post": {"embedment_mm"},
    "floor": {"width_mm", "depth_mm"},
    "wall": {"length_mm", "height_mm"},
    "roof": {"width_mm", "depth_mm", "west_eave_mm", "north_eave_mm"},
    "glazing": {"width_mm"},
}
EXPECTED_CASES = 2
NULL_FIELD_REFUSAL_TEXT = "expected number/string"


class EngineRefused(Exception):
    pass


def read_engine_pin() -> str:
    return (WORLD / "engine.pin").read_text(encoding="utf-8").strip()


def locate_engine() -> Path:
    return Path(os.environ.get("WORLD_ENGINE_DIR") or WORLD.parent / "world-engine").resolve()


def find_launcher(engine: Path) -> Path:
    return engine / "kotlin" / ("we.cmd" if os.name == "nt" else "we")


def has_commit(engine: Path, pin: str) -> bool:
    ancestry = subprocess.run(["git", "-C", str(engine), "merge-base", "--is-ancestor", pin, "HEAD"], capture_output=True)
    return ancestry.returncode == 0


def require_engine(engine: Path, pin: str) -> Path:
    launcher = find_launcher(engine)
    if not launcher.is_file():
        raise EngineRefused(f"no Kotlin launcher at {launcher}; set WORLD_ENGINE_DIR to a world-engine checkout")
    if not has_commit(engine, pin):
        raise EngineRefused(f"the engine at {engine} does not contain engine.pin {pin}")
    return launcher


def run_engine(launcher: Path, arguments: list[str]) -> str:
    finished = subprocess.run([str(launcher), *arguments], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    if not finished.stdout.strip():
        raise EngineRefused(f"`we {' '.join(arguments)}` answered nothing (exit {finished.returncode}): {finished.stderr.strip()}")
    return finished.stdout


def ask_world(launcher: Path, directory: Path, steps: list[dict]) -> dict:
    with tempfile.TemporaryDirectory() as request_directory:
        request_file = Path(request_directory) / "request.json"
        request_file.write_text(json.dumps({"world": str(directory), "steps": steps}), encoding="utf-8")
        return json.loads(run_engine(launcher, ["run", str(request_file)]))


def to_whole_mm(feet: float) -> int:
    return round(feet * MM_PER_FOOT)


def work_equations_by_hand() -> dict[str, float]:
    floor, eave = to_whole_mm(SKETCH_FT["floor"]), to_whole_mm(SKETCH_FT["eave"])
    roof_width, roof_depth = to_whole_mm(SKETCH_FT["roof_width"]), to_whole_mm(SKETCH_FT["roof_depth"])
    sketch_volume = SKETCH_FT["board_feet"] * CUBIC_MM_PER_BOARD_FOOT
    return {
        "floor_area": floor * floor / SQUARE_MM_PER_SQUARE_METRE,
        "roof_area": roof_width * roof_depth / SQUARE_MM_PER_SQUARE_METRE,
        "roof_overhang_width_mm": roof_width - floor,
        "roof_overhang_depth_mm": roof_depth - floor,
        "roof_east_eave_mm": roof_width - eave - floor,
        "roof_south_hangover_mm": roof_depth - eave - floor,
        "sketch_board_feet": SKETCH_FT["board_feet"],
        "board_foot_volume": CUBIC_MM_PER_BOARD_FOOT / CUBIC_MM_PER_CUBIC_METRE,
        "sketch_board_feet_volume": sketch_volume / CUBIC_MM_PER_CUBIC_METRE,
        "reading_section_total_at_wall_height": sketch_volume / to_whole_mm(SKETCH_FT["wall_height"]) / SQUARE_MM_PER_SQUARE_METRE,
    }


def judge(expected, observed) -> str:
    if isinstance(expected, (int, float)) and isinstance(observed, (int, float)):
        is_equal = abs(expected - observed) <= RELATIVE_TOLERANCE * max(abs(expected), 1.0)
    else:
        is_equal = expected == observed
    return "agrees" if is_equal else "differs"


def state_line(what: str, expected, observed) -> str:
    return f"{what}: {expected} against {observed}: {judge(expected, observed)}"


def copy_world(destination: Path) -> Path:
    target = destination / WORLD_NAME
    target.mkdir(parents=True)
    for part in PART_FILES:
        shutil.copy2(WORLD / part, target / part)
    return target


def read_part(directory: Path, name: str) -> dict:
    return json.loads((directory / name).read_text(encoding="utf-8"))


def write_part(directory: Path, name: str, document: dict) -> None:
    (directory / name).write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")


def find_type(types: dict, type_id: str) -> dict:
    return next(item for item in types["object_types"] if item["id"] == type_id)


def set_property_default(object_type: dict, name: str, value) -> None:
    next(item for item in object_type["properties"] if item["name"] == name)["default"] = value


def plant_small_roof(directory: Path) -> None:
    types = read_part(directory, "types.json")
    roof = find_type(types, "roof")
    roof["footprint"] = [PLANTED_ROOF_FT, PLANTED_ROOF_FT]
    set_property_default(roof, "width_mm", to_whole_mm(PLANTED_ROOF_FT))
    set_property_default(roof, "depth_mm", to_whole_mm(PLANTED_ROOF_FT))
    write_part(directory, "types.json", types)


def add_null_field(directory: Path) -> None:
    types = read_part(directory, "types.json")
    find_type(types, "post")["properties"].append({"name": "above_grade_mm", "unit": "mm", "default": None, "kind": "design"})
    write_part(directory, "types.json", types)


def stand_walls_on_the_ground(directory: Path) -> None:
    types = read_part(directory, "types.json")
    types["object_types"].append({"id": "wall_ns", "extends": "wall", "footprint": [1, 6]})
    write_part(directory, "types.json", types)
    write_part(directory, "placements.json", {"seed": []})


def describe_refusal(answer: dict) -> str | None:
    refused = answer.get("refused")
    return f"refused by {refused['rule']}: {refused['message']}" if refused else None


def describe_load_refusal(launcher: Path, directory: Path) -> str:
    refused = ask_world(launcher, directory, []).get("refused")
    if refused is None:
        return "loads"
    return "refused" if NULL_FIELD_REFUSAL_TEXT in refused["message"] else f"refused otherwise: {refused['message']}"


def to_attempt(index: int, placement: tuple) -> dict:
    type_id, col, row, stack_level = placement
    return {"attempt": {"branch": "main", "actor": "jim", "action": "place", "at": f"2026-10-15T00:00:{index:02d}Z",
                        "args": {"type": type_id, "col": col, "row": row, "stack_level": stack_level}}}


def place_in_order(launcher: Path, directory: Path, placements: list[tuple]) -> str:
    answer = ask_world(launcher, directory, [to_attempt(index, placement) for index, placement in enumerate(placements)])
    if "refused" in answer:
        return f"world {describe_refusal(answer)}"
    for (type_id, *_), result in zip(placements, answer["results"]):
        if "refused" in result:
            return f"{type_id} refused by {result['refused']['rule']}"
    return "every placement applied"


def check_counts(outputs: dict) -> list[str]:
    return [state_line(f"placed {type_id}", expected, outputs["counts"].get(type_id)) for type_id, expected in EXPECTED_COUNTS.items()]


def check_equations(outputs: dict) -> list[str]:
    observed = outputs["equations"]
    return [state_line(f"equation {name}", expected, observed.get(name)) for name, expected in work_equations_by_hand().items()]


def check_rules(outputs: dict) -> list[str]:
    return [state_line("rules broken by the placed house", [], outputs.get("violations"))]


def read_types(directory: Path) -> dict:
    return {item["id"]: item for item in read_part(directory, "types.json")["object_types"]}


def check_footprints(types: dict) -> list[str]:
    lines = [state_line(f"{type_id} footprint in tiles", expected, types[type_id].get("footprint"))
             for type_id, expected in EXPECTED_FOOTPRINTS.items()]
    roof, floor = types["roof"]["footprint"], types["floor"]["footprint"]
    return lines + [state_line("overhang in tiles, roof minus floor", EXPECTED_OVERHANG_TILES, [roof[0] - floor[0], roof[1] - floor[1]])]


def check_nothing_invented(types: dict) -> list[str]:
    lines = [state_line("post height_mm, the sketch's '?' above grade", None, types["post"].get("height_mm"))]
    for type_id, expected in EXPECTED_FIELDS.items():
        properties = types[type_id].get("properties", [])
        lines.append(state_line(f"{type_id} fields", sorted(expected), sorted(item["name"] for item in properties)))
        unsourced = [item["name"] for item in properties if not item.get("source", {}).get("reason")]
        lines.append(state_line(f"{type_id} fields with no source reason", [], unsourced))
    return lines


def judge_embedded_cases(launcher: Path, worlds: Path) -> dict:
    answer = run_engine(launcher, ["judge", "--embedded", str(worlds), "--json"])
    return json.loads(answer.strip().splitlines()[-1])


def check_embedded_cases(launcher: Path, directory: Path, scratch: Path) -> list[str]:
    worlds = scratch / "worlds"
    shutil.copytree(directory, worlds / WORLD_NAME)
    verdicts = {case_id: problems for case_id, problems in judge_embedded_cases(launcher, worlds).items() if case_id.startswith(f"{WORLD_NAME}-")}
    failing = [case_id for case_id, problems in verdicts.items() if problems]
    return [state_line("embedded cases", EXPECTED_CASES, len(verdicts)), state_line("embedded cases failing", [], failing)]


def check_world(launcher: Path, directory: Path, scratch: Path) -> list[str]:
    answer = ask_world(launcher, directory, [{"outputs": {}}])
    refusal = describe_refusal(answer)
    lines = [state_line("placing the seed", "no refusal", refusal or "no refusal")]
    if refusal is None:
        outputs = answer["results"][0]
        lines += check_counts(outputs) + check_equations(outputs) + check_rules(outputs)
    types = read_types(directory)
    return lines + check_footprints(types) + check_nothing_invented(types) + check_embedded_cases(launcher, directory, scratch / "cases")


def check_engine_stops(launcher: Path, scratch: Path) -> list[str]:
    null_copy = copy_world(scratch / "null-field")
    add_null_field(null_copy)
    wall_copy = copy_world(scratch / "walls-on-the-ground")
    stand_walls_on_the_ground(wall_copy)
    walls = [("wall", 2, 2, 0), ("wall", 2, 9, 0), ("wall_ns", 2, 3, 0), ("wall_ns", 9, 3, 0), ("roof", 0, 0, 1)]
    return [
        state_line("engine still refuses a null field default (request A)", "refused", describe_load_refusal(launcher, null_copy)),
        state_line("engine still refuses the floor on four corner posts (request B)", "floor refused by bears-on",
                   place_in_order(launcher, WORLD, [("floor", 2, 2, 1)])),
        state_line("engine still refuses the roof past its walls (request B)", "roof refused by bears-on",
                   place_in_order(launcher, wall_copy, walls)),
    ]


def run_checks(launcher: Path, plant: str | None) -> list[str]:
    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = Path(scratch_name)
        directory = WORLD
        if plant:
            directory = copy_world(scratch / "planted")
            plant_small_roof(directory)
        return check_world(launcher, directory, scratch) + check_engine_stops(launcher, scratch)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plant", choices=["roof-smaller-than-floor"], help="run on a copy carrying this defect; the check must exit 1")
    options = parser.parse_args()
    pin, engine = read_engine_pin(), locate_engine()
    try:
        launcher = require_engine(engine, pin)
        lines = run_checks(launcher, options.plant)
    except EngineRefused as refusal:
        print(f"refused: {refusal}")
        return EXIT_REFUSED_ENGINE
    print(f"engine {engine} contains engine.pin {pin}")
    for line in lines:
        print(line)
    agreed = sum(line.endswith(": agrees") for line in lines)
    print(f"{agreed} of {len(lines)} small house checks agree")
    return 0 if agreed == len(lines) else 1


if __name__ == "__main__":
    sys.exit(main())
