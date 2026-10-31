#!/usr/bin/env python3
"""Render a shorts file to finished vertical MP4s, without Resolve.

Takes cuts/<episode>.shorts.json (config/SHORTS.md) and writes one 1080x1920
video per short, straight from the two media files in the project config:

    +------------------+
    | First Time Watch |   the title band: "First Time Watching" over
    | The Thing (1982) |   "<Title> (<year>)", for the whole short
    +------------------+
    |       film       |   full width, a wider film cropped at the sides
    +-- CAPTION WORDS --+   1-3 words at a time, the spoken one highlighted
    |      hosts       |   the reaction camera, cropped to fit
    +------------------+
    |                  |   black, under the apps' title and buttons
    +------------------+

    python src/render_shorts.py --cuts cuts/the-thing.shorts.json
    python src/render_shorts.py --cuts cuts/the-thing.shorts.json --short 2
    python src/render_shorts.py --cuts cuts/the-thing.shorts.json --preview

--preview writes one still per short instead of a video: quick enough to tune
the hosts crop and the text before a full render.

A short that breaks a hard limit in src/check_cuts.py (the film-exposure
ceiling, the 35s length limit) is not rendered.

Captions come from each segment's "captions" list - phrases the select-shorts
step wrote, in film and our colours - with the word timings taken from the
transcripts. A segment with no "captions" key falls back to our transcript's
words as they are.

Film time is recording time minus movie_offset_seconds. There is no Resolve
multicam here to sync the two files, and the mics don't hear the film (we
watch on earbuds), so that offset is all that lines the film up with our
reactions. If a short's film runs early or late, set
"shorts_sync_nudge_seconds" in the media config: positive plays the film
later.

A segment's "bleeps" list - [{"who": "us"|"film", "start", "end"}] in
recording time, set in the app's shorts editor - mutes that side's audio over
each span, lays the bleep sound over it ("bleep" in config/shorts.json: a
sound file in "sound", repeated to fill a long span, else a "tone_hz" tone)
and stars out
the caption words it covers. A film bleep in a segment the film isn't heard in
does nothing.

Looks, sizes and audio levels are in config/shorts.json. Output goes to a
"Shorts" folder beside the reaction recording (--out to change it), with a
.txt per short holding its YouTube title and description.

The band's lines are templates in config/shorts.json ("title"): {title} is
the film's title, {year} its year (the media config's "year", else the
"(1982)" in the movie's file name) and {hook} the short's hook_text.

All text - the title band and the captions - stays inside the platforms' safe zone
("safe_zone" in config/shorts.json): clear of the status/search bar at the
top, the title, description and subscribe row at the bottom, and the
like/comment/share column on the right. --preview --safe-zone shades what's
outside it on the stills, to check by eye.

Needs requirements-transcribe.txt (PyAV, numpy) and requirements-shorts.txt
(Pillow). No ffmpeg install.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from fractions import Fraction

from build_timeline import BuildError, _coerce_cut_row, load_shorts
from check_cuts import find_media_config, run_shorts_checks, words_paths
from convert_movie import first_times, pick_audio

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SETTINGS = os.path.join(REPO_ROOT, "config", "shorts.json")

AUDIO_RATE = 48000
FILM_AUDIO_LAYOUTS = {"panel"}
FONT_FOLDERS = (
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"),
    "/Library/Fonts", "/System/Library/Fonts", os.path.expanduser("~/Library/Fonts"),
    "/usr/share/fonts", os.path.expanduser("~/.fonts"),
)
WORD_SLACK = 0.15               # a caption's span may clip its words' edges by this
END_OF_PHRASE = ".!?"
BLEEP_DEFAULTS = {"sound": "", "tone_hz": 1000, "level_db": -4, "pad_ms": 90, "fade_ms": 5, "words": []}


# --- the job: shorts file + project config -------------------------------------


MIN_BAND_ROOM = 80               # px of the text band that must be inside the safe zone


def load_settings(path=DEFAULT_SETTINGS):
    if not os.path.exists(path):
        raise BuildError("Shorts config not found: {}".format(path))
    with open(path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)
    settings.setdefault("safe_zone", {"top": 0, "bottom": 0, "left": 0, "right": 0})
    settings["bleep"] = dict(BLEEP_DEFAULTS, **settings.get("bleep", {}))
    sound = settings["bleep"]["sound"]
    if sound:
        sound = os.path.expanduser(sound)
        settings["bleep"]["sound"] = sound if os.path.isabs(sound) else os.path.join(REPO_ROOT, sound)
        if not os.path.isfile(settings["bleep"]["sound"]):
            raise BuildError("{}: the bleep sound isn't there: {}".format(path, sound))
    left, top, right, bottom = safe_box(settings)
    if right - left < 200 or bottom - top < 200:
        raise BuildError("{}: safe_zone leaves almost nothing of the frame.".format(path))
    if settings["text_band_height"] - top < MIN_BAND_ROOM:
        raise BuildError(
            "{}: text_band_height ({}) must reach at least {}px below the safe zone's top ({}), "
            "or the title sits under the app's top bar.".format(
                path, settings["text_band_height"], MIN_BAND_ROOM, top))
    stack = settings["text_band_height"] + settings["film_height"] + settings.get("hosts_height", 0)
    if stack > settings["height"]:
        raise BuildError("{}: text_band_height + film_height + hosts_height is {}px, taller than "
                         "the {}px frame.".format(path, stack, settings["height"]))
    seam = settings["text_band_height"] + settings["film_height"]
    if not top < seam < bottom:
        raise BuildError(
            "{}: the caption seam (y={}) is outside the safe zone ({}-{}); change "
            "text_band_height or film_height.".format(path, seam, top, bottom))
    return settings


def safe_box(settings):
    """(left, top, right, bottom) in pixels: the part of the frame no app covers."""
    zone = settings["safe_zone"]
    return (zone["left"], zone["top"],
            settings["width"] - zone["right"], settings["height"] - zone["bottom"])


def load_job(cuts_path):
    """Everything a render needs that isn't in config/shorts.json."""
    shorts, meta = load_shorts(cuts_path)
    with open(cuts_path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)["shorts"]

    media_path = find_media_config(cuts_path)
    if not os.path.exists(media_path):
        raise BuildError("Project config not found: {}".format(media_path))
    with open(media_path, "r", encoding="utf-8") as handle:
        media = json.load(handle)
    for key in ("reaction_media", "movie_media"):
        if not media.get(key) or not os.path.exists(media[key]):
            raise BuildError("{}: {} not found ({!r}).".format(media_path, key, media.get(key)))

    offset = meta.get("movie_offset_seconds", media.get("movie_offset_seconds"))
    if offset is None:
        raise BuildError("No movie_offset_seconds in {} or {}.".format(cuts_path, media_path))

    # load_shorts keeps only the fields a timeline needs; captions and bleeps ride along here.
    for short, raw_short in zip(shorts, raw):
        for cut, raw_segment in zip(short["cuts"], raw_short["segments"]):
            raw_segment = raw_segment if isinstance(raw_segment, dict) else {}
            cut["captions"] = raw_segment.get("captions")
            cut["bleeps"] = segment_bleeps(raw_segment)
    return {
        "shorts": shorts,
        "raw": raw,
        "title": str(meta.get("title") or media.get("title") or "Short"),
        "year": film_year(media),
        "media": media,
        "offset": float(offset),
    }


