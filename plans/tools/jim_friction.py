#!/usr/bin/env python3
"""Friction classifier for Jim's messages: binary judge questions, deterministic score.

Commands: selftest | extract | analyse | judge-stats
Judge: Groq when GROQ_API_KEY is set, otherwise `claude -p --model haiku` (SAME-FAMILY).
"""
import concurrent.futures
import glob
import hashlib
import json
import os
import random
import re
import statistics
import subprocess
import sys
import urllib.request
from collections import Counter, defaultdict

HOME = os.path.expanduser("~")
PROJECTS = f"{HOME}/.claude/projects"
SEATS = ["small-house", "domains", "world-engine", "factored-ui", "research", "business"]
DAY_FIRST, DAY_LAST = "2026-10-17", "2026-10-27"
BEFORE_DAYS = [f"2026-10-{d}" for d in range(19, 24)]
AFTER_DAYS = [f"2026-10-{d}" for d in range(24, 28)]
CAP_PER_PERIOD = 400
THIN_BELOW = 30
SEED = 1
CACHE_PATH = "/tmp/jim_friction_cache.jsonl"
SMALL_HOUSE_MAIN = "ca0bc5ee-1b9d-5e26-8c01-32ec5c7cc7d5.jsonl"

KNOWN_ANGRY = [50826, 51515, 36525, 36745, 27127, 26937]
KNOWN_HAPPY = [38189, 38262, 38423, 38716, 38760, 38777, 38848]
CASES_FILES = [f"{HOME}/.claude/references/jim-communication-cases.jsonl", f"{HOME}/.claude/skills/focus/cases.jsonl"]

SYSTEM_PROMPT = (
    "You judge one message a user (Jim) typed to an AI assistant. You are given the start of the assistant's "
    "previous reply and Jim's message. Jim swears a lot when he is excited, thinking aloud or talking about other "
    "people and companies; that alone is NOT a complaint. Answer six yes/no questions about Jim's message. "
    'Answer with JSON only: {"q1":bool,"q2":bool,"q3":bool,"q4":bool,"q5":bool,"q6":bool}.\n'
    "q1: Does Jim explicitly say the assistant's previous answer or action was wrong, unwanted, useless or not what "
    "he asked for, or criticise the way it was designed or done? Criticism of other companies, AI labs or the world is NOT a yes. A plain question about what something means is NOT a yes (that is q3). Jim agreeing with the assistant, brainstorming, "
    "or continuing his own long thought (often voice-dictated) is NOT a yes; q1 needs a statement that the assistant's output was bad. A passing remark on how the assistant behaves ('you keep pushing me') while he builds on the answer, without calling it wrong or unwanted, is NOT a yes.\n"
    "q2: Does Jim say he already told the assistant something, or repeat an earlier instruction because it was "
    "not followed ('I said ...', 'again', 'stop doing X')? New instructions are NOT a yes.\n"
    "q3: Does Jim say or ask that he does not understand something the assistant said or did (including 'what X?')?\n"
    "q4: Is Jim's anger, cursing or shouting (all caps, '!!!', 'fuck you', 'how the hell') directed at the assistant "
    "or at what it did or said? Triple exclamation marks or 'DUH' next to a complaint or challenge about what the assistant did, proposed or costs is a yes even when phrased as a question. Answer false if the cursing is excitement about ideas, enthusiasm, a rant about "
    "companies, the world or other people, or just casual speech with no complaint about the assistant.\n"
    "q5: Does Jim praise the assistant or its work, or express delight at what it said?\n"
    "q6: Does Jim build on the assistant's previous reply: continue the idea it gave, answer its question, accept it "
    "('yes', 'go', 'ok'), or use it? Continuing his own thought after it, without complaint, is a yes."
)

IGNORED_PREFIXES = ("<",)
IGNORED_SUBSTRINGS = ("Stop hook feedback", "continued from a previous conversation", "Base directory", "Another Claude session",
                      "Overnight chief-of-staff", "<system-reminder>", "[Request interrupted")


def content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text")
    return ""


def is_interrupt(text):
    return text.lstrip().startswith("[Request interrupted by user")


def is_jim_typed(text):
    stripped = text.strip()
    if not stripped or stripped.startswith(IGNORED_PREFIXES):
        return False
    return not any(marker in stripped[:400] for marker in IGNORED_SUBSTRINGS)


def seat_session_files(seat):
    directory = f"{PROJECTS}/-home-deploy-workspace-{seat}"
    return [path for path in sorted(glob.glob(f"{directory}/*.jsonl")) if not os.path.basename(path).startswith("fork-test")]


