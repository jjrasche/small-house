"""Check the small-house world's domain pins load on the pinned world engine, with the standard library alone.

world.json is Jim's small house as five systems, each with a chosen solution from the construction domain and the settings the sketch
gives, written against a draft of the world config the engine does not read yet. What can be checked today: every domain the world `uses`
is pinned by its current bytes and loads on the engine as a used domain. The check copies the domain files from ../domains (or
DOMAINS_DIR) into a scratch directory, writes a world there that carries this world's own `uses` entries, and runs `we validate` on it, so a
domain edited since the world pinned it, or one the engine's contract refuses, fails here.
One line a pinned domain, the validator's own count, then '<n> of <m> small house checks agree'; exit 1 on any difference, 2 when the
engine or the domains cannot be found. --plant domain-pin-stale changes one hex digit of the pin and must exit 1.
Usage: python3 check.py [--plant domain-pin-stale]
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
WORLD_FILE = "world.json"
DOMAIN_FILE_GLOB = "*.domain.json"
WRAPPER_ID = "small-house-uses"
WRAPPER_GRID = {"cols": 1, "rows": 1, "tile_mm": 1000, "shape": "square"}
WRAPPER_TYPES = [{"id": "marker", "label": "A type the world schema demands at least one of", "footprint": [1, 1]}]
EXIT_REFUSED = 2


class Refused(Exception):
    pass


def read_engine_pin() -> str:
    return (WORLD / "engine.pin").read_text(encoding="utf-8").strip()


def locate_engine() -> Path:
    return Path(os.environ.get("WORLD_ENGINE_DIR") or WORLD.parent / "world-engine").resolve()


def locate_domains() -> Path:
    return Path(os.environ.get("DOMAINS_DIR") or WORLD.parent / "domains").resolve()


def find_launcher(engine: Path) -> Path:
    return engine / "kotlin" / ("we.cmd" if os.name == "nt" else "we")


def has_commit(engine: Path, pin: str) -> bool:
    ancestry = subprocess.run(["git", "-C", str(engine), "merge-base", "--is-ancestor", pin, "HEAD"], capture_output=True)
    return ancestry.returncode == 0


def require_engine(engine: Path, pin: str) -> Path:
    launcher = find_launcher(engine)
    if not launcher.is_file():
        raise Refused(f"no Kotlin launcher at {launcher}; set WORLD_ENGINE_DIR to a world-engine checkout")
    if not has_commit(engine, pin):
        raise Refused(f"the engine at {engine} does not contain engine.pin {pin}")
    return launcher


def require_domains(domains: Path) -> list[Path]:
    domain_files = sorted(domains.glob(DOMAIN_FILE_GLOB))
    if not domain_files:
        raise Refused(f"no {DOMAIN_FILE_GLOB} at {domains}; set DOMAINS_DIR to a domains checkout")
    return domain_files


def run_engine(launcher: Path, arguments: list[str]) -> str:
    finished = subprocess.run([str(launcher), *arguments], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    if not finished.stdout.strip():
        raise Refused(f"`we {' '.join(arguments)}` answered nothing (exit {finished.returncode}): {finished.stderr.strip()}")
    return finished.stdout


def read_world() -> dict:
    return json.loads((WORLD / WORLD_FILE).read_text(encoding="utf-8"))


def to_scratch_reference(reference: dict) -> dict:
    return {**reference, "file": Path(reference["file"]).name}


def write_wrapper_world(uses: list[dict], worlds: Path) -> None:
    world = {"id": WRAPPER_ID, "world_version": 2, "title": "The domains small-house pins", "grid": WRAPPER_GRID,
             "object_types": WRAPPER_TYPES, "rules": [], "equations": [], "seed": [], "uses": [to_scratch_reference(entry) for entry in uses]}
    (worlds / f"{WRAPPER_ID}.world.json").write_text(json.dumps(world, indent=1) + "\n", encoding="utf-8")


def plant_stale_pin(uses: list[dict]) -> None:
    pin = uses[0]["sha256"]
    uses[0]["sha256"] = ("1" if pin[0] == "0" else "0") + pin[1:]


PLANTS = {"domain-pin-stale": plant_stale_pin}


def judge(expected, observed) -> str:
    return "agrees" if expected == observed else "differs"


def state_line(what: str, expected, observed) -> str:
    return f"{what}: {expected} against {observed}: {judge(expected, observed)}"


def validate_worlds(launcher: Path, worlds: Path) -> list[str]:
    return run_engine(launcher, ["validate", "--worlds", str(worlds)]).strip().splitlines()


def check_pins(launcher: Path, domain_files: list[Path], uses: list[dict]) -> list[str]:
    with tempfile.TemporaryDirectory() as scratch:
        worlds = Path(scratch) / "worlds"
        worlds.mkdir()
        for path in domain_files:
            shutil.copy2(path, worlds / path.name)
        write_wrapper_world(uses, worlds)
        report = validate_worlds(launcher, worlds)
    failures = [line for line in report if line.startswith("FAIL")]
    lines = [state_line(f"{Path(entry['file']).name} as pinned by {WORLD_FILE} loads on the engine", [],
                        [line for line in failures if entry["domain"] in line or WRAPPER_ID in line])
             for entry in uses]
    return lines + [state_line("worlds the validator accepts", ["1 worlds valid", "0 invalid"], report[-2:])]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plant", choices=sorted(PLANTS), help="run on a copy carrying this defect; the check must exit 1")
    options = parser.parse_args()
    pin, engine, domains = read_engine_pin(), locate_engine(), locate_domains()
    try:
        launcher = require_engine(engine, pin)
        domain_files = require_domains(domains)
        uses = read_world()["uses"]
        if options.plant:
            PLANTS[options.plant](uses)
        lines = check_pins(launcher, domain_files, uses)
    except Refused as refusal:
        print(f"refused: {refusal}")
        return EXIT_REFUSED
    print(f"engine {engine} contains engine.pin {pin}; domains at {domains}")
    for line in lines:
        print(line)
    agreed = sum(line.endswith(": agrees") for line in lines)
    print(f"{agreed} of {len(lines)} small house checks agree")
    return 0 if agreed == len(lines) else 1


if __name__ == "__main__":
    sys.exit(main())
