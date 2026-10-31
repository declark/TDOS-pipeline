#!/usr/bin/env python3
"""Check a long-cut list against the hard limits and targets in config/SKILL.md.

The select-cuts and review-cuts skills both run this instead of writing a
throwaway check each time, so the rules are measured the same way every run.
It never touches Resolve and never edits the cut list.

FAIL lines are hard limits (overlaps, the 6s film-exposure ceiling, the 6s
us-only cap, more than 4 panel segments in a row) and make the exit code 1.
WARN lines are targets and judgement calls (runtime, layout mix, rhythm,
timestamps off a word boundary) for whoever is reviewing the cut to weigh.

A shorts file (cuts/<episode>.shorts.json) is checked short by short against
config/SHORTS.md instead: the same film-exposure ceiling, the 35s length limit
and the two shorts layouts. src/render_shorts.py won't render a short that fails.

Usage:
    python src/check_cuts.py --cuts cuts/<episode>.json
    python src/check_cuts.py --cuts cuts/<episode>.json --verbose
    python src/check_cuts.py --cuts cuts/<episode>.shorts.json
"""

import argparse
import bisect
import json
import os
import sys

from build_timeline import (
    BuildError,
    DEFAULT_CONFIG,
    is_shorts_file,
    load_config,
    load_cuts,
    load_shorts,
    resolve_fps,
    validate_cuts,
)

# --- the numbers from config/SKILL.md ----------------------------------------
# Keep these in step with that file; it is the source of truth.

FILM_AUDIO = {"panel", "pip_circles", "hosts_movie_audio"}
US_ONLY = {"hosts_full", "hosts_movie_audio"}
MUTED_OVER_FILM = {"panel_hosts_only", "pip_circles_hosts_only"}

RUNTIME_MINUTES = (35, 50)
MIN_SOURCE_SKIP = 2.0      # a smaller gap doesn't break a film-audio run
FILM_RUN_DEFAULT = 4.0
FILM_RUN_CEILING = 6.0
US_ONLY_CAP = 6.0
INTRO_MAX = 20.0
MAX_PANEL_STREAK = 4
PANEL_SHARE = (60, 70)
MUTED_SHARE = (15, 25)
PIP_SHARE_MAX = 15
US_ONLY_SHARE_MAX = 8

# The numbers from config/SHORTS.md.
SHORT_LAYOUTS = {"panel", "panel_hosts_only"}
SHORT_SECONDS = (15, 30)
SHORT_MAX_SECONDS = 35

# Judgement thresholds for the rhythm and timestamp warnings.
NEAR_EQUAL_SECONDS = 0.2   # three in a row within this of each other
PATTERN_REPEATS = 3        # a layout sequence repeated this many times
HANDLE_SLACK = 0.3         # the ~0.25s handle, plus rounding
WORD_EDGE = 0.05           # this far inside a word counts as mid-word
EPSILON = 1e-6


def seg_label(cut):
    return "segment {}".format(cut["index"] + 1)


def span_label(cuts):
    if len(cuts) == 1:
        return seg_label(cuts[0])
    return "segments {}-{}".format(cuts[0]["index"] + 1, cuts[-1]["index"] + 1)


def duration(cut):
    return cut["end"] - cut["start"]


def film_runs(cuts):
    """Group film-audio segments into continuous runs (config/SKILL.md BREAKS)."""
    runs, current = [], []
    for cut in cuts:
        if cut["layout"] not in FILM_AUDIO:
            if current:
                runs.append(current)
            current = []
            continue
        # abs(): a short may jump backwards in the source, which breaks a run too.
        if current and abs(cut["start"] - current[-1]["end"]) >= MIN_SOURCE_SKIP - EPSILON:
            runs.append(current)
            current = []
        current.append(cut)
    if current:
        runs.append(current)
    return runs


def layout_runs(cuts, layouts):
    """Consecutive segments whose layout is in `layouts`, in list order."""
    runs, current = [], []
    for cut in cuts:
        if cut["layout"] in layouts:
            current.append(cut)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def check_film_exposure(cuts, fails, warns):
    runs = film_runs(cuts)
    over_default = []
    for run in runs:
        length = sum(duration(c) for c in run)
        if length > FILM_RUN_CEILING + EPSILON:
            fails.append("{}: {:.2f}s of continuous film audio, over the {:g}s ceiling.".format(
                span_label(run), length, FILM_RUN_CEILING))
        elif length > FILM_RUN_DEFAULT + EPSILON:
            over_default.append((run, length))
    if over_default:
        warns.append(
            "{} of {} film-audio runs go past the {:g}s default; each needs its why "
            "in `reason`, and they should be the exception: {}.".format(
                len(over_default), len(runs), FILM_RUN_DEFAULT,
                ", ".join("{} ({:.1f}s)".format(span_label(r), n) for r, n in over_default)))


