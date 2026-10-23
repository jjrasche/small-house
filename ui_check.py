#!/usr/bin/env python3
"""Does the page show what the engine places? Any world the resident engine serves, standard library plus headless Chromium.

Engine against spec: every piece `we expand` places is in the page's spec.json with the same system, material, size and position (mm),
and the spec holds no box the engine did not place. A wall the page cuts around an opening is several boxes (`<id>`, `<id>#2`); they must
lie inside the engine's piece, span its footprint and reach its top.
Spec against drawn: the page is loaded headless at 390x844 and 1280x800 and its accessibility tree is read; the volume renders one node per
box it draws, named `volume/<id>`, each with a screen rectangle. The drawn ids must be the spec's boxes, each with area, the counts per
system must be the engine's, and the dock must list every system that places something.
One line a check; '<n> of <m> ui checks agree'; exit 1 on any difference, 2 when the engine or the page cannot be reached.
Usage: python3 ui_check.py --world small-house [--plant drop-loft-joist]
"""
import argparse
import base64
import copy
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

CHROME = os.environ.get("CHROME_BIN") or str(Path.home() / ".cache/ms-playwright/chromium-1140/chrome-linux/chrome")
VIEWPORTS = (("phone", 390, 844), ("desktop", 1280, 800))
TOLERANCE_MM = 1.0
EXIT_UNREACHABLE = 2
SETTLE_POLLS = 3
POLL_SECONDS = 2
LOAD_SECONDS = 120
DEBUG_PORT = 9333


class Unreachable(Exception):
    pass


def fetch_text(url: str, body: bytes | None = None) -> str:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=120) as reply:
            return reply.read().decode("utf-8")
    except OSError as failure:
        raise Unreachable(f"{url}: {failure}") from failure


def fetch_expansion(engine_url: str, world: str) -> dict:
    asked = json.dumps({"command": "expand", "config": world}).encode()
    return json.loads(fetch_text(f"{engine_url}/run", asked))


def fetch_spec(page_url: str, world: str) -> dict:
    return json.loads(fetch_text(f"{page_url}/spec.json?world={world}"))


def find_volume(spec: dict) -> dict:
    volumes, stack = [], [spec["root"]]
    while stack:
        node = stack.pop()
        if node["type"] == "volume" and node["id"] == "volume":
            volumes.append(node["props"])
        stack.extend(node.get("children", []))
    if not volumes:
        raise Unreachable("the spec has no node named volume")
    return volumes[0]


def base_id(box_id: str) -> str:
    return box_id.split("#")[0]


def drop_loft_joist(spec: dict) -> None:
    volume = find_volume(spec)
    joist = next(box for box in volume["boxes"] if box["id"].startswith("joist@"))
    volume["boxes"].remove(joist)


PLANTS = {"drop-loft-joist": drop_loft_joist}


def expected_box(piece: dict) -> dict:
    """The box the page should hold for one engine piece: centre x and y, base z, and the three sizes."""
    fields = piece.get("fields", {})
    if "length_mm" in piece:
        along, across = piece["length_mm"], fields["thickness_mm"]
        is_quarter_turn = piece.get("rotation_deg") == 90
        width, depth = (across, along) if is_quarter_turn else (along, across)
        centre_x = piece["x_mm"] + (0 if is_quarter_turn else along / 2)
        centre_y = piece["y_mm"] + (along / 2 if is_quarter_turn else 0)
        return {"x": centre_x, "y": centre_y, "z": piece["elevation_mm"], "width": width, "depth": depth, "height": fields["height_mm"]}
    return {"x": piece["x_mm"] + piece["width_mm"] / 2, "y": piece["y_mm"] + piece["depth_mm"] / 2, "z": piece["elevation_mm"],
            "width": piece["width_mm"], "depth": piece["depth_mm"], "height": fields["height_mm"]}


def box_extent(box: dict) -> dict:
    return {"x0": box["x_mm"] - box["width_mm"] / 2, "x1": box["x_mm"] + box["width_mm"] / 2,
            "y0": box["y_mm"] - box["depth_mm"] / 2, "y1": box["y_mm"] + box["depth_mm"] / 2,
            "z0": box["z_mm"], "z1": box["z_mm"] + box["height_mm"]}