def read_session(path):
    """Yield one dict per top-level record in file order with the facts the measures need."""
    with open(path, encoding="utf-8") as handle:
        for line_index, line in enumerate(handle):
            try:
                record = json.loads(line)
            except ValueError:
                continue
            yield line_index, record


def summarise_session(seat, path):
    """One pass: Jim messages (with previous assistant text), interrupts, tool results, assistant stats, models."""
    session = os.path.basename(path)
    jim_messages, interrupts, tool_results, models = [], [], [], []
    assistant_messages_by_day = Counter()
    final_reply_words = []
    previous_assistant_text = ""
    last_assistant_text = ""
    last_assistant_day = None
    pending_final = None
    for line_index, record in read_session(path):
        kind = record.get("type")
        stamp = record.get("timestamp") or ""
        day = stamp[:10]
        if record.get("isSidechain"):
            continue
        message = record.get("message") or {}
        if kind == "assistant":
            blocks = message.get("content")
            text = content_text(blocks)
            if day:
                assistant_messages_by_day[day] += 1
                if message.get("model"):
                    models.append((day, message["model"]))
            if text.strip():
                previous_assistant_text = text
                pending_final = (day, len(text.split()))
        elif kind == "user":
            content = message.get("content")
            if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_results.append((day, bool(block.get("is_error"))))
                continue
            text = content_text(content)
            if is_interrupt(text):
                interrupts.append(day)
                continue
            if not is_jim_typed(text):
                continue
            if pending_final:
                final_reply_words.append(pending_final)
                pending_final = None
            jim_messages.append({"seat": seat, "session": session, "line": line_index, "day": day, "jim": text.strip(),
                                 "assistant": previous_assistant_text[:600]})
    return {"jim": jim_messages, "interrupts": interrupts, "tool_results": tool_results, "models": models,
            "assistant_by_day": assistant_messages_by_day, "final_words": final_reply_words}


def in_window(day):
    return DAY_FIRST <= day <= DAY_LAST


def load_cache():
    cache = {}
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    cache[row["key"]] = row["answers"]
                except (ValueError, KeyError):
                    continue
    return cache


def append_cache(key, answers):
    with open(CACHE_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"key": key, "answers": answers}) + "\n")


def judge_key(assistant_text, jim_text):
    digest = hashlib.sha256((SYSTEM_PROMPT + "\x00" + assistant_text[:600] + "\x00" + jim_text[:1500]).encode("utf-8"))
    return digest.hexdigest()


def build_user_prompt(assistant_text, jim_text):
    return f"ASSISTANT'S PREVIOUS REPLY (start):\n{assistant_text[:600] or '(none)'}\n\nJIM'S MESSAGE:\n{jim_text[:1500]}"


def parse_answers(raw):
    found = re.search(r"\{.*?\}", raw, re.S)
    answers = {name: False for name in ("q1", "q2", "q3", "q4", "q5", "q6")}
    if not found:
        return answers, False
    try:
        parsed = json.loads(found.group(0))
    except ValueError:
        return answers, False
    for name in answers:
        answers[name] = parsed.get(name) is True
    return answers, True


def call_groq(user_prompt):
    body = {"model": "openai/gpt-oss-20b", "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                                          {"role": "user", "content": user_prompt}],
            "max_completion_tokens": 1500, "response_format": {"type": "json_object"},
            "reasoning_effort": "low", "include_reasoning": False}
    request = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=json.dumps(body).encode(),
                                     method="POST", headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0",
                                                             "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)["choices"][0]["message"]["content"]


def call_claude_haiku(user_prompt):
    command = ["claude", "-p", "--model", "haiku", "--system-prompt", SYSTEM_PROMPT, "--tools", "",
               "--no-session-persistence", "--disable-slash-commands", "--setting-sources", "", "--output-format", "json"]
    no_window = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    finished = subprocess.run(command, input=user_prompt, capture_output=True, text=True, encoding="utf-8", timeout=180,
                              creationflags=no_window)
    if finished.returncode != 0:
        raise RuntimeError(f"claude exited {finished.returncode}: {finished.stderr[:200]}")
    return json.loads(finished.stdout)["result"]


def judge_family():
    return "groq" if os.environ.get("GROQ_API_KEY") else "claude-haiku SAME-FAMILY"


def judge_one(assistant_text, jim_text, cache):
    key = judge_key(assistant_text, jim_text)
    if key in cache:
        return cache[key]
    call = call_groq if os.environ.get("GROQ_API_KEY") else call_claude_haiku
    prompt = build_user_prompt(assistant_text, jim_text)
    for _attempt in range(3):
        try:
            answers, parsed_ok = parse_answers(call(prompt))
        except Exception:
            continue
        if parsed_ok:
            cache[key] = answers
            append_cache(key, answers)
            return answers
    return None


