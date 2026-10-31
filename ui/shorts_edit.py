"""The desktop app's shorts editor, server side.

The page edits one short as a draft and calls in here to measure it (the same
checks src/check_cuts.py runs, and the caption groups src/render_shorts.py
would draw), to read waveforms and transcript words for the timeline, and to
save it back into cuts/<slug>.shorts.json. Playback is the page's own, from the
proxies src/make_proxies.py writes.
"""

import json
import os
import shutil

import render_shorts
from build_timeline import BuildError, DEFAULT_CONFIG, load_config, resolve_fps, validate_cuts
from check_cuts import SHORT_MAX_SECONDS, SHORT_SECONDS, check_short, load_words, words_paths
from make_proxies import proxy_paths
from projects import cuts_file, shorts_path

# Times are written to the file at this precision, as the cut stages write them.
DECIMALS = 2

_cache = {}     # slug -> loaded transcripts, peaks and settings


def file_version(path):
    """Changes whenever the file is rewritten by anything."""
    stat = os.stat(path)
    return "{}:{}".format(int(stat.st_mtime_ns), stat.st_size)


def has_proxies(media):
    return all(media.get(key) and all(os.path.exists(p) for p in proxy_paths(media[key]))
               for key in ("reaction_media", "movie_media"))


def _project(slug):
    """Job, settings, transcripts and peaks for a project, loaded once."""
    path = shorts_path(slug)
    job = render_shorts.load_job(path)
    stamp = (file_version(path), json.dumps(job["media"], sort_keys=True))
    cached = _cache.get(slug)
    if cached and cached["stamp"][1] == stamp[1]:
        cached["job"], cached["stamp"] = job, stamp
        return cached

    media = job["media"]
    film_offset = job["offset"] + float(media.get("shorts_sync_nudge_seconds") or 0.0)
    words = {"us": [], "film": []}
    for key, who, shift in (("reaction_media", "us", 0.0), ("movie_media", "film", film_offset)):
        for words_path in words_paths(media[key])[:1]:
            with open(words_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            words[who] = sorted(
                (round(w["start"] + shift, 3), round(w["end"] + shift, 3), w["word"].strip())
                for segment in data.get("segments", []) for w in segment.get("words", [])
                if w["word"].strip())
    peaks = {}
    for key, who in (("reaction_media", "us"), ("movie_media", "film")):
        peaks_path = proxy_paths(media[key])[1]
        if os.path.exists(peaks_path):
            with open(peaks_path, "r", encoding="utf-8") as handle:
                peaks[who] = json.load(handle)
    _cache[slug] = cached = {
        "stamp": stamp,
        "job": job,
        "settings": render_shorts.load_settings(),
        "config": load_config(DEFAULT_CONFIG),
        "film_offset": film_offset,
        "words": words,
        "spoken": {
            "us": render_shorts.load_spoken(media["reaction_media"], 0.0),
            "film": render_shorts.load_spoken(media["movie_media"], job["offset"]),
        },
        "peaks": peaks,
    }
    return cached


def editor_view(slug, number):
    project = _project(slug)
    job, settings = project["job"], project["settings"]
    if not 1 <= number <= len(job["raw"]):
        raise ValueError("There is no short {}.".format(number))
    raw = job["raw"][number - 1]
    media = job["media"]
    short = render_shorts.prepare_short(raw, number)
    peaks = project["peaks"]
    style = settings["captions"]
    return {
        "number": number,
        "short": raw,
        "version": file_version(shorts_path(slug)),
        "proxies": has_proxies(media),
        "fps": settings["fps"],
        "film_offset": project["film_offset"],
        "hosts_crop_x": float(media.get("shorts_hosts_crop_x", settings["hosts_crop_x"])),
        "film_gain": 10 ** (settings["audio"]["film_gain_db"] / 20),
        "hosts_gain": 10 ** (settings["audio"]["hosts_gain_db"] / 20),
        "band_lines": [{"text": text, "size": size}
                       for text, size, _ in render_shorts.band_lines(settings, job, short)],
        "caption_style": {"color": style["color"], "stroke": style["stroke_color"],
                          "stroke_width": style["stroke_width"], "size": style["size"],
                          "highlight": style["highlight"], "uppercase": bool(style.get("uppercase"))},
        "frame": {
            "width": settings["width"], "height": settings["height"],
            "band": settings["text_band_height"], "film": settings["film_height"],
            "hosts": settings.get("hosts_height") or
            settings["height"] - settings["text_band_height"] - settings["film_height"],
            "safe": settings["safe_zone"], "background": settings["background"],
            "title_color": settings["title"]["color"],
        },
        "bleep": {"sound": bool(settings["bleep"]["sound"]), "tone_hz": settings["bleep"]["tone_hz"],
                  "level": 10 ** (settings["bleep"]["level_db"] / 20),
                  "pad": settings["bleep"]["pad_ms"] / 1000},
        "durations": {who: len(p["db"]) / p["rate"] for who, p in peaks.items()},
        "limits": {"target": list(SHORT_SECONDS), "max": SHORT_MAX_SECONDS},
    }


def peaks(slug, who, start, end):
    """{"rate", "start", "db": [...]} for one recording, in recording time.

    The film's peaks are read at film time and handed back on the recording's
    clock, so the page can draw both under the same clip.
    """
    project = _project(slug)
    data = project["peaks"].get("film" if who == "film" else "us")
    if not data:
        return {"rate": 25, "start": start, "db": []}
    shift = project["film_offset"] if who == "film" else 0.0
    rate = data["rate"]
    first = max(0, int((start - shift) * rate))
    last = max(first, int((end - shift) * rate) + 1)
    return {"rate": rate, "start": first / rate + shift, "db": data["db"][first:last]}


def words(slug, start, end):
    """Transcript words from both sides overlapping [start, end], in recording time."""
    project = _project(slug)
    return {who: [w for w in found if w[1] >= start and w[0] <= end]
            for who, found in project["words"].items()}


def draft_state(slug, number, raw_short):
    """What the checks and the renderer make of an unsaved draft of one short."""
    project = _project(slug)
    try:
        short = render_shorts.prepare_short(raw_short, number)
    except BuildError as error:
        return {"runtime": 0, "fails": [str(error)], "warns": [], "groups": []}
    config = project["config"]
    runtime, fails, warns = check_short(short, config, resolve_fps(config["fps"]))
    groups = []
    if not fails or all("overlap" not in f for f in fails):
        groups = [{"start": g["start"], "end": g["end"], "who": g["who"],
                   "words": [[at, text] for at, text in g["words"]]}
                  for g in render_shorts.preview_groups(short, project["spoken"], project["settings"])]
    return {"runtime": runtime, "fails": fails, "warns": warns, "groups": groups}


def find_swears(slug, number, raw_short):
    """{segment index: [bleep, ...]} for the listed swears the transcripts hear in a draft."""
    project = _project(slug)
    short = render_shorts.prepare_short(raw_short, number)
    return {str(index): found for index, found in
            render_shorts.find_swears(short, project["spoken"], project["settings"]).items()}


def clean_draft(raw_short):
    """The draft as it should be written: times rounded, captions kept in their clip."""
    short = dict(raw_short)
    segments = []
    for segment in raw_short.get("segments") or []:
        segment = dict(segment)
        segment["start"] = round(float(segment["start"]), DECIMALS)
        segment["end"] = round(float(segment["end"]), DECIMALS)
        trimmed = segment.get("trimmed_from")
        if trimmed is not None and not isinstance(trimmed, list):
            segment.pop("trimmed_from")
        if isinstance(segment.get("captions"), list):
            captions = []
            for caption in segment["captions"]:
                caption = dict(caption)
                caption["text"] = " ".join(str(caption.get("text") or "").split())
                if not caption["text"]:
                    continue
                caption["start"] = round(float(caption["start"]), DECIMALS)
                caption["end"] = round(float(caption["end"]), DECIMALS)
                captions.append(caption)
            segment["captions"] = sorted(captions, key=lambda c: c["start"])
        if "bleeps" in segment:
            bleeps = []
            for bleep in segment["bleeps"] or []:
                start = round(max(float(bleep["start"]), segment["start"]), DECIMALS)
                end = round(min(float(bleep["end"]), segment["end"]), DECIMALS)
                if end > start:
                    bleeps.append({"who": "film" if bleep.get("who") == "film" else "us",
                                   "start": start, "end": end})
            if bleeps:
                segment["bleeps"] = sorted(bleeps, key=lambda b: b["start"])
            else:
                segment.pop("bleeps")
        segments.append(segment)
    short["segments"] = segments
    return short


def save_short(slug, number, raw_short, version):
    """Write one short back into the shorts file. Returns the file's new version."""
    path = shorts_path(slug)
    if file_version(path) != version:
        raise ValueError("The shorts file changed since the editor opened it (a revision or "
                         "Tighten ran). Reload the editor to pick up the new version.")
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not 1 <= number <= len(data.get("shorts") or []):
        raise ValueError("There is no short {}.".format(number))

    short = clean_draft(raw_short)
    prepared = render_shorts.prepare_short(short, number)
    config = load_config(DEFAULT_CONFIG)
    validate_cuts(prepared["cuts"], config, resolve_fps(config["fps"]), chronological=False)

    shutil.copyfile(path, cuts_file(slug, ".shorts.prev.json"))
    data["shorts"][number - 1] = short
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    _cache.pop(slug, None)
    return file_version(path)