def is_near(left: float, right: float) -> bool:
    return abs(left - right) <= TOLERANCE_MM


def describe_gap(name: str, want: float, got: float) -> str:
    return f"{name} {want:g} against {got:g}"


def compare_whole_box(want: dict, box: dict) -> list[str]:
    got = {"x": box["x_mm"], "y": box["y_mm"], "z": box["z_mm"], "width": box["width_mm"], "depth": box["depth_mm"], "height": box["height_mm"]}
    return [describe_gap(name, want[name], got[name]) for name in want if not is_near(want[name], got[name])]


def compare_cut_boxes(want: dict, boxes: list[dict]) -> list[str]:
    envelope = {"x0": want["x"] - want["width"] / 2, "x1": want["x"] + want["width"] / 2,
                "y0": want["y"] - want["depth"] / 2, "y1": want["y"] + want["depth"] / 2,
                "z0": want["z"], "z1": want["z"] + want["height"]}
    extents = [box_extent(box) for box in boxes]
    gaps = []
    for edge in ("x0", "y0", "z0"):
        lowest = min(extent[edge] for extent in extents)
        if lowest < envelope[edge] - TOLERANCE_MM:
            gaps.append(f"{edge} reaches {lowest:g} outside {envelope[edge]:g}")
    for edge in ("x1", "y1", "z1"):
        highest = max(extent[edge] for extent in extents)
        if not is_near(highest, envelope[edge]):
            gaps.append(describe_gap(f"{edge} reach", envelope[edge], highest))
    for edge in ("x0", "y0"):
        if not is_near(min(extent[edge] for extent in extents), envelope[edge]):
            gaps.append(describe_gap(f"{edge} span", envelope[edge], min(extent[edge] for extent in extents)))
    return gaps


def read_detail_system(volume: dict, piece_id: str) -> str | None:
    detail = volume.get("details", {}).get(piece_id)
    if not detail:
        return None
    for section in detail["sections"]:
        for row in section["rows"]:
            if row["label"] == "system":
                return row["value"]
    return None


def is_cut_by_opening(piece: dict, openings: list[dict]) -> bool:
    if piece in openings:
        return False
    wall = box_extent_of(expected_box(piece))
    return any(overlaps_in_plan(wall, box_extent_of(expected_box(opening))) for opening in openings)


def box_extent_of(want: dict) -> dict:
    return {"x0": want["x"] - want["width"] / 2, "x1": want["x"] + want["width"] / 2, "y0": want["y"] - want["depth"] / 2, "y1": want["y"] + want["depth"] / 2}


def overlaps_in_plan(left: dict, right: dict) -> bool:
    return left["x0"] < right["x1"] and right["x0"] < left["x1"] and left["y0"] < right["y1"] and right["y0"] < left["y1"]


def piece_difference(piece: dict, volume: dict, openings: list[dict]) -> list[str]:
    boxes = [box for box in volume["boxes"] if base_id(box["id"]) == piece["id"]]
    if not boxes:
        return ["no box in the spec"]
    gaps = []
    system = read_detail_system(volume, piece["id"])
    if system != piece["system"]:
        gaps.append(f"system {piece['system']} against {system}")
    styles = {box["style"] for box in boxes}
    if styles != {piece["material"]}:
        gaps.append(f"material {piece['material']} against {sorted(styles)}")
    want = expected_box(piece)
    gaps += compare_whole_box(want, boxes[0]) if len(boxes) == 1 and not is_cut_by_opening(piece, openings) else compare_cut_boxes(want, boxes)
    return gaps


def judge(gaps: list[str]) -> str:
    return "agrees" if not gaps else "differs (" + "; ".join(gaps) + ")"


def engine_pieces(expansion: dict) -> list[dict]:
    return expansion["objects"] + expansion["instances"]


def count_by_system(pieces: list[dict]) -> dict:
    counts: dict = {}
    for piece in pieces:
        counts[piece["system"]] = counts.get(piece["system"], 0) + 1
    return counts