SHOUT_MARKER = re.compile(r"[!?]{3,}|\?!|!\?")


def has_shout_marker(jim_text):
    return bool(SHOUT_MARKER.search(jim_text))


def with_shout_marker(answers, jim_text):
    if answers is None or not has_shout_marker(jim_text):
        return answers
    return {**answers, "q4": True}


def judge_many(pairs, workers=8):
    cache = load_cache()
    results = [None] * len(pairs)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(judge_one, assistant, jim, cache): index for index, (assistant, jim) in enumerate(pairs)}
        for future in concurrent.futures.as_completed(futures):
            results[futures[future]] = future.result()
    return [with_shout_marker(answers, pairs[index][1]) for index, answers in enumerate(results)]


def likert(answers):
    if answers["q4"] and (answers["q1"] or answers["q2"]):
        return 1
    if answers["q1"] or answers["q2"] or answers["q4"]:
        return 2
    if answers["q5"]:
        return 5
    return 4 if answers["q6"] else 3


def is_friction(answers):
    return bool(answers["q1"] or answers["q2"] or answers["q4"])


def is_confusion(answers):
    return bool(answers["q3"])


def line_message(path, wanted_line):
    for line_index, record in read_session(path):
        if line_index == wanted_line:
            text = content_text((record.get("message") or {}).get("content")).strip()
            return text
    return ""


def previous_assistant_for_line(path, wanted_line):
    previous = ""
    for line_index, record in read_session(path):
        if line_index >= wanted_line:
            break
        if record.get("type") == "assistant" and not record.get("isSidechain"):
            text = content_text((record.get("message") or {}).get("content"))
            if text.strip():
                previous = text
    return previous[:600]


def load_known_cases():
    rows = []
    for path in CASES_FILES:
        with open(path, encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle)
    return rows


def pick_own_cases(rows):
    """3 of Jim's own cases: two fails (one swearing at the assistant, one confusion) and one success."""
    wanted = {"fuck you that I hate you saying that": True, "what profile?": False, "very smoothly": False}
    picked = []
    for row in rows:
        if row["jim"] in wanted and all(row["jim"] != p["jim"] for p in picked):
            picked.append({"assistant": row["said"], "jim": row["jim"], "expect_friction": wanted[row["jim"]],
                           "expect_confusion": row["jim"] == "what profile?", "expect_praise": row["jim"] == "very smoothly"})
    return picked


LABELS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jim_labels.jsonl")


def load_jim_labels():
    if not os.path.exists(LABELS_PATH):
        return []
    with open(LABELS_PATH) as handle:
        return [json.loads(line) for line in handle if line.strip()]


def selftest():
    main_path = f"{PROJECTS}/-home-deploy-workspace-small-house/{SMALL_HOUSE_MAIN}"
    cases = []
    for line in KNOWN_ANGRY:
        cases.append({"label": f"angry@{line}", "assistant": previous_assistant_for_line(main_path, line),
                      "jim": line_message(main_path, line), "expect_friction": True})
    for line in KNOWN_HAPPY:
        cases.append({"label": f"happy@{line}", "assistant": previous_assistant_for_line(main_path, line),
                      "jim": line_message(main_path, line), "expect_friction": False})
    for row in load_jim_labels():
        cases.append({"label": f"jim@{row['line']}", "assistant": previous_assistant_for_line(main_path, row["line"]),
                      "jim": line_message(main_path, row["line"]), "expect_friction": row["friction"], "jim_likert": row.get("likert")})
    for row in pick_own_cases(load_known_cases()):
        cases.append({"label": f"own:{row['jim'][:20]}", **{k: row[k] for k in ("assistant", "jim", "expect_friction")}})
    answers = judge_many([(case["assistant"], case["jim"]) for case in cases], workers=4)
    agree = 0
    positives_found = happy_left_alone = 0
    for case, answer in zip(cases, answers):
        verdict = is_friction(answer) if answer else None
        right = verdict == case["expect_friction"]
        agree += right
        if right and case["expect_friction"]:
            positives_found += 1
        if right and case["label"].startswith("happy"):
            happy_left_alone += 1
        print(f"{'ok ' if right else 'BAD'} {case['label']:28} friction={verdict} likert={likert(answer) if answer else None} jim_likert={case.get('jim_likert')} answers={answer}")
    print(f"judge={judge_family()} angry_found={sum(1 for c, a in zip(cases, answers) if c['label'].startswith('angry') and a and is_friction(a))}/6 "
          f"happy_left_alone={happy_left_alone}/7 own={sum(1 for c in cases if c['label'].startswith('own:'))} jim_labels={sum(1 for c in cases if c['label'].startswith('jim@'))} cases={len(cases)}")
    print(f"knowns agree {agree}")
    return 0 if agree >= 14 else 1