def check_us_only(cuts, fails, warns):
    for run in layout_runs(cuts, US_ONLY):
        length = sum(duration(c) for c in run)
        is_intro = run[0]["index"] == 0
        is_outro = run[-1]["index"] == len(cuts) - 1
        if is_intro and length > INTRO_MAX + EPSILON:
            warns.append("intro ({}) runs {:.1f}s; it should be under {:g}s.".format(
                span_label(run), length, INTRO_MAX))
        if not (is_intro or is_outro) and length > US_ONLY_CAP + EPSILON:
            fails.append("{}: {:.2f}s of us-only footage, over the {:g}s cap.".format(
                span_label(run), length, US_ONLY_CAP))


def check_panel_streak(cuts, fails):
    for run in layout_runs(cuts, {"panel"}):
        if len(run) > MAX_PANEL_STREAK:
            fails.append("{}: {} `panel` segments in a row, max is {}.".format(
                span_label(run), len(run), MAX_PANEL_STREAK))


def layout_shares(cuts):
    total = sum(duration(c) for c in cuts)
    seconds = {}
    for cut in cuts:
        seconds[cut["layout"]] = seconds.get(cut["layout"], 0.0) + duration(cut)
    return total, {layout: 100.0 * s / total for layout, s in seconds.items()}


def check_layout_mix(cuts, warns):
    total, shares = layout_shares(cuts)

    def share(layouts):
        return sum(shares.get(layout, 0.0) for layout in layouts)

    rows = [
        ("panel", share({"panel"}), "{}-{}%".format(*PANEL_SHARE)),
        ("panel_hosts_only + pip_circles_hosts_only", share(MUTED_OVER_FILM),
         "~{}-{}%".format(*MUTED_SHARE)),
        ("pip_circles", share({"pip_circles"}), "<= ~{}%".format(PIP_SHARE_MAX)),
        ("hosts_full + hosts_movie_audio", share(US_ONLY), "<= ~{}%".format(US_ONLY_SHARE_MAX)),
    ]

    minutes = total / 60.0
    if not RUNTIME_MINUTES[0] <= minutes <= RUNTIME_MINUTES[1]:
        warns.append("runtime is {:.1f} min; the target is {}-{} min.".format(
            minutes, *RUNTIME_MINUTES))
    panel = rows[0][1]
    if not PANEL_SHARE[0] <= panel <= PANEL_SHARE[1]:
        warns.append("`panel` is {:.1f}% of runtime; the target is {}-{}%.".format(
            panel, *PANEL_SHARE))
    if rows[2][1] > PIP_SHARE_MAX:
        warns.append("`pip_circles` is {:.1f}% of runtime; the target is <= ~{}%.".format(
            rows[2][1], PIP_SHARE_MAX))
    if rows[3][1] > US_ONLY_SHARE_MAX:
        warns.append("us-only layouts are {:.1f}% of runtime; the target is <= ~{}%.".format(
            rows[3][1], US_ONLY_SHARE_MAX))
    return total, rows


def check_rhythm(cuts, warns):
    """Metronome stretches: near-equal lengths and repeating layout sequences."""
    equal, i = [], 0
    while i < len(cuts):
        j = i + 1
        low = high = duration(cuts[i])
        while j < len(cuts):
            d = duration(cuts[j])
            if max(high, d) - min(low, d) > NEAR_EQUAL_SECONDS:
                break
            low, high = min(low, d), max(high, d)
            j += 1
        if j - i >= 3:
            equal.append("{} (~{:.1f}s each)".format(span_label(cuts[i:j]), (low + high) / 2))
            i = j
        else:
            i += 1
    if equal:
        warns.append("three or more segments in a row of nearly the same length: {}.".format(
            ", ".join(equal)))

    layouts = [c["layout"] for c in cuts]
    patterns, i = [], 0
    while i < len(layouts):
        found = None
        for period in (2, 3, 4):
            unit = layouts[i:i + period]
            if len(unit) < period or len(set(unit)) < 2:
                continue
            repeats = 1
            while layouts[i + repeats * period:i + (repeats + 1) * period] == unit:
                repeats += 1
            if repeats >= PATTERN_REPEATS:
                found = (period, repeats, unit)
                break
        if found:
            period, repeats, unit = found
            patterns.append("{} ({} x{})".format(
                span_label(cuts[i:i + period * repeats]), " > ".join(unit), repeats))
            i += period * repeats
        else:
            i += 1
    if patterns:
        warns.append("repeating layout pattern: {}.".format(", ".join(patterns)))


