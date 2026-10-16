"""Check the small-house world, Jim's pencil sketch as plain data, against figures stated by hand in this file and never read from the engine.

The Kotlin engine at ../world-engine (or WORLD_ENGINE_DIR), which must contain engine.pin, loads this directory through `we run` and replays
its seed: four corner posts, the floor on them, four walls, the roof over the walls. The check compares where each object stands, the tiles
each type covers, the type footprints, the overhang as roof minus floor, every equation against its hand calculation, that every figure the
sketch does not give is a null with its reason and that what is derived from one reads null, that the post's whole length and the floor's
elevation compute once a height is stated in a scratch copy, and the world's embedded cases through `we judge --embedded`.
One line a check, '<what>: <expected> against <observed>: agrees' or 'differs', then '<n> of <m> small house checks agree'.
--plant runs the same checks on a scratch copy carrying a defect, and must exit 1: roof-smaller-than-floor makes the roof 6 by 6 ft,
corner-post-removed takes the south-east post out of the seed.
Usage: python check.py [--plant roof-smaller-than-floor|corner-post-removed]
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
PART_FILES = ("world.json", "types.json", "equations.json", "rules.json", "people.json", "placements.json", "views.json", "cases.json")
EXIT_REFUSED_ENGINE = 2

MM_PER_FOOT = 304.8
CUBIC_MM_PER_BOARD_FOOT = 144 * 25.4 ** 3
CUBIC_MM_PER_CUBIC_METRE = 1e9
SQUARE_MM_PER_SQUARE_METRE = 1e6
RELATIVE_TOLERANCE = 1e-9
PLANTED_ROOF_FT = 6
PLANTED_MISSING_POST = "post-se"
SCRATCH_ABOVE_GRADE_FT = 2

SKETCH_FT = {"floor": 8, "roof_width": 12, "roof_depth": 18, "wall_height": 12, "eave": 2, "embedment": 4, "board_feet": 630}
EXPECTED_TILES = {"post": 4, "floor": 8 * 8, "wall": 2 * 8, "wall_ns": 2 * (8 - 2), "roof": 12 * 18, "glazing": 0}
EXPECTED_STACK_LEVELS = {"post-nw": 0, "post-ne": 0, "post-sw": 0, "post-se": 0, "floor": 1,
                         "wall-n": 2, "wall-s": 2, "wall-w": 2, "wall-e": 2, "roof": 3}
EXPECTED_FOOTPRINTS = {"post": [1, 1], "floor": [8, 8], "wall": [8, 1], "wall_ns": [1, 6], "roof": [12, 18], "glazing": [8, 1]}
EXPECTED_OVERHANG_TILES = [4, 10]
EXPECTED_BEARING = {"floor": ["post", "corners"], "roof": ["#wall", "any"]}
EXPECTED_FIELDS = {
    "post": {"embedment_mm", "above_grade_mm", "section_mm"},
    "floor": {"width_mm", "depth_mm", "thickness_mm"},
    "wall": {"length_mm", "height_mm", "thickness_mm"},
    "roof": {"width_mm", "depth_mm", "west_eave_mm", "north_eave_mm", "thickness_mm"},
    "glazing": {"width_mm", "glass_height_mm", "sill_height_mm"},
}
EXPECTED_NULLS = {
    "post": {"above_grade_mm", "section_mm"},
    "floor": {"thickness_mm"},
    "wall": {"thickness_mm"},
    "roof": {"thickness_mm"},
    "glazing": {"glass_height_mm", "sill_height_mm"},
}
EXPECTED_CASES = 2
POST_VIEW = "posts"


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


def work_post_length_by_hand() -> int:
    return to_whole_mm(SKETCH_FT["embedment"]) + to_whole_mm(SCRATCH_ABOVE_GRADE_FT)


def judge(expected, observed) -> str:
    if isinstance(expected, (int, float)) and isinstance(observed, (int, float)):
        is_equal = abs(expected - observed) <= RELATIVE_TOLERANCE * max(abs(expected), 1.0)
    else:
        is_equal = expected == observed
    return "agrees" if is_equal else "differs"


def state_line(what: str, expected, observed) -> str:
    return f"{what}: {expected} against {observed}: {judge(expected, observed)}"


def copy_world(destination: Path, source: Path = WORLD) -> Path:
    target = destination / WORLD_NAME
    target.mkdir(parents=True)
    for part in PART_FILES:
        shutil.copy2(source / part, target / part)
    return target


def read_part(directory: Path, name: str) -> dict:
    return json.loads((directory / name).read_text(encoding="utf-8"))


def write_part(directory: Path, name: str, document: dict) -> None:
    (directory / name).write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")


def find_type(types: dict, type_id: str) -> dict:
    return next(item for item in types["object_types"] if item["id"] == type_id)


def find_property(object_type: dict, name: str) -> dict:
    return next(item for item in object_type["properties"] if item["name"] == name)


def set_property_default(object_type: dict, name: str, value) -> None:
    find_property(object_type, name)["default"] = value


def plant_small_roof(directory: Path) -> None:
    types = read_part(directory, "types.json")
    roof = find_type(types, "roof")
    roof["footprint"] = [PLANTED_ROOF_FT, PLANTED_ROOF_FT]
    set_property_default(roof, "width_mm", to_whole_mm(PLANTED_ROOF_FT))
    set_property_default(roof, "depth_mm", to_whole_mm(PLANTED_ROOF_FT))
    write_part(directory, "types.json", types)


def plant_missing_corner_post(directory: Path) -> None:
    placements = read_part(directory, "placements.json")
    placements["seed"] = [entry for entry in placements["seed"] if entry["id"] != PLANTED_MISSING_POST]
    write_part(directory, "placements.json", placements)


PLANTS = {"roof-smaller-than-floor": plant_small_roof, "corner-post-removed": plant_missing_corner_post}


def state_post_height(directory: Path) -> None:
    types = read_part(directory, "types.json")
    above_grade = find_property(find_type(types, "post"), "above_grade_mm")
    above_grade["default"] = to_whole_mm(SCRATCH_ABOVE_GRADE_FT)
    del above_grade["null_reason"]
    write_part(directory, "types.json", types)


def describe_refusal(answer: dict) -> str | None:
    refused = answer.get("refused")
    return f"refused by {refused['rule']}: {refused['message']}" if refused else None


def to_scene_request(directory: Path) -> dict:
    grid = read_part(directory, "world.json")["grid"]
    window = {"x0": 0, "y0": 0, "x1": grid["cols"] * grid["tile_mm"], "y1": grid["rows"] * grid["tile_mm"]}
    return {"scene": {"level_feet": 1, "window": window, "budget": {"max_features": 1000}, "layers": ["footprints"]}}


def read_house(launcher: Path, directory: Path) -> dict:
    steps = [{"state": {}}, {"views": {"views": [POST_VIEW]}}, to_scene_request(directory), {"outputs": {}}]
    answer = ask_world(launcher, directory, steps)
    if "refused" in answer:
        return answer
    placed, views, scene, outputs = answer["results"]
    elevations = {item["id"]: item.get("z_mm") for item in scene["footprints"]["items"]}
    return {"placed": placed, "post_rows": views["views"][0]["rows"], "elevations": elevations, "outputs": outputs}


def check_placed(house: dict) -> list[str]:
    observed = {object_id: item["stack_level"] for object_id, item in house["placed"].items()}
    return [
        state_line("objects placed at their stack levels", EXPECTED_STACK_LEVELS, observed),
        state_line("floor on four corner posts, applied at stack level", 1, observed.get("floor")),
        state_line("roof past its walls, applied at stack level", 3, observed.get("roof")),
    ]


def check_tiles(outputs: dict) -> list[str]:
    return [state_line(f"tiles under {type_id}", expected, outputs["counts"].get(type_id)) for type_id, expected in EXPECTED_TILES.items()]


def check_equations(outputs: dict) -> list[str]:
    observed = outputs["equations"]
    return [state_line(f"equation {name}", expected, observed.get(name)) for name, expected in work_equations_by_hand().items()]


def check_rules(outputs: dict) -> list[str]:
    return [state_line("rules broken by the placed house", [], outputs.get("violations"))]


def read_null_reason(directory: Path, type_id: str, name: str) -> str:
    return find_property(find_type(read_part(directory, "types.json"), type_id), name)["null_reason"]


def check_null_posts(directory: Path, house: dict) -> list[str]:
    reason = read_null_reason(directory, "post", "above_grade_mm")
    rows = house["post_rows"]
    reasons = [row.get("null_reasons") for row in rows]
    distinct_reasons = [item for index, item in enumerate(reasons) if item not in reasons[:index]]
    return [
        state_line("post rows in the posts view", 4, len(rows)),
        state_line("post height above grade in every row", [None] * 4, [row["values"]["above_grade"] for row in rows]),
        state_line("post whole length, above grade plus buried, in every row", [None] * 4, [row["values"]["length"] for row in rows]),
        state_line("the one reason every post row gives", [{"above_grade_mm": reason}], distinct_reasons),
    ]


def check_elevations(house: dict) -> list[str]:
    elevations = house["elevations"]
    return [
        state_line("floor elevation, on posts of no stated height", None, elevations.get("floor")),
        state_line("roof elevation, over a floor of no stated thickness", None, elevations.get("roof")),
    ]


def check_stated_height(launcher: Path, directory: Path, scratch: Path) -> list[str]:
    stated = copy_world(scratch / "post-height-stated", directory)
    state_post_height(stated)
    house = read_house(launcher, stated)
    if "refused" in house:
        return [state_line("the house with a post height stated", "no refusal", describe_refusal(house))]
    floor_elevation = to_whole_mm(SCRATCH_ABOVE_GRADE_FT)
    return [
        state_line(f"post whole length with {SCRATCH_ABOVE_GRADE_FT} ft above grade stated", [work_post_length_by_hand()] * 4,
                   [row["values"]["length"] for row in house["post_rows"]]),
        state_line(f"floor elevation with {SCRATCH_ABOVE_GRADE_FT} ft posts stated", floor_elevation, house["elevations"].get("floor")),
        state_line("roof elevation, the floor thickness still null", None, house["elevations"].get("roof")),
    ]


def read_types(directory: Path) -> dict:
    return {item["id"]: item for item in read_part(directory, "types.json")["object_types"]}


def check_footprints(types: dict) -> list[str]:
    lines = [state_line(f"{type_id} footprint in tiles", expected, types[type_id].get("footprint"))
             for type_id, expected in EXPECTED_FOOTPRINTS.items()]
    roof, floor = types["roof"]["footprint"], types["floor"]["footprint"]
    return lines + [state_line("overhang in tiles, roof minus floor", EXPECTED_OVERHANG_TILES, [roof[0] - floor[0], roof[1] - floor[1]])]


def check_bearing(types: dict) -> list[str]:
    return [state_line(f"{type_id} bears on, and by which tiles", expected, [types[type_id].get("bears_on"), types[type_id].get("bearing")])
            for type_id, expected in EXPECTED_BEARING.items()]


def has_reason(field: dict) -> bool:
    return bool(field.get("null_reason") if field.get("default") is None else field.get("source", {}).get("reason"))


def check_nothing_invented(types: dict) -> list[str]:
    lines = []
    for type_id, expected in EXPECTED_FIELDS.items():
        properties = types[type_id].get("properties", [])
        lines.append(state_line(f"{type_id} fields", sorted(expected), sorted(item["name"] for item in properties)))
        lines.append(state_line(f"{type_id} null fields", sorted(EXPECTED_NULLS[type_id]),
                                sorted(item["name"] for item in properties if item.get("default") is None)))
        lines.append(state_line(f"{type_id} fields with no reason", [], [item["name"] for item in properties if not has_reason(item)]))
    return lines


def judge_embedded_cases(launcher: Path, worlds: Path) -> dict:
    answer = run_engine(launcher, ["judge", "--embedded", str(worlds), "--json"])
    return json.loads(answer.strip().splitlines()[-1])


def check_embedded_cases(launcher: Path, directory: Path, scratch: Path) -> list[str]:
    worlds = scratch / "worlds"
    copy_world(worlds, directory)
    verdicts = {case_id: problems for case_id, problems in judge_embedded_cases(launcher, worlds).items() if case_id.startswith(f"{WORLD_NAME}-")}
    failing = [case_id for case_id, problems in verdicts.items() if problems]
    return [state_line("embedded cases", EXPECTED_CASES, len(verdicts)), state_line("embedded cases failing", [], failing)]


def to_attempt(index: int, entry: dict) -> dict:
    return {"attempt": {"branch": "main", "actor": "jim", "action": entry["action"], "at": f"2026-10-15T00:00:{index:02d}Z",
                        "args": entry["parameters"]}}


def name_seed_refusal(launcher: Path, directory: Path, scratch: Path) -> str:
    replay = copy_world(scratch / "seed-replay", directory)
    seed = read_part(replay, "placements.json")["seed"]
    write_part(replay, "placements.json", {"seed": []})
    answer = ask_world(launcher, replay, [to_attempt(index, entry) for index, entry in enumerate(seed)])
    if "refused" in answer:
        return f"world {describe_refusal(answer)}"
    for entry, result in zip(seed, answer["results"]):
        if "refused" in result:
            return f"{entry['id']} {describe_refusal(result)}"
    return "every placement applied one by one"


def check_house(launcher: Path, directory: Path, scratch: Path) -> list[str]:
    house = read_house(launcher, directory)
    refusal = describe_refusal(house) and name_seed_refusal(launcher, directory, scratch)
    lines = [state_line("placing the seed", "no refusal", refusal or "no refusal")]
    if refusal is None:
        outputs = house["outputs"]
        lines += check_placed(house) + check_tiles(outputs) + check_equations(outputs) + check_rules(outputs)
        lines += check_null_posts(directory, house) + check_elevations(house)
    return lines


def check_world(launcher: Path, directory: Path, scratch: Path) -> list[str]:
    types = read_types(directory)
    return (check_house(launcher, directory, scratch) + check_stated_height(launcher, directory, scratch) + check_footprints(types) + check_bearing(types)
            + check_nothing_invented(types) + check_embedded_cases(launcher, directory, scratch / "cases"))


def run_checks(launcher: Path, plant: str | None) -> list[str]:
    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = Path(scratch_name)
        directory = WORLD
        if plant:
            directory = copy_world(scratch / "planted")
            PLANTS[plant](directory)
        return check_world(launcher, directory, scratch)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plant", choices=sorted(PLANTS), help="run on a copy carrying this defect; the check must exit 1")
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
