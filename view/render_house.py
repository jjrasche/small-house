"""Draw the small house from the engine's expansion as one self-contained, phone-first page, with the standard library alone.

Reads `we expand world.json` (the engine at ../world-engine, or WORLD_ENGINE_DIR) and the reasons stated in world.json, and writes
view/house.html: a labelled plan in millimetres with north up (x east, y north from the south-west corner), a legend, one card for each
part of the house saying what the sketch gives and what it does not (with the reason), and every object in a folded table.
Usage: python3 view/render_house.py
"""
import html
import json
import os
import subprocess
import sys
from pathlib import Path

VIEW = Path(__file__).resolve().parent
WORLD_FILE = VIEW.parent / "world.json"
OUTPUT_FILE = VIEW / "house.html"
UNKNOWN_MARK = "—"
READING_PREFIX = "reading:"
POST_MARKER_MM = 300
PLAN_MARGIN_MM = 350
LABEL_SIZE_MM = 190
SYSTEM_TITLES = {"foundation": "Posts", "floor": "Floor", "walls": "Walls", "roof": "Roof", "glazing": "Glass"}
SYSTEM_CLASS = {"foundation": "post", "floor": "floor", "walls": "wall", "roof": "roof", "glazing": "glass"}
LEVEL_CLASS = {0: "post", 1: "floor", 2: "wall", 3: "roof"}
PAINT_ORDER = {"roof": 0, "floor": 1, "wall": 2, "post": 3}


def locate_launcher() -> Path:
    engine = Path(os.environ.get("WORLD_ENGINE_DIR") or VIEW.parent.parent / "world-engine")
    return engine / "kotlin" / "we"


def run_expansion() -> dict:
    finished = subprocess.run(["sh", str(locate_launcher()), "expand", str(WORLD_FILE)], capture_output=True, text=True)
    answer = json.loads(finished.stdout)
    if finished.returncode != 0 or "refused" in answer:
        raise SystemExit(f"the engine refused the world: {answer.get('refused')}")
    return answer


def read_world() -> dict:
    return json.loads(WORLD_FILE.read_text(encoding="utf-8"))


def humanize(name: str) -> str:
    return name.removesuffix("_mm").replace("_", " ")


def escape(value) -> str:
    return html.escape(str(value))


def flip_y(extent_height: int, y_mm: float) -> float:
    return extent_height - y_mm


def find_object(expansion: dict, type_id: str) -> dict:
    return next(item for item in expansion["objects"] if item["type"] == type_id)


# ---- the plan

def draw_text(x: float, y: float, content: str, css_class: str = "label", anchor: str = "middle", rotate: bool = False) -> str:
    turn = f' transform="rotate(-90 {x} {y})"' if rotate else ""
    return f'<text class="{css_class}" x="{x}" y="{y}" text-anchor="{anchor}"{turn}>{escape(content)}</text>'


def draw_box(item: dict, extent_height: int) -> str:
    top = flip_y(extent_height, item["y_mm"] + item["depth_mm"])
    return (f'<rect class="{LEVEL_CLASS[item["level"]]}" x="{item["x_mm"]}" y="{top}" '
            f'width="{item["width_mm"]}" height="{item["depth_mm"]}"/>')


def draw_wall(item: dict, extent_height: int) -> str:
    x, y = item["x_mm"], flip_y(extent_height, item["y_mm"])
    if item["width_mm"] is not None:
        return f'<line class="wall" x1="{x}" y1="{y}" x2="{x + item["width_mm"]}" y2="{y}"/>'
    return f'<line class="wall" x1="{x}" y1="{y}" x2="{x}" y2="{y - item["depth_mm"]}"/>'


def draw_post(item: dict, extent_height: int) -> str:
    half = POST_MARKER_MM / 2
    return (f'<rect class="post" x="{item["x_mm"] - half}" y="{flip_y(extent_height, item["y_mm"]) - half}" '
            f'width="{POST_MARKER_MM}" height="{POST_MARKER_MM}"/>')


def draw_pane(pane: dict, extent_height: int) -> str:
    half = pane["length_mm"] / 2
    x, y = pane["x_mm"], flip_y(extent_height, pane["y_mm"])
    if pane["rotation_deg"] == 0:
        return f'<line class="glass" x1="{x - half}" y1="{y}" x2="{x + half}" y2="{y}"/>'
    return f'<line class="glass" x1="{x}" y1="{y - half}" x2="{x}" y2="{y + half}"/>'


def draw_shape(item: dict, extent_height: int) -> str:
    drawers = {"post": draw_post, "wall": draw_wall}
    return drawers.get(item["type"], draw_box)(item, extent_height)