def prepare_short(raw_short, number):
    """One short from a shorts file (or the editor's draft of one), as load_job gives it."""
    if not isinstance(raw_short, dict) or not isinstance(raw_short.get("segments"), list)             or not raw_short["segments"]:
        raise BuildError("short {} needs a non-empty 'segments' array.".format(number))
    short = {k: v for k, v in raw_short.items() if k != "segments"}
    short["number"] = number
    short["name"] = str(raw_short.get("name") or "Short {}".format(number)).strip()
    short["cuts"] = [_coerce_cut_row(row, i, "short {}".format(number))
                     for i, row in enumerate(raw_short["segments"])]
    for cut, raw_segment in zip(short["cuts"], raw_short["segments"]):
        cut["captions"] = raw_segment.get("captions")
        cut["bleeps"] = segment_bleeps(raw_segment)
    return short


def segment_bleeps(raw_segment):
    """[(start, end, who)] from a segment's "bleeps", kept inside the segment."""
    bleeps = []
    for bleep in raw_segment.get("bleeps") or []:
        try:
            start = max(float(bleep["start"]), float(raw_segment["start"]))
            end = min(float(bleep["end"]), float(raw_segment["end"]))
        except (KeyError, TypeError, ValueError):
            continue
        if end > start:
            bleeps.append((start, end, "film" if bleep.get("who") == "film" else "us"))
    return sorted(bleeps)


def is_swear(word, swears):
    """True when `word` is on the list. An entry matches the whole word; one
    ending in * matches any word it starts ("fuck*" catches "fucking")."""
    word = re.sub(r"[^a-z0-9]", "", word.lower())
    if not word:
        return False
    for entry in swears:
        entry = entry.lower().strip()
        if word == entry or entry.endswith("*") and word.startswith(entry[:-1]):
            return True
    return False


def find_swears(short, spoken, settings):
    """{segment index: [{"who", "start", "end"}]} for every listed swear the
    transcripts hear in a segment: ours always, the film's only where it's heard."""
    style = settings["bleep"]
    pad = style["pad_ms"] / 1000
    found = {}
    for index, cut in enumerate(short["cuts"]):
        sides = ["us"] + (["film"] if cut["layout"] in FILM_AUDIO_LAYOUTS else [])
        for who in sides:
            for start, end, text in spoken[who]:
                if end <= cut["start"] or start >= cut["end"] or not is_swear(text, style["words"]):
                    continue
                found.setdefault(index, []).append({
                    "who": who,
                    "start": round(max(cut["start"], start - pad), 2),
                    "end": round(min(cut["end"], end + pad), 2),
                })
    return found


