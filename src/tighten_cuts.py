#!/usr/bin/env python3
"""Cut the dead air out of a cut list, from the waveform and the picture.

Dead air is a stretch where nothing is heard - nobody talking or laughing,
and in a film-audio segment of a short, no film dialogue or sound either -
and nothing much moves on screen. This finds it and edits it out:

  - a silent, still lead-in or tail is trimmed, keeping a short handle before
    the first sound and after the last so nothing sounds clipped;
  - a silent, still pause inside a segment is cut out, which splits the
    segment in two (a jump cut), keeping a short beat of the pause either side.

"Still" is measured, not assumed: frames are sampled across the segment and
compared, and a stretch where the visible picture changes a lot (sustained
action in the film, one of us jumping) counts as something happening, so the
silence there is kept - it's a reaction. Transcribed words count as sound
too, whatever the meter says, so a quiet word is never cut into.

Two profiles, chosen by the file:

  - A long cut (cuts/<slug>.json) only touches the layouts where our audio is
    the only audio (`panel_hosts_only`, `pip_circles_hosts_only`,
    `hosts_full`), gently: 0.25s handles, pauses over 1s.
  - A shorts file (cuts/<slug>.shorts.json) touches every segment. In `panel`
    the film's audio and dialogue count as sound alongside ours. It cuts much
    harder - config/SHORTS.md wants every pause over ~0.4s gone - so the
    shorts feel fast.

A segment with no sound in it at all is left alone and listed: that's a
silent reaction chosen on purpose, and a human should judge it.

    python src/tighten_cuts.py --cuts cuts/<slug>.json --dry-run
    python src/tighten_cuts.py --cuts cuts/<slug>.json
    python src/tighten_cuts.py --cuts cuts/<slug>.shorts.json

The long cut runs it after review-cuts and before build_timeline; shorts run
it after select-shorts and before render_shorts. The file is rewritten in
place; the version before is kept as cuts/<slug>.pretighten.json (or
.pretighten.shorts.json). Each segment it changed gets "trimmed_from":
[start, end], its span before tightening, so check_cuts knows those edges sit
on sound rather than on a transcribed word. Running it again on a tightened
file changes little or nothing. The thresholds are the "tighten" block in
config/timeline.json, with "shorts" inside it overriding them for shorts.

Needs PyAV and numpy (requirements-transcribe.txt). No ffmpeg, no Resolve.
"""

import argparse
import datetime
import json
import os
import shutil
import sys

from build_timeline import BuildError, DEFAULT_CONFIG, load_config
from check_cuts import find_media_config, load_words, words_paths

# layout -> (what the viewer sees, what the viewer hears)
LONG_CUT_LAYOUTS = {
    "panel_hosts_only": (("film", "hosts"), ("hosts",)),
    "pip_circles_hosts_only": (("film", "hosts"), ("hosts",)),
    "hosts_full": (("hosts",), ("hosts",)),
}
SHORTS_LAYOUTS = {
    "panel": (("film", "hosts"), ("hosts", "film")),
    "panel_hosts_only": (("film", "hosts"), ("hosts",)),
}

DEFAULTS = {
    "window_ms": 20,             # loudness is measured in windows this long
    "floor_samples": 120,        # one-second samples across each file, for its floor
    "floor_percentile": 10,      # a file's noise floor is this percentile of its levels
    "sound_above_floor_db": 18,  # our mics: louder than floor + this is sound
    "film_sound_above_floor_db": 10,  # the film: its quiet is room tone and score, not silence
    "sound_db_range": [-60, -30],  # thresholds are clamped to this range, in dBFS
    "min_sound_ms": 80,          # a click shorter than this isn't sound
    "edge_handle_seconds": 0.25,  # kept before the first sound and after the last
    "min_trim_seconds": 0.2,     # don't bother trimming an edge by less
    "min_pause_seconds": 1.0,    # an inner silence at least this long is cut out
    "film_min_pause_seconds": 1.0,  # ... in a segment with film audio, where the cut jumps the film
    "pause_keep_seconds": 0.25,  # ... keeping this much of it on each side
    "min_piece_seconds": 0.6,    # never leave a piece shorter than this
    "motion_fps": 10,            # pictures sampled per second for the motion check
    "motion_smooth_seconds": 0.5,  # motion is the median over this, so a hard cut alone isn't action
    "film_motion": 12.0,         # mean pixel change (0-255) that counts as action
    "hosts_motion": 4.0,
    "motion_hold_seconds": 0.4,  # action keeps the moment "busy" this long either side
    "word_pad_seconds": 0.05,    # transcribed words, widened by this
}