def draw_plan_labels(expansion: dict) -> str:
    width, height = expansion["extent_mm"]
    roof, floor = find_object(expansion, "roof"), find_object(expansion, "floor")
    floor_top = flip_y(height, floor["y_mm"] + floor["depth_mm"])
    floor_centre_x = floor["x_mm"] + floor["width_mm"] / 2
    south_strip_y = flip_y(height, floor["y_mm"]) + 330
    east_x = floor["x_mm"] + floor["width_mm"] + 320
    return "".join([
        draw_text(roof["x_mm"] + 120, flip_y(height, roof["y_mm"] + roof["depth_mm"]) + 260, f"roof {roof['width_mm']} × {roof['depth_mm']}", anchor="start"),
        draw_text(floor_centre_x, floor_top + floor["depth_mm"] / 2, f"floor {floor['width_mm']} × {floor['depth_mm']}"),
        draw_text(floor_centre_x, south_strip_y, "glass (south)", "label glasslabel"),
        draw_text(floor_centre_x, south_strip_y + 600, f"roof reaches {roof['depth_mm'] - floor['depth_mm'] - 610} past the floor", "label muted"),
        draw_text(east_x, floor_top + floor["depth_mm"] / 2, "glass (east)", "label glasslabel", rotate=True),
        draw_text(width + 120, -120, "N ↑", "label muted", anchor="end"),
    ])


def draw_plan(expansion: dict) -> str:
    width, height = expansion["extent_mm"]
    by_level = sorted(expansion["objects"], key=lambda item: PAINT_ORDER[item["type"]])
    shapes = "".join(draw_shape(item, height) for item in by_level) + "".join(draw_pane(pane, height) for pane in expansion.get("instances", []))
    box = f"{-PLAN_MARGIN_MM} {-PLAN_MARGIN_MM} {width + 2 * PLAN_MARGIN_MM} {height + 2 * PLAN_MARGIN_MM}"
    return f'<svg viewBox="{box}" role="img" aria-label="Plan of the small house seen from above, north up">{shapes}{draw_plan_labels(expansion)}</svg>'


def draw_legend() -> str:
    entries = [("roof", "Roof (over everything)"), ("floor", "Floor"), ("wall", "Walls"), ("post", "Posts"), ("glass", "Glass")]
    return '<ul class="legend">' + "".join(f'<li><i class="sw {css}"></i>{label}</li>' for css, label in entries) + "</ul>"


# ---- the cards

def format_known(name: str, value, reason: str) -> str:
    note = f'<span class="badge">Jim to confirm</span><small>{escape(reason.removeprefix(READING_PREFIX).strip())}</small>' if reason.startswith(READING_PREFIX) else ""
    return f"<li><span>{escape(humanize(name))}</span> <b>{escape(value)} mm</b>{note}</li>"


def format_unknown(name: str, reason: str) -> str:
    return f'<li class="unknown"><span>{escape(humanize(name))}</span> <b>{UNKNOWN_MARK}</b><small>{escape(reason)}</small></li>'


def format_sides(sides: list[str]) -> str:
    return f"<li><span>sides</span> <b>{escape(', '.join(sides))}</b></li>"


def draw_setting(name: str, value, reason: str) -> str:
    if isinstance(value, list):
        return format_sides(value)
    return format_unknown(name, reason) if value is None else format_known(name, value, reason)


def draw_card(system: str, body: dict, count: int) -> str:
    reasons = body.get("reasons", {})
    rows = "".join(draw_setting(name, value, reasons.get(name, "")) for name, value in body["settings"].items())
    noun = "object" if count == 1 else "objects"
    return (f'<section class="card {SYSTEM_CLASS[system]}"><h3>{SYSTEM_TITLES[system]}<small>{count} {noun}</small></h3>'
            f"<ul>{rows}</ul></section>")


def count_by_system(expansion: dict) -> dict:
    counts: dict = {}
    for item in expansion["objects"] + expansion.get("instances", []):
        counts[item["system"]] = counts.get(item["system"], 0) + 1
    return counts


def draw_cards(world: dict, expansion: dict) -> str:
    counts = count_by_system(expansion)
    return "".join(draw_card(system, body, counts.get(system, 0)) for system, body in world["systems"].items())


def draw_supplied(expansion: dict) -> str:
    items = "".join(f"<p><b>{escape(figure['value'])} {escape(humanize(figure['unit']))}</b> <small>{escape(figure.get('reason', ''))}</small></p>"
                    for figure in expansion.get("supplied", {}).values())
    return f'<h2>From the sketch</h2><div class="supplied">{items}</div>' if items else ""


def draw_row(item: dict) -> str:
    cells = [item["id"], item["x_mm"], item["y_mm"], item.get("width_mm"), item.get("depth_mm"), item.get("level", "")]
    return "<tr>" + "".join(f"<td>{UNKNOWN_MARK if cell is None else escape(cell)}</td>" for cell in cells) + "</tr>"