def bleeped(text):
    """A word starred out after its first letter, punctuation kept: "f***!"."""
    match = re.match(r"^(\W*)(\w)(\w*)(.*)$", text)
    if not match:
        return text
    lead, first, rest, tail = match.groups()
    return lead + first + "*" * len(rest) + tail


def preview_groups(short, spoken, settings):
    """The caption groups a render would draw, without opening any media."""
    fps = settings["fps"]
    counts = [max(1, round((c["end"] - c["start"]) * fps)) for c in short["cuts"]]
    return caption_groups(short, spoken, settings, counts, fps)


def film_year(media):
    """The film's year: the media config's "year", else "(1982)" in the movie's file name."""
    if media.get("year"):
        return str(media["year"])
    for key in ("movie_source", "movie_media"):
        match = re.search(r"\((\d{4})\)", os.path.basename(media.get(key) or ""))
        if match:
            return match.group(1)
    return ""


def band_lines(settings, job, short):
    """[(text, size, font names)] for the title band, its templates filled in."""
    style = settings["title"]
    values = {"title": job["title"], "year": job.get("year", ""), "hook": short.get("hook_text") or ""}
    lines = []
    for line in style["lines"]:
        text = str(line["text"]).format_map(values)
        text = re.sub(r"\s*\(\s*\)", "", text)     # "({year})" with no year
        text = printable(" ".join(text.split()))
        if style.get("uppercase"):
            text = text.upper()
        if text:
            lines.append((text, line["size"], line.get("fonts") or settings["fonts"]))
    return lines


def default_out_dir(media):
    return os.path.join(os.path.dirname(media["reaction_media"]), "Shorts")


def output_base(title, short):
    """File name, without extension, for one short's video and its sidecars."""
    name = "{} Short {} - {}".format(title, short["number"], short["name"])
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip(" .")