# Shorts are cut much tighter (config/SHORTS.md TIMING).
SHORTS_DEFAULTS = {
    "edge_handle_seconds": 0.1,
    "min_trim_seconds": 0.08,
    "min_pause_seconds": 0.4,
    "film_min_pause_seconds": 0.8,
    "pause_keep_seconds": 0.1,
    "min_piece_seconds": 0.7,
    "motion_hold_seconds": 0.2,
    # Only film dialogue or a real hit (a scream, a bang) holds a moment open;
    # quiet score and room tone under a still shot is dead air in a short.
    "film_sound_above_floor_db": 16,
}

MOTION_SIZE = (64, 36)
EPSILON = 1e-6


def load_settings(config_path, shorts=False):
    config = config_path if isinstance(config_path, dict) else load_config(config_path)
    block = dict(config.get("tighten") or {})
    overrides = block.pop("shorts", None) or {}
    settings = dict(DEFAULTS)
    settings.update(block)
    if shorts:
        settings.update(SHORTS_DEFAULTS)
        settings.update(overrides)
    return settings


# --- the cut list, as raw JSON so every field survives -------------------------


def load_raw(path):
    """(data, groups, is_shorts): the file's JSON, and every list of segment dicts in it.

    A long cut has one group; a shorts file has one per short. Each group is
    edited in place, so writing `data` back writes the result.
    """
    if os.path.splitext(path)[1].lower() != ".json":
        raise BuildError("{}: tighten works on .json cut lists only.".format(path))
    if not os.path.exists(path):
        raise BuildError("Cut list not found: {}".format(path))
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        data = {"segments": data}
    if isinstance(data.get("shorts"), list):
        groups = [s["segments"] for s in data["shorts"] if isinstance(s.get("segments"), list)]
        return data, groups, True
    for key in ("segments", "cuts", "edit"):
        if isinstance(data.get(key), list):
            return data, [data[key]], False
    raise BuildError("{}: no segments found.".format(path))


def load_media(cuts_path, data):
    media_path = find_media_config(cuts_path)
    if not os.path.exists(media_path):
        raise BuildError("Project config not found: {}".format(media_path))
    with open(media_path, "r", encoding="utf-8") as handle:
        media = json.load(handle)
    for key in ("reaction_media", "movie_media"):
        if not media.get(key) or not os.path.exists(media[key]):
            raise BuildError("{}: {} not found ({!r}).".format(media_path, key, media.get(key)))
    offset = data.get("movie_offset_seconds", media.get("movie_offset_seconds"))
    if offset is None:
        raise BuildError("No movie_offset_seconds in the cut list or {}.".format(media_path))
    return media, float(offset)


# --- measuring one segment ---------------------------------------------------------


def loudness(clip, start, end, window):
    """dBFS per `window` seconds of a clip's audio over [start, end)."""
    import numpy
    from render_shorts import AUDIO_RATE

    per = max(1, int(round(window * AUDIO_RATE)))
    count = int(round((end - start) / window))
    samples = clip.samples(start, count * per).mean(axis=1)
    power = (samples[:count * per].reshape(count, per) ** 2).mean(axis=1)
    return 10 * numpy.log10(numpy.maximum(power, 1e-12))


def motion(clip, start, end, fps, smooth=1):
    """Mean absolute pixel change between pictures 1/fps apart, one per sample.

    The first sample has nothing to compare with and scores 0. With `smooth`
    over 1, each score is the median of that many around it: sustained action
    stays, a single hard cut between two still shots drops out.
    """
    import numpy

    count = max(1, int(round((end - start) * fps)))
    scores, previous = [], None
    for frame in clip.frames(start, count, fps):
        small = frame.reformat(width=MOTION_SIZE[0], height=MOTION_SIZE[1],
                               format="gray").to_ndarray().astype(numpy.int16)
        scores.append(0.0 if previous is None else float(numpy.abs(small - previous).mean()))
        previous = small
    scores = numpy.array(scores)
    if smooth > 1 and len(scores) > 1:
        half = smooth // 2
        padded = numpy.pad(scores, (half, smooth - 1 - half), mode="edge")
        scores = numpy.median(numpy.lib.stride_tricks.sliding_window_view(padded, smooth), axis=1)
    return scores