def draw_sample(messages, seed, cap):
    ordered = sorted(messages, key=lambda m: (m["session"], m["line"]))
    if len(ordered) <= cap:
        return ordered
    return random.Random(seed).sample(ordered, cap)


def drop_repeated_messages(messages):
    seen = set()
    unique = []
    for message in messages:
        key = (message["day"], message["jim"][:300])
        if key is not None and key in seen:
            continue
        seen.add(key)
        unique.append(message)
    return unique


def collect_seat(seat):
    summaries = [summarise_session(seat, path) for path in seat_session_files(seat)]
    merged = {"jim": [], "interrupts": [], "tool_results": [], "models": [], "assistant_by_day": Counter(), "final_words": []}
    for summary in summaries:
        for key in ("jim", "interrupts", "tool_results", "models", "final_words"):
            merged[key].extend(summary[key])
        merged["assistant_by_day"].update(summary["assistant_by_day"])
    merged["jim"] = drop_repeated_messages([m for m in merged["jim"] if in_window(m["day"])])
    return merged


def permutation_p(day_labelled_flags, before_days, after_days, observed_ratio, shuffles=10000, seed=SEED):
    """Shuffle period labels across messages (day labels permuted at message level) and count ratios >= observed."""
    flags = [flag for _day, flag in day_labelled_flags]
    labels = [day in after_days for day, _flag in day_labelled_flags]
    n_after = sum(labels)
    if n_after == 0 or n_after == len(flags):
        return None
    rng = random.Random(seed)
    at_least = 0
    total = len(flags)
    for _ in range(shuffles):
        shuffled = labels[:]
        rng.shuffle(shuffled)
        after_flags = sum(f for f, is_after in zip(flags, shuffled) if is_after)
        before_flags = sum(flags) - after_flags
        before_rate = before_flags / (total - n_after)
        after_rate = after_flags / n_after
        ratio = after_rate / before_rate if before_rate else (float("inf") if after_rate else 1.0)
        if ratio >= observed_ratio - 1e-12:
            at_least += 1
    return (at_least + 1) / (shuffles + 1)


def rate(flags):
    return sum(flags) / len(flags) if flags else float("nan")


def analyse():
    cache_before = len(load_cache())
    seat_rows = {}
    secondary = {}
    for seat in SEATS:
        collected = collect_seat(seat)
        before = [m for m in collected["jim"] if m["day"] in BEFORE_DAYS]
        after = [m for m in collected["jim"] if m["day"] in AFTER_DAYS]
        sample = draw_sample(before, SEED, CAP_PER_PERIOD) + draw_sample(after, SEED, CAP_PER_PERIOD)
        verdicts = judge_many([(m["assistant"], m["jim"]) for m in sample])
        usable = [(m, a) for m, a in zip(sample, verdicts) if a is not None]
        seat_rows[seat] = {"n_before_all": len(before), "n_after_all": len(after), "scored": usable,
                           "unjudged": len(sample) - len(usable)}
        secondary[seat] = collected
        print(f"{seat}: jim before={len(before)} after={len(after)} sampled={len(sample)} unjudged={len(sample) - len(usable)}", flush=True)
    print(f"judge={judge_family()} cache_before={cache_before} cache_after={len(load_cache())}")
    changed_seats = []
    for seat in SEATS:
        usable = seat_rows[seat]["scored"]
        before_flags = [is_friction(a) for m, a in usable if m["day"] in BEFORE_DAYS]
        after_flags = [is_friction(a) for m, a in usable if m["day"] in AFTER_DAYS]
        before_rate, after_rate = rate(before_flags), rate(after_flags)
        if not before_flags or not after_flags:
            print(f"SEAT {seat} before=n/a after=n/a ratio=n/a p=n/a changed=no (n_before={len(before_flags)} n_after={len(after_flags)})")
            continue
        ratio = after_rate / before_rate if before_rate else (float("inf") if after_rate else 1.0)
        p_value = permutation_p([(m["day"], is_friction(a)) for m, a in usable], BEFORE_DAYS, AFTER_DAYS, ratio) if ratio >= 1.5 else 1.0
        is_thin = len(before_flags) < THIN_BELOW or len(after_flags) < THIN_BELOW
        changed = ratio >= 1.5 and p_value is not None and p_value < 0.05 and not is_thin
        if changed:
            changed_seats.append(seat)
        confusion_before = rate([is_confusion(a) for m, a in usable if m["day"] in BEFORE_DAYS])
        confusion_after = rate([is_confusion(a) for m, a in usable if m["day"] in AFTER_DAYS])
        print(f"SEAT {seat} before={before_rate:.3f} after={after_rate:.3f} ratio={ratio:.2f} p={p_value if p_value is None else round(p_value, 4)} "
              f"changed={'yes' if changed else 'no'}{' THIN' if is_thin else ''} (n_before={len(before_flags)} n_after={len(after_flags)} of {seat_rows[seat]['n_before_all']}/{seat_rows[seat]['n_after_all']}; confusion {confusion_before:.3f}->{confusion_after:.3f})")
    print(f"VERDICT {verdict_word(changed_seats)}" + ("" if verdict_word(changed_seats) != "MIXED" else " " + ",".join(changed_seats)))
    print_secondary(secondary)
    return 0


