"""Measure what keeping configs warm costs the resident engine: heap used and RSS per loaded config, cold vs warm latency, one simulate run.

Read-only against the running we-serve: it never restarts it. Distinct configs are copies of a world with one
millimetre setting the expand reads moved by 1 mm per copy, written beside the source (relative domain paths resolve) and removed afterwards.
"""
import json
import re
import subprocess
import statistics
import sys
import threading
import time
import urllib.request
from pathlib import Path

ENGINE = "http://127.0.0.1:8197/run"


def read_rss_kb(pid: int) -> int:
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    raise RuntimeError("no VmRSS")


def read_heap_used_kb(pid: int) -> int:
    subprocess.run(["jcmd", str(pid), "GC.run"], capture_output=True, check=True)
    info = subprocess.run(["jcmd", str(pid), "GC.heap_info"], capture_output=True, text=True, check=True).stdout
    return sum(int(used) for used in re.findall(r"generation\s+total \d+K, used (\d+)K", info))


def run_command(command: str, config: str) -> tuple[float, str]:
    body = json.dumps({"command": command, "config": config, "args": []}).encode()
    started = time.perf_counter()
    with urllib.request.urlopen(urllib.request.Request(ENGINE, data=body), timeout=600) as reply:
        reply.read()
        cache = reply.headers.get("X-We-Cache", "?")
    return time.perf_counter() - started, cache


def write_variants(source: Path, system: str, setting: str, count: int) -> list[str]:
    world = json.loads(source.read_text())
    base = world["systems"][system]["settings"][setting]
    paths = []
    for index in range(count):
        world["systems"][system]["settings"][setting] = base + index + 1
        path = source.parent / f".measure-{source.stem}-{index}.json"
        path.write_text(json.dumps(world))
        paths.append(str(path))
    return paths


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))]


def measure_world(pid: int, source: Path, system: str, setting: str) -> None:
    variants = write_variants(source, system, setting, 50)
    print(f"\n{source} varying {system}.{setting}: heap used before {read_heap_used_kb(pid)} kB, rss {read_rss_kb(pid)} kB")
    loaded = 0
    for target in (1, 10, 50):
        calls = [run_command("expand", path) for path in variants[loaded:target]]
        loaded = target
        cold = [seconds for seconds, cache in calls if cache == "miss"]
        hits = len(calls) - len(cold)
        spread = f"cold p50 {statistics.median(cold):.3f} s over {len(cold)} misses" if cold else "no misses"
        print(f"  after {target} distinct expands: heap used {read_heap_used_kb(pid)} kB, rss {read_rss_kb(pid)} kB, {spread}, {hits} hits dropped")
    warm = [run_command("expand", variants[0]) for _ in range(100)]
    times = [seconds for seconds, _ in warm]
    print(f"  warm repeat x100: p50 {percentile(times, 0.5):.4f} s, p99 {percentile(times, 0.99):.4f} s, cache {sorted({c for _, c in warm})}")


def measure_simulate(pid: int, config: str) -> None:
    peak = [read_rss_kb(pid)]
    done = threading.Event()

    def sample() -> None:
        while not done.is_set():
            peak.append(read_rss_kb(pid))
            time.sleep(0.05)

    sampler = threading.Thread(target=sample)
    sampler.start()
    seconds, cache = run_command("simulate", config)
    done.set()
    sampler.join()
    print(f"\nsimulate {config}: {seconds:.2f} s wall, cache {cache}, rss start {peak[0]} kB, peak {max(peak)} kB")


def main() -> None:
    pid = int(sys.argv[1])
    try:
        print(f"we-serve pid {pid}, rss now {read_rss_kb(pid)} kB (not idle: the service is live and keeps its cache)")
        measure_world(pid, Path("/home/deploy/workspace/worlds/greenhouse/seventy.json"), "earth_battery", "strip_mm")
        measure_world(pid, Path("/home/deploy/workspace/small-house/world.json"), "walls", "height_mm")
        measure_simulate(pid, "/home/deploy/workspace/small-house/world.json")
    finally:
        for leftover in [*Path("/home/deploy/workspace/worlds/greenhouse").glob(".measure-*.json"), *Path("/home/deploy/workspace/small-house").glob(".measure-*.json")]:
            leftover.unlink()


if __name__ == "__main__":
    main()