def short_signature(raw_short, job, settings):
    """Changes whenever a re-render would come out different."""
    media = job["media"]
    payload = {
        "short": raw_short,
        "settings": settings,
        "offset": job["offset"],
        "media": [media["reaction_media"], media["movie_media"]],
        "crop": media.get("shorts_hosts_crop_x"),
        "nudge": media.get("shorts_sync_nudge_seconds"),
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


# --- reading the two media files -------------------------------------------------


class Clip:
    """One media file, read by time. Zero is its first video frame."""

    def __init__(self, path):
        import av

        self.path = path
        self.frames_in = av.open(path)
        self.video = self.frames_in.streams.video[0]
        self.video.thread_type = "AUTO"
        self.audio_in = av.open(path)
        self.audio = pick_audio(self.audio_in)
        start, _ = first_times(path, self.video.index, None)
        self.zero = float(start * self.video.time_base)
        self._converted = (None, None)

    def close(self):
        self.frames_in.close()
        self.audio_in.close()

    def frames(self, start, count, fps):
        """The frame showing at start, start + 1/fps, ... (`count` of them)."""
        base = self.video.time_base
        first = start + self.zero
        self.frames_in.seek(max(int(first / base), 0), stream=self.video, backward=True)
        decoder = self.frames_in.decode(self.video)
        showing, coming = None, None
        for k in range(count):
            want = first + k / fps + 1e-3
            while True:
                if coming is None:
                    coming = next(decoder, None)
                    if coming is None:
                        break
                if coming.pts is not None and float(coming.pts * base) > want:
                    break
                if coming.pts is not None:
                    showing = coming
                coming = None
            if showing is None:
                showing = coming        # asked for a time before the file's first frame
            if showing is None:
                raise BuildError("{} has no picture at {:.2f}s.".format(self.path, start))
            yield showing

    def picture(self, frame, width, height, crop_x=0.5):
        """`frame` scaled to cover width x height, as an RGB array."""
        if self._converted[0] == frame.pts:
            return self._converted[1]
        scale = max(width / frame.width, height / frame.height)
        wide = max(width, round(frame.width * scale))
        tall = max(height, round(frame.height * scale))
        rgb = frame.reformat(width=wide, height=tall, format="rgb24",
                             src_colorspace="ITU709", interpolation="BICUBIC").to_ndarray()
        x = round((wide - width) * min(max(crop_x, 0.0), 1.0))
        y = (tall - height) // 2
        result = rgb[y:y + height, x:x + width]
        self._converted = (frame.pts, result)
        return result

    def samples(self, start, count):
        """`count` stereo float samples at 48 kHz from `start`; silence where there are none."""
        import av
        import numpy

        out = numpy.zeros((count, 2), dtype=numpy.float32)
        if self.audio is None or count <= 0:
            return out
        first = start + self.zero
        self.audio_in.seek(max(int((first - 1.0) * av.time_base), 0))
        resampler = av.AudioResampler(format="flt", layout="stereo", rate=AUDIO_RATE)
        position = None
        for frame in self.audio_in.decode(self.audio):
            if frame.pts is None:
                continue
            for piece in resampler.resample(frame):
                data = piece.to_ndarray().reshape(-1, 2)
                if position is None:
                    position = round((float(frame.pts * self.audio.time_base) - first) * AUDIO_RATE)
                a, b = max(position, 0), min(position + len(data), count)
                if b > a:
                    out[a:b] = data[a - position:b - position]
                position += len(data)
            if position is not None and position >= count:
                break
        return out


# --- captions --------------------------------------------------------------------


def load_spoken(media_path, shift):
    """[(start, end, text)] from the transcript beside a media file, in recording time."""
    paths = words_paths(media_path)
    if not paths:
        return []
    with open(paths[0], "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return sorted(
        (word["start"] + shift, word["end"] + shift, word["word"].strip())
        for segment in data.get("segments", []) for word in segment.get("words", [])
        if word["word"].strip())


def caption_words(cut, spoken):
    """[(start, end, text, who)] in recording time for one segment, bleeped words starred out."""
    bleeps = cut.get("bleeps") or []

    def masked(words):
        return [(s, e, bleeped(text) if any(
                    side == who and b_start <= (s + e) / 2 <= b_end for b_start, b_end, side in bleeps)
                 else text, who) for s, e, text, who in words]

    captions = cut.get("captions")
    if captions is None:
        # No captions written for this segment: our transcript's words, as heard.
        return masked([(s, e, text, "us") for s, e, text in spoken["us"]
                       if cut["start"] - 1e-3 <= s < cut["end"]])

    words = []
    for caption in captions:
        who = "film" if caption.get("who") == "film" else "us"
        tokens = str(caption.get("text") or "").split()
        start = max(float(caption.get("start", cut["start"])), cut["start"])
        end = min(float(caption.get("end", cut["end"])), cut["end"])
        if not tokens or end <= start:
            continue
        heard = [w for w in spoken[who] if start - WORD_SLACK <= w[0] and w[1] <= end + WORD_SLACK]
        if len(heard) == len(tokens):
            timed = [(max(s, start), min(e, end)) for s, e, _ in heard]
        else:
            # The text was corrected, so the transcript's words don't pair off:
            # share the span out by word length.
            weights = [len(token) + 1 for token in tokens]
            edges, run = [start], 0
            for weight in weights:
                run += weight
                edges.append(start + (end - start) * run / sum(weights))
            timed = list(zip(edges, edges[1:]))
        words += [(s, max(e, s + 0.01), token, who) for (s, e), token in zip(timed, tokens)]
    return masked(sorted(words))


def caption_groups(short, spoken, settings, frame_counts, fps):
    """The word-pop groups, timed in the short's own output seconds.

    Each is {"start", "end", "who", "words": [(start, text)]}; a word is the
    highlighted one from its start until the next word's.
    """
    style = settings["captions"]
    groups, output_start = [], 0.0
    for cut, frames in zip(short["cuts"], frame_counts):
        length = frames / fps
        current = None
        for start, end, text, who in caption_words(cut, spoken):
            at = output_start + min(max(start - cut["start"], 0.0), length)
            until = output_start + min(max(end - cut["start"], 0.0), length)
            if style.get("uppercase"):
                text = text.upper()
            fresh = (
                current is None or current["who"] != who
                or at - current["end"] > style["gap_seconds"]
                or len(current["words"]) >= style["max_words"]
                or len(" ".join(w for _, w in current["words"])) + 1 + len(text) > style["max_chars"]
                or current["words"][-1][1][-1:] in END_OF_PHRASE
            )
            if fresh:
                current = {"start": at, "end": until, "who": who, "words": [], "limit": output_start + length}
                groups.append(current)
            current["words"].append((at, text))
            current["end"] = max(current["end"], until)
        output_start += length

    # Hold each group long enough to read, but never into the next or across a cut.
    for group, following in zip(groups, groups[1:] + [None]):
        hold = max(group["end"], group["start"] + style["min_show_seconds"])
        if following is not None and following["start"] - group["end"] < style["gap_seconds"]:
            hold = max(hold, following["start"])
        ceiling = group["limit"] if following is None else min(group["limit"], following["start"])
        group["end"] = max(min(hold, ceiling), group["start"])
    return groups


# --- drawing ---------------------------------------------------------------------


def find_font(names):
    for name in names:
        if os.path.isabs(name) and os.path.exists(name):
            return name
        for folder in FONT_FOLDERS:
            candidate = os.path.join(folder, name)
            if folder and os.path.exists(candidate):
                return candidate
    raise BuildError("None of the fonts in config/shorts.json are installed: {}.".format(
        ", ".join(names)))


def hex_color(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def printable(text):
    """Drop emoji and the like: the caption fonts have no glyphs for them."""
    return "".join(ch for ch in text if ord(ch) < 0x2190 or 0x2C00 <= ord(ch) < 0xD800).strip()


class Painter:
    """Draws the title band and the caption groups as RGBA images."""

    def __init__(self, settings):
        from PIL import ImageFont

        self.settings = settings
        self.font_path = find_font(settings["fonts"])
        self._font = ImageFont.truetype
        self._fonts = {}

    def font(self, size, path=None):
        key = (path or self.font_path, size)
        if key not in self._fonts:
            self._fonts[key] = self._font(key[0], size)
        return self._fonts[key]

    def band(self, lines):
        """The whole title band as an RGB array, its lines centred in the safe part of it.

        The lines keep their sizes relative to each other; if one is too wide,
        or the block too tall, they all shrink together.
        """
        import numpy
        from PIL import Image, ImageDraw

        settings, style = self.settings, self.settings["title"]
        width, height = settings["width"], settings["text_band_height"]
        image = Image.new("RGB", (width, height), hex_color(settings["background"]))
        if not lines:
            return numpy.asarray(image)
        # The text goes in the part of the band that's inside the safe zone.
        left, top, right, _ = safe_box(settings)
        room = right - left - 2 * style["margin"]
        room_height = height - top - 2 * style["margin"]
        draw = ImageDraw.Draw(image)
        paths = [find_font(fonts) for _, _, fonts in lines]
        scale = 1.0
        while True:
            fonts = [self.font(max(12, int(size * scale)), path)
                     for (_, size, _), path in zip(lines, paths)]
            boxes = [draw.textbbox((0, 0), text, font=font, anchor="ls")
                     for (text, _, _), font in zip(lines, fonts)]
            # Baseline to baseline is each line's cap height plus the gap.
            caps = [-box[1] for box in boxes]
            gap = style["line_gap"] * scale
            block = sum(caps) + gap * (len(lines) - 1) + max(0, boxes[-1][3])
            if (max(b[2] - b[0] for b in boxes) <= room and block <= room_height) or scale < 0.4:
                break
            scale *= 0.94
        y = top + style["margin"] + (room_height - block) / 2
        for (text, _, _), font, box, cap in zip(lines, fonts, boxes, caps):
            y += cap
            x = centred_x(width, left, right, box[2] - box[0]) - box[0]
            draw.text((x, y), text, font=font, fill=hex_color(style["color"]), anchor="ls")
            y += gap
        return numpy.asarray(image)

    def caption(self, words, active, who):
        """(rgba array, width, height) for one group with word `active` highlighted."""
        import numpy
        from PIL import Image, ImageDraw

        style = self.settings["captions"]
        left, _, right, _ = safe_box(self.settings)
        room = right - left - 2 * style["margin"]
        stroke = style["stroke_width"]
        probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        size = style["size"]
        while True:
            font = self.font(size)
            space = probe.textlength(" ", font=font)
            widths = [probe.textlength(word, font=font) for word in words]
            total = sum(widths) + space * (len(words) - 1)
            if total + 2 * stroke <= room or size <= 36:
                break
            size -= 4
        ascent, descent = font.getmetrics()
        width = int(total + 2 * stroke + 4)
        height = ascent + descent + 2 * stroke + 4
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        x = stroke + 2
        for index, (word, word_width) in enumerate(zip(words, widths)):
            fill = style["highlight"][who] if index == active else style["color"]
            draw.text((x, stroke + 2), word, font=font, fill=hex_color(fill),
                      stroke_width=stroke, stroke_fill=hex_color(style["stroke_color"]))
            x += word_width + space
        return numpy.asarray(image)


def wrap(draw, text, font, room, max_lines):
    """Break `text` into at most `max_lines` lines no wider than `room`, evenly."""
    words = text.split()
    if draw.textlength(text, font=font) <= room or max_lines < 2 or len(words) < 2:
        return [text]
    # Two balanced lines read better than one full line and an orphan.
    best = min(range(1, len(words)), key=lambda i: abs(
        draw.textlength(" ".join(words[:i]), font=font) - draw.textlength(" ".join(words[i:]), font=font)))
    return [" ".join(words[:best]), " ".join(words[best:])]


def centred_x(width, left, right, size):
    """Left edge for something `size` wide: centred on the frame, moved only as
    far as it takes to stay inside the safe zone's left..right."""
    x = (width - size) / 2
    return max(left, min(x, right - size))


def shade_unsafe(picture, settings):
    """A copy of `picture` with everything outside the safe zone tinted red."""
    import numpy

    left, top, right, bottom = safe_box(settings)
    out = picture.copy()
    mask = numpy.ones(out.shape[:2], dtype=bool)
    mask[top:bottom, left:right] = False
    out[mask] = (out[mask] * 0.45 + numpy.array([255, 0, 0]) * 0.55).astype(numpy.uint8)
    return out


def blend(canvas, rgba, center_x, center_y):
    """Alpha-blend `rgba` onto `canvas`, centred on a point."""
    import numpy

    height, width = rgba.shape[:2]
    x, y = int(center_x - width / 2), int(center_y - height / 2)
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + width, canvas.shape[1]), min(y + height, canvas.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    patch = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    alpha = patch[:, :, 3:4].astype(numpy.uint16)
    under = canvas[y0:y1, x0:x1].astype(numpy.uint16)
    canvas[y0:y1, x0:x1] = ((patch[:, :, :3] * alpha + under * (255 - alpha)) // 255).astype(numpy.uint8)


# --- one short -------------------------------------------------------------------


class ShortRender:
    """Everything worked out for one short before any frame is drawn."""

    def __init__(self, short, job, settings, reaction, film, painter, spoken):
        self.short, self.settings = short, settings
        self.reaction, self.film, self.painter = reaction, film, painter
        self.fps = settings["fps"]
        self.frame_counts = [max(1, round((c["end"] - c["start"]) * self.fps)) for c in short["cuts"]]
        self.total_frames = sum(self.frame_counts)
        self.crop_x = float(job["media"].get("shorts_hosts_crop_x", settings["hosts_crop_x"]))

        # Seconds to slide the film against the recording, for an offset that's a touch off.
        self.correction = float(job["media"].get("shorts_sync_nudge_seconds") or 0.0)
        self.film_offset = job["offset"] + self.correction

        self.band = painter.band(band_lines(settings, job, short))
        self.groups = caption_groups(short, spoken, settings, self.frame_counts, self.fps)
        self._caption_images = {}

    def caption_at(self, seconds):
        for index, group in enumerate(self.groups):
            if group["start"] - 1e-6 <= seconds < group["end"]:
                active = max(i for i, (at, _) in enumerate(group["words"]) if at <= seconds + 1e-6)
                key = (index, active)
                if key not in self._caption_images:
                    self._caption_images[key] = self.painter.caption(
                        [word for _, word in group["words"]], active, group["who"])
                return self._caption_images[key]
        return None

    def compose(self, film_frame, hosts_frame, seconds):
        import numpy

        settings = self.settings
        width, height = settings["width"], settings["height"]
        band, film_height = settings["text_band_height"], settings["film_height"]
        hosts_top = band + film_height
        hosts_height = settings.get("hosts_height") or height - hosts_top
        canvas = numpy.empty((height, width, 3), dtype=numpy.uint8)
        canvas[:] = hex_color(settings["background"])
        canvas[:band] = self.band
        canvas[band:hosts_top] = self.film.picture(film_frame, width, film_height)
        canvas[hosts_top:hosts_top + hosts_height] = self.reaction.picture(
            hosts_frame, width, hosts_height, self.crop_x)
        caption = self.caption_at(seconds)
        if caption is not None:
            # On the seam, centred in the safe zone, and pushed inside it if it's tall.
            left, top, right, bottom = safe_box(settings)
            half = caption.shape[0] / 2
            y = min(max(band + film_height, top + half), bottom - half)
            x = centred_x(width, left, right, caption.shape[1])
            blend(canvas, caption, x + caption.shape[1] / 2, y)
        return canvas

    def pictures(self):
        """Every output frame, in order, as (index, RGB array)."""
        index = 0
        for cut, count in zip(self.short["cuts"], self.frame_counts):
            hosts = self.reaction.frames(cut["start"], count, self.fps)
            film = self.film.frames(cut["start"] - self.film_offset, count, self.fps)
            for hosts_frame, film_frame in zip(hosts, film):
                yield index, self.compose(film_frame, hosts_frame, index / self.fps)
                index += 1

    def still(self):
        """One representative frame: mid-way through the first caption, else the first cut."""
        seconds = (self.groups[0]["start"] + self.groups[0]["end"]) / 2 if self.groups else \
            self.frame_counts[0] / self.fps / 2
        target = min(int(seconds * self.fps), self.total_frames - 1)
        passed = 0
        for cut, count in zip(self.short["cuts"], self.frame_counts):
            if target < passed + count:
                at = cut["start"] + (target - passed) / self.fps
                hosts_frame = next(self.reaction.frames(at, 1, self.fps))
                film_frame = next(self.film.frames(at - self.film_offset, 1, self.fps))
                return self.compose(film_frame, hosts_frame, target / self.fps)
            passed += count

    def sound(self):
        """The whole short's audio: (samples, 2) float32, cut-for-cut with the frames."""
        import numpy

        audio = self.settings["audio"]
        per_frame = AUDIO_RATE // self.fps
        fade = max(1, int(audio["fade_ms"] * AUDIO_RATE / 1000))
        ramp = numpy.linspace(0.0, 1.0, fade, dtype=numpy.float32)[:, None]
        hosts_gain = 10 ** (audio["hosts_gain_db"] / 20)
        film_gain = 10 ** (audio["film_gain_db"] / 20)

        bleep = self.settings["bleep"]
        bleep_fade = max(1, int(bleep["fade_ms"] * AUDIO_RATE / 1000))

        parts, tones, at = [], [], 0
        for cut, count in zip(self.short["cuts"], self.frame_counts):
            samples = count * per_frame
            heard = {"us": self.reaction.samples(cut["start"], samples) * hosts_gain}
            if cut["layout"] in FILM_AUDIO_LAYOUTS:
                heard["film"] = self.film.samples(cut["start"] - self.film_offset, samples) * film_gain
            for start, end, who in cut.get("bleeps") or []:
                if who not in heard:
                    continue        # the film isn't heard here, so there's nothing to bleep
                a = max(0, round((start - cut["start"]) * AUDIO_RATE))
                b = min(samples, round((end - cut["start"]) * AUDIO_RATE))
                if b > a:
                    heard[who][a:b] *= (1.0 - envelope(b - a, bleep_fade))[:, None]
                    tones.append((at + a, at + b))
            mix = sum(heard.values())
            if samples >= 2 * fade:
                mix[:fade] *= ramp
                mix[-fade:] *= ramp[::-1]
            parts.append(mix)
            at += samples
        sound = numpy.concatenate(parts)
        peak = float(numpy.abs(sound).max())
        if peak > 0:
            # Bring the loudest moment to the target; never boost a near-silent short absurdly.
            sound *= min(10 ** (audio["peak_db"] / 20) / peak, 8.0)
        # The bleep goes on after the levelling, so it's the same level in every short.
        level = 10 ** (bleep["level_db"] / 20)
        effect = bleep_sound(bleep["sound"]) if bleep["sound"] and tones else None
        for a, b in tones:
            if effect is not None:
                # From its start, over again for a span longer than one.
                over = numpy.resize(effect, (b - a, 2)) * level
            else:
                t = numpy.arange(b - a, dtype=numpy.float32) / AUDIO_RATE
                over = (numpy.sin(2 * numpy.pi * bleep["tone_hz"] * t) * level)[:, None]
            sound[a:b] += over * envelope(b - a, bleep_fade)[:, None]
        numpy.clip(sound, -1.0, 1.0, out=sound)
        return sound


def bleep_sound(path):
    """The bleep sound file as (samples, 2) float32 at 48 kHz, peak at 1.0,
    the near-silent tail cut off so a repeat comes straight back in."""
    import av
    import numpy

    resampler = av.AudioResampler(format="flt", layout="stereo", rate=AUDIO_RATE)
    pieces = []
    with av.open(path) as source:
        if not source.streams.audio:
            raise BuildError("The bleep sound has no audio: {}".format(path))
        for frame in source.decode(audio=0):
            pieces += [piece.to_ndarray().reshape(-1, 2) for piece in resampler.resample(frame)]
        pieces += [piece.to_ndarray().reshape(-1, 2) for piece in resampler.resample(None)]
    data = numpy.concatenate(pieces) if pieces else numpy.zeros((0, 2), dtype=numpy.float32)
    loud = numpy.abs(data).max(axis=1)
    peak = float(loud.max()) if len(loud) else 0.0
    if peak <= 0:
        raise BuildError("The bleep sound is silent: {}".format(path))
    heard = numpy.nonzero(loud > peak * 10 ** (-50 / 20))[0]
    return data[heard[0]:heard[-1] + 1] / peak


def envelope(length, fade):
    """0..1 over `length` samples: up across `fade`, held, back down - no clicks."""
    import numpy

    shape = numpy.ones(length, dtype=numpy.float32)
    fade = min(fade, length // 2)
    if fade:
        ramp = numpy.linspace(0.0, 1.0, fade, dtype=numpy.float32)
        shape[:fade] = ramp
        shape[-fade:] = ramp[::-1]
    return shape


def encode(render, path):
    import av
    import numpy

    settings = render.settings
    fps = render.fps
    per_frame = AUDIO_RATE // fps
    sound = render.sound()

    with av.open(path, "w", format="mp4", options={"movflags": "+faststart"}) as out:
        video = out.add_stream("libx264", rate=fps, options={
            "crf": str(settings["video"]["crf"]), "preset": settings["video"]["preset"]})
        video.width, video.height, video.pix_fmt = settings["width"], settings["height"], "yuv420p"
        audio = out.add_stream("aac", rate=AUDIO_RATE, layout="stereo")
        audio.bit_rate = 192000

        next_report = 10
        for index, picture in render.pictures():
            frame = av.VideoFrame.from_ndarray(numpy.ascontiguousarray(picture), format="rgb24")
            frame = frame.reformat(format="yuv420p", dst_colorspace="ITU709")
            frame.pts = index
            frame.time_base = Fraction(1, fps)
            for packet in video.encode(frame):
                out.mux(packet)

            chunk = sound[index * per_frame:(index + 1) * per_frame]
            sound_frame = av.AudioFrame.from_ndarray(
                numpy.ascontiguousarray(chunk.T), format="fltp", layout="stereo")
            sound_frame.sample_rate = AUDIO_RATE
            sound_frame.pts = index * per_frame
            for packet in audio.encode(sound_frame):
                out.mux(packet)

            done = 100 * (index + 1) // render.total_frames
            if done >= next_report:
                print("  {:3d}%".format(done))
                next_report = (done // 10 + 1) * 10
        for packet in video.encode(None):
            out.mux(packet)
        for packet in audio.encode(None):
            out.mux(packet)


def write_sidecars(base_path, short, render, signature):
    with open(base_path + ".txt", "w", encoding="utf-8") as handle:
        handle.write("{}\n\n{}\n".format(short.get("yt_title") or short["name"],
                                         short.get("description") or ""))
    with open(base_path + ".render.json", "w", encoding="utf-8") as handle:
        json.dump({
            "signature": signature,
            "rendered": datetime.datetime.now().isoformat(timespec="seconds"),
            "seconds": render.total_frames / render.fps,
            "sync_nudge_seconds": render.correction,
        }, handle, indent=2)
        handle.write("\n")


# --- entry point -------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cuts", required=True, help="Shorts file (cuts/<episode>.shorts.json).")
    parser.add_argument("--short", type=int, action="append", metavar="N",
                        help="Render just short N (1-based). Repeatable.")
    parser.add_argument("--preview", action="store_true",
                        help="Write one still per short instead of the video.")
    parser.add_argument("--safe-zone", action="store_true",
                        help="With --preview: shade the area outside the safe zone red.")
    parser.add_argument("--out", default=None,
                        help="Output folder. Default: a Shorts folder beside the reaction recording.")
    parser.add_argument("--config", default=DEFAULT_SETTINGS,
                        help="Shorts look and sound. Default: %(default)s")
    args = parser.parse_args(argv)

    try:
        settings = load_settings(args.config)
        job = load_job(args.cuts)
        checks = {c["number"]: c for c in run_shorts_checks(args.cuts)}
        numbers = args.short or [s["number"] for s in job["shorts"]]
        bad = [n for n in numbers if n not in checks]
        if bad:
            raise BuildError("--short {}: the file has shorts 1-{}.".format(
                ", ".join(str(n) for n in bad), len(job["shorts"])))
        painter = Painter(settings)
    except BuildError as error:
        print("ERROR: {}".format(error), file=sys.stderr)
        return 1
    except ImportError as error:
        print("ERROR: {} - pip install -r requirements-shorts.txt".format(error), file=sys.stderr)
        return 1

    from PIL import Image

    out_dir = args.out or default_out_dir(job["media"])
    os.makedirs(out_dir, exist_ok=True)
    for short in job["shorts"]:
        # A render that was cancelled leaves its half-written file behind.
        abandoned = os.path.join(out_dir, output_base(job["title"], short)) + ".rendering.mp4"
        if os.path.exists(abandoned):
            os.remove(abandoned)
    media = job["media"]
    spoken = {"us": load_spoken(media["reaction_media"], 0.0),
              "film": load_spoken(media["movie_media"], job["offset"])}
    reaction, film = Clip(media["reaction_media"]), Clip(media["movie_media"])

    refused = 0
    try:
        for short, raw_short in zip(job["shorts"], job["raw"]):
            if short["number"] not in numbers:
                continue
            base = os.path.join(out_dir, output_base(job["title"], short))
            print("Short {} - {}".format(short["number"], short["name"]))
            fails = checks[short["number"]]["fails"]
            if fails:
                refused += 1
                print("  NOT RENDERED - it breaks a hard limit:")
                for line in fails:
                    print("    FAIL  {}".format(line))
                continue

            render = ShortRender(short, job, settings, reaction, film, painter, spoken)
            print("  {:.1f}s, {} segments, {} caption groups.".format(
                render.total_frames / render.fps, len(short["cuts"]), len(render.groups)))
            if args.preview:
                still = render.still()
                if args.safe_zone:
                    still = shade_unsafe(still, settings)
                Image.fromarray(still).save(base + ".preview.png")
                print("  Wrote {}.preview.png".format(base))
                continue

            partial = base + ".rendering.mp4"
            encode(render, partial)
            os.replace(partial, base + ".mp4")
            Image.fromarray(render.still()).save(base + ".preview.png")
            write_sidecars(base, short, render, short_signature(raw_short, job, settings))
            print("  Wrote {}.mp4".format(base))
    except BuildError as error:
        print("ERROR: {}".format(error), file=sys.stderr)
        return 1
    finally:
        reaction.close()
        film.close()

    if refused:
        print("{} short(s) not rendered. Fix them (python src/check_cuts.py --cuts {}) "
              "and render again.".format(refused, args.cuts))
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