def spread(mask, steps):
    """Widen every True run in a boolean array by `steps` either side."""
    import numpy

    if steps <= 0 or not mask.any():
        return mask
    kernel = numpy.ones(2 * steps + 1, dtype=int)
    return numpy.convolve(mask.astype(int), kernel, mode="same") > 0


def drop_short_runs(mask, steps):
    """Clear True runs shorter than `steps` windows."""
    out = mask.copy()
    for a, b in runs(mask, True):
        if b - a < steps:
            out[a:b] = False
    return out


def runs(mask, value):
    """[(first, last_exclusive)] of the runs in `mask` equal to `value`."""
    found, i = [], 0
    while i < len(mask):
        if bool(mask[i]) == value:
            j = i
            while j < len(mask) and bool(mask[j]) == value:
                j += 1
            found.append((i, j))
            i = j
        else:
            i += 1
    return found


class Segment:
    """One segment's measurements, on a grid of `window` seconds."""

    def __init__(self, cut, visible, audible, window):
        self.cut = cut
        self.start, self.end = float(cut["start"]), float(cut["end"])
        self.visible, self.audible = visible, audible
        self.window = window
        self.levels = {}      # source -> dBFS per window
        self.busy = None      # picture changing a lot, per window
        self.words = None     # a transcribed word that's heard here, per window
        self.heard = False    # set by plan(): any sound at all

    def measure(self, clips, film_offset, words, settings):
        import numpy

        window = self.window
        length = self.end - self.start

        def at(source):
            return self.start - (film_offset if source == "film" else 0.0)

        for source in self.audible:
            self.levels[source] = loudness(clips[source], at(source), at(source) + length, window)
        n = min(len(level) for level in self.levels.values())
        self.levels = {source: level[:n] for source, level in self.levels.items()}
        times = self.start + (numpy.arange(n) + 0.5) * window

        self.busy = numpy.zeros(n, dtype=bool)
        fps = settings["motion_fps"]
        smooth = max(1, int(round(settings["motion_smooth_seconds"] * fps)))
        for source in self.visible:
            scores = motion(clips[source], at(source), at(source) + length, fps, smooth)
            limit = settings["film_motion" if source == "film" else "hosts_motion"]
            # Each score is the change over the 1/fps before its sample.
            index = numpy.minimum(((times - self.start) * fps).astype(int) + 1, len(scores) - 1)
            self.busy |= scores[index] > limit
        self.busy = spread(self.busy, int(round(settings["motion_hold_seconds"] / window)))

        pad = settings["word_pad_seconds"]
        self.words = numpy.zeros(n, dtype=bool)
        for source in self.audible:
            for word_start, word_end in words[source]:
                if word_end + pad < self.start or word_start - pad > self.end:
                    continue
                a = max(0, int((word_start - pad - self.start) / window))
                b = min(n, int(numpy.ceil((word_end + pad - self.start) / window)))
                self.words[a:b] = True

    def plan(self, thresholds, settings):
        """[(start, end)] to keep, or None when the segment should stay as it is."""
        window = self.window
        steps = max(1, int(round(settings["min_sound_ms"] / 1000.0 / window)))
        sound = self.words.copy()
        for source, level in self.levels.items():
            sound |= drop_short_runs(level > thresholds[source], steps)
        self.heard = bool(sound.any())
        if not self.heard:
            return None       # a silent reaction: leave it to a human
        alive = sound | self.busy

        lively = runs(alive, True)
        first = self.start + lively[0][0] * window
        last = self.start + lively[-1][1] * window
        handle = settings["edge_handle_seconds"]
        start, end = self.start, self.end
        if first - handle - self.start >= settings["min_trim_seconds"]:
            start = first - handle
        if self.end - (last + handle) >= settings["min_trim_seconds"]:
            end = last + handle

        keep = settings["pause_keep_seconds"]
        # A jump in the film reads as a glitch more than a jump on us does.
        min_pause = settings["film_min_pause_seconds" if "film" in self.audible else "min_pause_seconds"]
        cuts = []
        for a, b in runs(alive, False):
            gap_start, gap_end = self.start + a * window, self.start + b * window
            if gap_start <= first + EPSILON or gap_end >= last - EPSILON:
                continue      # the lead-in or the tail, handled above
            if gap_end - gap_start >= min_pause:
                cuts.append((gap_start + keep, gap_end - keep))

        pieces, piece_start = [], start
        shortest = settings["min_piece_seconds"]
        for cut_from, cut_to in cuts:
            # Skip a cut that would strand a sliver either side of it.
            if cut_from - piece_start < shortest or end - cut_to < shortest:
                continue
            pieces.append((piece_start, cut_from))
            piece_start = cut_to
        pieces.append((piece_start, end))
        if end - start < shortest:
            return None
        return [(round(a, 2), round(b, 2)) for a, b in pieces]