def verdict_word(changed_seats):
    if len(changed_seats) >= 4:
        return "GLOBAL"
    if changed_seats == ["small-house"]:
        return "ONE-SESSION"
    if not changed_seats:
        return "NONE"
    return "MIXED"


def period_of(day):
    return "before" if day in BEFORE_DAYS else "after" if day in AFTER_DAYS else None


def tool_error_verdict(tool_results):
    windowed = [(day, is_error) for day, is_error in tool_results if period_of(day)]
    before = [e for d, e in windowed if period_of(d) == "before"]
    after = [e for d, e in windowed if period_of(d) == "after"]
    if not before or not after or rate(before) == 0:
        return f"tool_err_test=n/a (n_before={len(before)} n_after={len(after)})"
    ratio = rate(after) / rate(before)
    p_value = permutation_p(windowed, BEFORE_DAYS, AFTER_DAYS, ratio) if ratio >= 1.5 else 1.0
    changed = ratio >= 1.5 and p_value is not None and p_value < 0.05
    return f"tool_err_ratio={ratio:.2f} p={round(p_value, 4) if p_value is not None else None} tool_err_changed={'yes' if changed else 'no'} (n_before={len(before)} n_after={len(after)})"


def print_secondary(secondary):
    for seat in SEATS:
        data = secondary[seat]
        per = {"before": defaultdict(list), "after": defaultdict(list)}
        n_jim = {"before": 0, "after": 0}
        for m in data["jim"]:
            if period_of(m["day"]):
                n_jim[period_of(m["day"])] += 1
        n_interrupt = {"before": 0, "after": 0}
        for day in data["interrupts"]:
            if period_of(day):
                n_interrupt[period_of(day)] += 1
        errors = {"before": [], "after": []}
        for day, is_error in data["tool_results"]:
            if period_of(day):
                errors[period_of(day)].append(is_error)
        words = {"before": [], "after": []}
        for day, count in data["final_words"]:
            if period_of(day):
                words[period_of(day)].append(count)
        assistant_count = {"before": sum(data["assistant_by_day"][d] for d in BEFORE_DAYS),
                           "after": sum(data["assistant_by_day"][d] for d in AFTER_DAYS)}
        cells = []
        for period in ("before", "after"):
            jim_count = n_jim[period]
            cells.append(f"{period}: jim={jim_count} interrupts/100={100 * n_interrupt[period] / jim_count if jim_count else float('nan'):.1f} "
                         f"tool_err={rate(errors[period]):.3f} median_words={statistics.median(words[period]) if words[period] else float('nan')} "
                         f"asst_per_jim={assistant_count[period] / jim_count if jim_count else float('nan'):.1f}")
        print(f"SECONDARY {seat} | " + " | ".join(cells) + " | " + tool_error_verdict(data["tool_results"]))
        mix = defaultdict(Counter)
        for day, model in data["models"]:
            mix[day][model] += 1
        for day in sorted(mix):
            if in_window(day):
                print(f"MODELMIX {seat} {day} " + " ".join(f"{model}={count}" for model, count in mix[day].most_common()))


def extract_counts():
    for seat in SEATS:
        collected = collect_seat(seat)
        by_day = Counter(m["day"] for m in collected["jim"])
        print(seat, len(collected["jim"]), dict(sorted(by_day.items())))
    return 0


COMMANDS = {"selftest": selftest, "analyse": analyse, "extract": extract_counts}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(f"usage: jim_friction.py {'|'.join(COMMANDS)}")
    sys.exit(COMMANDS[sys.argv[1]]())