# --- timestamps vs. the word-level transcripts --------------------------------


def words_paths(media_path):
    """The transcript(s) src/transcribe.py wrote beside a media file.

    A second --no-vad pass (<name>.novad.words.json) is included when present.
    """
    base = os.path.splitext(media_path)[0]
    return [p for p in (base + ".words.json", base + ".novad.words.json") if os.path.exists(p)]


def load_words(path, offset):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    words = []
    for segment in data.get("segments", []):
        for word in segment.get("words", []):
            words.append((word["start"] + offset, word["end"] + offset))
    return words


def find_media_config(cuts_path):
    """cuts/<slug>.json, cuts/<slug>.draft.json ... -> cuts/<slug>.media.json"""
    folder, name = os.path.split(cuts_path)
    return os.path.join(folder, name.split(".")[0] + ".media.json")


def check_timestamps(cuts, meta, media_path, warns, notes):
    if not os.path.exists(media_path):
        notes.append("timestamps not checked: {} not found.".format(media_path))
        return
    with open(media_path, "r", encoding="utf-8") as handle:
        media = json.load(handle)

    offset = meta.get("movie_offset_seconds", media.get("movie_offset_seconds"))
    if offset is None:
        notes.append("timestamps not checked: no movie_offset_seconds in the cut list or {}.".format(
            media_path))
        return

    ours, film = [], []
    for key, bucket, shift in (("reaction_media", ours, 0.0), ("movie_media", film, float(offset))):
        paths = words_paths(media.get(key) or "")
        if not paths:
            notes.append("timestamps not checked: no .words.json beside {} ({!r}).".format(
                key, media.get(key)))
            return
        for path in paths:
            bucket.extend(load_words(path, shift))

    boundaries = sorted(t for word in ours + film for t in word)
    ours.sort()
    our_starts = [w[0] for w in ours]

    unanchored, clipped, silent = [], [], 0
    for cut in cuts:
        # No word from either transcript inside it: a silent-reaction segment,
        # anchored on the beat's edges rather than on speech.
        if bisect.bisect_right(boundaries, cut["end"]) == bisect.bisect_left(boundaries, cut["start"]):
            silent += 1
            continue
        for side, edge in enumerate(("start", "end")):
            t = cut[edge]
            # An edge src/tighten_cuts.py moved is anchored on the waveform, a
            # handle off the first or last sound, which may be a laugh with no word.
            moved = cut.get("trimmed_from") and abs(cut["trimmed_from"][side] - t) > EPSILON
            i = bisect.bisect_left(boundaries, t)
            nearest = min(abs(boundaries[k] - t) for k in (i - 1, i) if 0 <= k < len(boundaries))
            if nearest > HANDLE_SLACK and not moved:
                unanchored.append("{} {} {:.2f} ({:.2f}s from a word)".format(
                    seg_label(cut), edge, t, nearest))
            k = bisect.bisect_right(our_starts, t) - 1
            if k >= 0 and ours[k][0] + WORD_EDGE < t < ours[k][1] - WORD_EDGE:
                clipped.append("{} {} {:.2f}".format(seg_label(cut), edge, t))

    notes.append("{} of {} segments have no transcribed words in them (silent beats); "
                 "their timestamps aren't checked.".format(silent, len(cuts)))
    if unanchored:
        warns.append(
            "{} boundaries of segments with speech aren't within {:g}s of any word "
            "boundary: {}.".format(len(unanchored), HANDLE_SLACK, "; ".join(unanchored)))
    if clipped:
        warns.append(
            "{} boundaries land inside a word in our transcript (the reaction mic also "
            "hears film dialogue, so listen before moving one): {}.".format(
                len(clipped), "; ".join(clipped)))


# --- every check, in one call ---------------------------------------------------


class InvalidCuts(Exception):
    """The cut list fails validation, so nothing else can be measured."""


def run_checks(cuts_path, config_path=DEFAULT_CONFIG, media_path=None):
    """Run every check. Returns (cuts, total_seconds, mix_rows, fails, warns, notes).

    Raises BuildError if the files can't be loaded and InvalidCuts if the cut
    list fails validation.
    """
    if is_shorts_file(cuts_path):
        raise BuildError("{} is a shorts file; this checks long cuts only.".format(cuts_path))
    config = load_config(config_path)
    cuts, meta = load_cuts(cuts_path)

    try:
        validate_cuts(cuts, config, resolve_fps(config["fps"]))
    except BuildError as error:
        # Overlaps and bad rows make every later measurement meaningless.
        raise InvalidCuts(str(error))

    fails, warns, notes = [], [], []
    check_film_exposure(cuts, fails, warns)
    check_us_only(cuts, fails, warns)
    check_panel_streak(cuts, fails)
    total, rows = check_layout_mix(cuts, warns)
    check_rhythm(cuts, warns)
    check_timestamps(cuts, meta, media_path or find_media_config(cuts_path), warns, notes)
    return cuts, total, rows, fails, warns, notes