# --- the whole list -------------------------------------------------------------------


def noise_floor(clip, levels, settings, margin):
    """(floor, threshold) in dBFS for one file.

    The floor is sampled across the whole file as well as the segments being
    edited: a shorts file's few talky seconds alone would put it far too high.
    """
    import numpy

    window = settings["window_ms"] / 1000.0
    length = float(clip.frames_in.duration or 0) / 1e6
    samples = settings["floor_samples"]
    spots = [length * (k + 0.5) / samples for k in range(samples)] if length > samples else []
    levels = numpy.concatenate(list(levels) + [loudness(clip, t, t + 1.0, window) for t in spots])
    floor = float(numpy.percentile(levels, settings["floor_percentile"]))
    low, high = settings["sound_db_range"]
    return floor, min(max(floor + margin, low), high)


def split_captions(segment, start, end):
    """A short's captions that belong to one piece of a split segment."""
    captions = segment.get("captions")
    if not isinstance(captions, list):
        return captions
    return [c for c in captions
            if float(c.get("end", end)) > start + EPSILON and float(c.get("start", start)) < end - EPSILON]


def apply(group, plans):
    """Rewrite one list of raw segments in place."""
    out = []
    for raw in group:
        pieces = plans.get(id(raw))
        if not pieces:
            out.append(raw)
            continue
        original = raw.get("trimmed_from") or [raw["start"], raw["end"]]
        for start, end in pieces:
            piece = dict(raw)
            piece["start"], piece["end"] = start, end
            piece["trimmed_from"] = original
            if "captions" in raw:
                piece["captions"] = split_captions(raw, start, end)
            out.append(piece)
    group[:] = out


def backup_path(cuts_path):
    stem = os.path.splitext(cuts_path)[0]
    if stem.endswith(".shorts"):
        return stem[:-len(".shorts")] + ".pretighten.shorts.json"
    return stem + ".pretighten.json"