def spec_lines(expansion: dict, volume: dict) -> list[str]:
    pieces = engine_pieces(expansion)
    lines = [f"spec holds {piece['id']} as the engine places it: {judge(piece_difference(piece, volume, expansion["instances"]))}" for piece in pieces]
    placed = {piece["id"] for piece in pieces}
    held = {base_id(box["id"]) for box in volume["boxes"]}
    lines.append(f"spec holds no box the engine did not place: {judge([f'extra {name}' for name in sorted(held - placed)])}")
    lines.append(f"spec holds one piece per engine piece: {judge([] if len(held) == len(placed) else [describe_gap('pieces', len(placed), len(held))])}")
    return lines


def drawn_gaps(spec_ids: set, drawn: dict) -> list[str]:
    return [f"drawn but not in the spec: {name}" for name in sorted(set(drawn) - spec_ids)] + \
           [f"in the spec but not drawn: {name}" for name in sorted(spec_ids - set(drawn))]


def blank_gaps(drawn: dict) -> list[str]:
    return [f"{name} has no area on screen" for name, rect in sorted(drawn.items()) if rect[0] < 1 or rect[1] < 1]


def system_count_gaps(expansion: dict, drawn: dict, system: str) -> list[str]:
    owner = {piece["id"]: piece["system"] for piece in engine_pieces(expansion)}
    drawn_here = {base_id(name) for name in drawn if owner.get(base_id(name)) == system}
    want = count_by_system(engine_pieces(expansion))[system]
    return [] if len(drawn_here) == want else [describe_gap("pieces drawn", want, len(drawn_here))]


def dock_gaps(expansion: dict, dock_systems: set) -> list[str]:
    return [f"dock has no row for {name}" for name in sorted(count_by_system(engine_pieces(expansion))) if name not in dock_systems]


def drawn_lines(label: str, expansion: dict, volume: dict, scene: dict) -> list[str]:
    drawn, dock = scene["boxes"], scene["dock_systems"]
    spec_ids = {box["id"] for box in volume["boxes"]}
    lines = [f"{label}: the drawn boxes are the spec's boxes: {judge(drawn_gaps(spec_ids, drawn))}",
             f"{label}: every drawn box has area on screen: {judge(blank_gaps(drawn))}"]
    lines += [f"{label}: {system} drawn as many times as the engine places it: {judge(system_count_gaps(expansion, drawn, system))}"
              for system in sorted(count_by_system(engine_pieces(expansion)))]
    lines.append(f"{label}: the dock lists every system that places something: {judge(dock_gaps(expansion, dock))}")
    return lines