def draw_table(expansion: dict) -> str:
    panes = [{**pane, "width_mm": pane["length_mm"], "depth_mm": None} for pane in expansion.get("instances", [])]
    head = "".join(f"<th>{name}</th>" for name in ("object", "x", "y", "width", "depth", "level"))
    rows = "".join(draw_row(item) for item in expansion["objects"] + panes)
    return f'<details><summary>Every object, in millimetres</summary><div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div></details>'


STYLE = """
:root { --ground:#f6f4ef; --card:#ffffff; --ink:#1f2328; --muted:#5f656c; --line:#dcd8cd; --roof:#9db4d6; --floor:#e2cfa5; --wall:#7a5a3a; --post:#3a3f45; --glass:#1f78b4; --badge:#fff0c2; }
@media (prefers-color-scheme: dark) { :root { --ground:#14161a; --card:#1d2026; --ink:#ececE7; --muted:#a3a9b1; --line:#30343b; --roof:#3a4b66; --floor:#5a4c33; --wall:#d5a574; --post:#d7dbe0; --glass:#5db7e8; --badge:#5a4a12; } }
* { box-sizing:border-box; }
body { margin:0 auto; padding:16px; max-width:640px; background:var(--ground); color:var(--ink); font:17px/1.45 system-ui, sans-serif; }
h1 { font-size:26px; margin:4px 0 2px; } h2 { font-size:20px; margin:28px 0 8px; } h3 { font-size:18px; margin:0 0 6px; display:flex; justify-content:space-between; align-items:baseline; }
p.sub { margin:0 0 14px; color:var(--muted); } small { color:var(--muted); font-weight:400; font-size:14px; display:block; }
h3 small { display:inline; }
svg { width:100%; height:auto; display:block; background:var(--card); border:1px solid var(--line); border-radius:8px; }
svg .roof { fill:var(--roof); fill-opacity:.5; stroke:var(--roof); stroke-width:24; stroke-dasharray:70 40; } svg .floor { fill:var(--floor); stroke:var(--muted); stroke-width:14; }
svg .wall { stroke:var(--wall); stroke-width:110; stroke-linecap:square; } svg .post { fill:var(--post); } svg .glass { stroke:var(--glass); stroke-width:80; }
svg .label { fill:var(--ink); font:600 190px system-ui, sans-serif; } svg .muted { fill:var(--muted); font-weight:400; } svg .glasslabel { fill:var(--glass); }
.legend { list-style:none; display:flex; flex-wrap:wrap; gap:6px 16px; padding:0; margin:12px 0 0; font-size:15px; }
.sw { display:inline-block; width:16px; height:16px; border-radius:3px; margin-right:6px; vertical-align:-2px; border:1px solid var(--line); }
.sw.roof { background:var(--roof); } .sw.floor { background:var(--floor); } .sw.wall { background:var(--wall); } .sw.post { background:var(--post); } .sw.glass { background:var(--glass); }
.card { background:var(--card); border:1px solid var(--line); border-left:6px solid var(--line); border-radius:8px; padding:12px 14px; margin:10px 0; }
.card.roof { border-left-color:var(--roof); } .card.floor { border-left-color:var(--floor); } .card.wall { border-left-color:var(--wall); } .card.post { border-left-color:var(--post); } .card.glass { border-left-color:var(--glass); }
.card ul { list-style:none; margin:0; padding:0; } .card li { padding:6px 0; border-top:1px solid var(--line); display:flex; flex-wrap:wrap; justify-content:space-between; gap:2px 12px; }
.card li:first-child { border-top:0; } .card li small { flex-basis:100%; } .unknown b { color:var(--muted); }
.badge { background:var(--badge); border-radius:10px; padding:1px 8px; font-size:13px; margin-left:8px; }
.supplied p { margin:6px 0; } details { margin-top:24px; } summary { cursor:pointer; padding:10px 0; font-weight:600; }
.scroll { overflow-x:auto; } table { border-collapse:collapse; font-size:14px; width:100%; } th, td { border-bottom:1px solid var(--line); padding:4px 8px; text-align:left; white-space:nowrap; }
"""


def build_page(world: dict, expansion: dict) -> str:
    width, height = expansion["extent_mm"]
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>Small house</title><style>{STYLE}</style></head><body>"
            f'<h1>Your small house</h1><p class="sub">Seen from above, north up. Every size is in millimetres. {width} × {height} overall.</p>'
            f"{draw_plan(expansion)}{draw_legend()}"
            f"<h2>What the sketch gives, and what it does not</h2>{draw_cards(world, expansion)}"
            f"{draw_supplied(expansion)}{draw_table(expansion)}</body></html>")


def main() -> int:
    OUTPUT_FILE.write_text(build_page(read_world(), run_expansion()), encoding="utf-8")
    print(f"wrote {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