# --- shorts ---------------------------------------------------------------------
# A short keeps the long cut's film-exposure limit (config/SHORTS.md), measured
# over its segments in the order they play.


def check_short(short, config, rate):
    """(runtime_seconds, fails, warns) for one entry from load_shorts."""
    cuts = short["cuts"]
    runtime = sum(duration(c) for c in cuts)
    fails, warns = [], []
    try:
        validate_cuts(cuts, config, rate, chronological=False)
    except BuildError as error:
        return runtime, [str(error)], warns

    wrong = sorted({c["layout"] for c in cuts} - SHORT_LAYOUTS)
    if wrong:
        fails.append("layout(s) {} aren't shorts layouts; use {}.".format(
            ", ".join(wrong), " or ".join(sorted(SHORT_LAYOUTS))))
    check_film_exposure(cuts, fails, warns)
    if runtime > SHORT_MAX_SECONDS + EPSILON:
        fails.append("runs {:.1f}s, over the {:g}s limit.".format(runtime, SHORT_MAX_SECONDS))
    elif not SHORT_SECONDS[0] <= runtime <= SHORT_SECONDS[1]:
        warns.append("runs {:.1f}s; the target is {}-{}s.".format(runtime, *SHORT_SECONDS))
    return runtime, fails, warns


def run_shorts_checks(shorts_path, config_path=DEFAULT_CONFIG):
    """[{number, name, runtime, fails, warns}] for every short in the file."""
    config = load_config(config_path)
    rate = resolve_fps(config["fps"])
    shorts, _ = load_shorts(shorts_path)
    results = []
    for short in shorts:
        runtime, fails, warns = check_short(short, config, rate)
        results.append({"number": short["number"], "name": short["name"],
                        "runtime": runtime, "fails": fails, "warns": warns})
    return results


def print_shorts_checks(path, results, verbose):
    print("{}: {} short(s)".format(path, len(results)))
    for result in results:
        print()
        print("Short {} - {}: {:.1f}s".format(result["number"], result["name"], result["runtime"]))
        for label in ("fails", "warns"):
            for line in result[label]:
                print("{}  {}".format(label[:-1].upper(), shorten(line, verbose)))
    fails = sum(len(r["fails"]) for r in results)
    print()
    print("{} hard failure(s), {} warning(s).".format(fails, sum(len(r["warns"]) for r in results)))
    return 1 if fails else 0


# --- CLI ----------------------------------------------------------------------


def shorten(line, verbose, limit=600):
    if verbose or len(line) <= limit:
        return line
    return line[:limit].rstrip() + " ... (--verbose for the full list)"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cuts", required=True,
                        help="Long-cut list to check (cuts/<episode>.json).")
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help="Timeline config, for the known layouts and fps.")
    parser.add_argument("--media", default=None,
                        help="Media config with the transcript locations. "
                             "Default: cuts/<slug>.media.json beside the cut list.")
    parser.add_argument("--verbose", action="store_true",
                        help="Don't truncate long lists of segments.")
    args = parser.parse_args(argv)

    if is_shorts_file(args.cuts):
        try:
            return print_shorts_checks(
                args.cuts, run_shorts_checks(args.cuts, args.config), args.verbose)
        except BuildError as error:
            print("error: {}".format(error), file=sys.stderr)
            return 1

    try:
        cuts, total, rows, fails, warns, notes = run_checks(args.cuts, args.config, args.media)
    except BuildError as error:
        print("error: {}".format(error), file=sys.stderr)
        return 1
    except InvalidCuts as error:
        print("FAIL  {}".format(error))
        return 1

    print("{}: {} segments, {:.1f} min".format(args.cuts, len(cuts), total / 60.0))
    print()
    print("Layout mix (share of runtime)")
    for name, share, target in rows:
        print("  {:<44}{:>6.1f}%   target {}".format(name, share, target))
    print()
    for label, lines in (("FAIL", fails), ("WARN", warns), ("NOTE", notes)):
        for line in lines:
            print("{}  {}".format(label, shorten(line, args.verbose)))
    print()
    print("{} hard failure(s), {} warning(s).".format(len(fails), len(warns)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