class Socket:
    """A client for the one WebSocket frame shape Chromium's debugging port speaks."""

    def __init__(self, url: str):
        address, path = url[len("ws://"):].split("/", 1)
        host, port = address.split(":")
        self.connection = socket.create_connection((host, int(port)), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.connection.sendall((f"GET /{path} HTTP/1.1\r\nHost: {address}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                                 f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        reply = b""
        while b"\r\n\r\n" not in reply:
            reply += self.connection.recv(1)
        self.last_id = 0

    def read_exactly(self, count: int) -> bytes:
        got = b""
        while len(got) < count:
            piece = self.connection.recv(count - len(got))
            if not piece:
                raise Unreachable("the browser closed its debugging port")
            got += piece
        return got

    def send_text(self, text: str) -> None:
        payload, mask = text.encode(), os.urandom(4)
        size = len(payload)
        head = bytes([0x80 | size]) if size < 126 else b"\xfe" + struct.pack(">H", size) if size < 65536 else b"\xff" + struct.pack(">Q", size)
        self.connection.sendall(b"\x81" + head + mask + bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload)))

    def read_message(self) -> str:
        message = b""
        while True:
            first, second = self.read_exactly(2)
            size = second & 127
            size = struct.unpack(">H", self.read_exactly(2))[0] if size == 126 else struct.unpack(">Q", self.read_exactly(8))[0] if size == 127 else size
            message += self.read_exactly(size)
            if first & 0x80:
                return message.decode()

    def call(self, method: str, **params) -> dict:
        self.last_id += 1
        self.send_text(json.dumps({"id": self.last_id, "method": method, "params": params}))
        while True:
            reply = json.loads(self.read_message())
            if reply.get("id") == self.last_id:
                return reply.get("result", {})


def start_browser(width: int, height: int, profile: str) -> tuple:
    if not Path(CHROME).exists():
        raise Unreachable(f"no Chromium at {CHROME}; set CHROME_BIN")
    process = subprocess.Popen([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--enable-unsafe-swiftshader", f"--window-size={width},{height}",
                                f"--remote-debugging-port={DEBUG_PORT}", f"--user-data-dir={profile}", "about:blank"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            tabs = json.loads(fetch_text(f"http://127.0.0.1:{DEBUG_PORT}/json"))
            return process, next(tab["webSocketDebuggerUrl"] for tab in tabs if tab["type"] == "page")
        except (Unreachable, StopIteration):
            time.sleep(0.2)
    process.kill()
    raise Unreachable("Chromium did not open its debugging port")


def read_nodes(browser: Socket) -> list[dict]:
    return browser.call("Accessibility.getFullAXTree").get("nodes", [])


def node_name(node: dict) -> str:
    return str(node.get("name", {}).get("value", ""))


def read_rectangle(browser: Socket, node: dict) -> tuple:
    box = browser.call("DOM.getBoxModel", backendNodeId=node["backendDOMNodeId"]).get("model")
    return (box["width"], box["height"]) if box else (0, 0)


def read_scene(browser: Socket, nodes: list[dict]) -> dict:
    boxes = {node_name(node)[len("volume/"):]: read_rectangle(browser, node) for node in nodes if "@" in node_name(node) and node_name(node).startswith("volume/")}
    dock = {name.split(",")[0][len("systems."):] for name in map(node_name, nodes) if name.startswith("systems.") and "." not in name.split(",")[0][len("systems."):]}
    return {"boxes": boxes, "dock_systems": dock}


def count_drawn(nodes: list[dict]) -> int:
    return sum(1 for node in nodes if "@" in node_name(node) and node_name(node).startswith("volume/"))


def wait_for_scene(browser: Socket) -> list[dict]:
    steady, last_count, nodes = 0, -1, []
    for _ in range(LOAD_SECONDS // POLL_SECONDS):
        time.sleep(POLL_SECONDS)
        nodes = read_nodes(browser)
        count = count_drawn(nodes)
        steady = steady + 1 if count == last_count and count > 0 else 0
        last_count = count
        if steady >= SETTLE_POLLS:
            break
    return nodes


def draw_page(page_url: str, world: str, width: int, height: int) -> dict:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
        process, address = start_browser(width, height, profile)
        try:
            browser = Socket(address)
            browser.call("Page.enable")
            browser.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=width < 600)
            browser.call("Page.navigate", url=f"{page_url}/index.html?spec=/spec.json?world={world}&full=1")
            return read_scene(browser, wait_for_scene(browser))
        finally:
            process.kill()
            process.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--world", required=True, help="a world id the resident engine serves")
    parser.add_argument("--engine", default=os.environ.get("WE_SERVE_URL", "http://127.0.0.1:8197"))
    parser.add_argument("--page", default=os.environ.get("PAGE_URL", "http://172.17.0.1:8090"))
    parser.add_argument("--plant", choices=sorted(PLANTS), help="run on a copy of the spec carrying this defect; the check must exit 1")
    options = parser.parse_args()
    try:
        expansion = fetch_expansion(options.engine, options.world)
        spec = fetch_spec(options.page, options.world)
        if options.plant:
            spec = copy.deepcopy(spec)
            PLANTS[options.plant](spec)
        volume = find_volume(spec)
        lines = spec_lines(expansion, volume)
        for label, width, height in VIEWPORTS:
            lines += drawn_lines(f"{label} {width}x{height}", expansion, volume, draw_page(options.page, options.world, width, height))
    except (Unreachable, KeyError, json.JSONDecodeError) as failure:
        print(f"refused: {failure!r}")
        return EXIT_UNREACHABLE
    for line in lines:
        print(line)
    agreed = sum(line.endswith(": agrees") for line in lines)
    print(f"{agreed} of {len(lines)} ui checks agree" + ("" if agreed == len(lines) else f"; {len(lines) - agreed} differ"))
    return 0 if agreed == len(lines) else 1


if __name__ == "__main__":
    sys.exit(main())