def tighten(cuts_path, config_path=DEFAULT_CONFIG, dry_run=False, verbose=False):
    from render_shorts import Clip

    data, groups, is_shorts = load_raw(cuts_path)
    settings = load_settings(config_path, shorts=is_shorts)
    layouts = SHORTS_LAYOUTS if is_shorts else LONG_CUT_LAYOUTS
    media, film_offset = load_media(cuts_path, data)
    if is_shorts:
        # The renderer plays the film this much later; measure what it plays.
        film_offset += float(media.get("shorts_sync_nudge_seconds") or 0.0)
    window = settings["window_ms"] / 1000.0

    words = {"hosts": [], "film": []}
    for path in words_paths(media["reaction_media"]):
        words["hosts"] += load_words(path, 0.0)
    for path in words_paths(media["movie_media"]):
        words["film"] += load_words(path, film_offset)

    segments = [Segment(raw, *layouts[raw["layout"]], window=window)
                for group in groups for raw in group
                if raw.get("layout") in layouts
                and float(raw["end"]) - float(raw["start"]) > 2 * window]
    if not segments:
        print("{}: no segments to tighten.".format(cuts_path))
        return 0

    print("Measuring {} segment(s), {:.0f}s in all ({} profile)...".format(
        len(segments), sum(s.end - s.start for s in segments),
        "shorts" if is_shorts else "long cut"))
    clips = {"hosts": Clip(media["reaction_media"]), "film": Clip(media["movie_media"])}
    thresholds = {}
    try:
        for number, segment in enumerate(segments, start=1):
            segment.measure(clips, film_offset, words, settings)
            if number % 10 == 0 or number == len(segments):
                print("  {}/{}".format(number, len(segments)))
        for source in ("hosts", "film"):
            levels = [s.levels[source] for s in segments if source in s.levels]
            if not levels:
                continue
            margin = settings["sound_above_floor_db" if source == "hosts" else "film_sound_above_floor_db"]
            floor, thresholds[source] = noise_floor(clips[source], levels, settings, margin)
            print("{} noise floor {:.1f} dBFS; sound is anything over {:.1f} dBFS.".format(
                "Our" if source == "hosts" else "Film", floor, thresholds[source]))
    finally:
        for clip in clips.values():
            clip.close()

    plans, silent, changed = {}, [], []
    for segment in segments:
        pieces = segment.plan(thresholds, settings)
        if pieces is None:
            if not segment.heard:
                silent.append(segment)
            continue
        if pieces != [(round(segment.start, 2), round(segment.end, 2))]:
            plans[id(segment.cut)] = pieces
            changed.append((segment, pieces))
        if verbose:
            print("  {:8.2f}-{:8.2f} {:<23} {}".format(
                segment.start, segment.end, segment.cut["layout"],
                ", ".join("{} peak {:.1f} dB".format(source, float(level.max()))
                          for source, level in segment.levels.items())))

    print("")
    for segment, pieces in changed:
        kept = sum(b - a for a, b in pieces)
        print("  {:8.2f}-{:8.2f} {:<23} -> {}  (-{:.2f}s)".format(
            segment.start, segment.end, segment.cut["layout"],
            ", ".join("{:.2f}-{:.2f}".format(a, b) for a, b in pieces),
            segment.end - segment.start - kept))
    for segment in silent:
        print("  {:8.2f}-{:8.2f} {:<23} no sound at all - left as is (a silent reaction?)".format(
            segment.start, segment.end, segment.cut["layout"]))

    removed = sum(seg.end - seg.start - sum(b - a for a, b in p) for seg, p in changed)
    splits = sum(len(p) - 1 for _, p in changed)
    print("")
    print("{} of {} segment(s) tightened, {} pause(s) cut out, {:.1f}s of dead air removed.".format(
        len(changed), len(segments), splits, removed))
    if is_shorts:
        for short, group in zip(data["shorts"], groups):
            before = sum(float(s["end"]) - float(s["start"]) for s in group)
            after = before - sum(
                seg.end - seg.start - sum(b - a for a, b in p)
                for seg, p in changed if any(seg.cut is s for s in group))
            if after < before - EPSILON:
                print("  {}: {:.1f}s -> {:.1f}s".format(short.get("name", "short"), before, after))

    if dry_run:
        print("Dry run - the file was not changed.")
        return 0
    if not changed:
        return 0

    backup = backup_path(cuts_path)
    shutil.copyfile(cuts_path, backup)
    for group in groups:
        apply(group, plans)
    data["tightened"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(cuts_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2 if is_shorts else 1, ensure_ascii=False)
        handle.write("\n")
    print("Wrote {} (the version before is {}).".format(cuts_path, backup))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cuts", required=True,
                        help="Cut list or shorts file (cuts/<slug>.json, cuts/<slug>.shorts.json).")
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help="Timeline config; its \"tighten\" block. Default: %(default)s")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change without writing the file.")
    parser.add_argument("--verbose", action="store_true",
                        help="Print every measured segment's peak levels.")
    args = parser.parse_args(argv)
    try:
        return tighten(args.cuts, args.config, args.dry_run, args.verbose)
    except BuildError as error:
        print("ERROR: {}".format(error), file=sys.stderr)
        return 1
    except ImportError as error:
        print("ERROR: {} - pip install -r requirements-transcribe.txt".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
