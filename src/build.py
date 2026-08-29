#!/usr/bin/env python3
"""Build an OTIO timeline from edit.json/sources.json and export it as FCPXML."""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from fractions import Fraction
from urllib.parse import quote, unquote

import opentimelineio as otio

# fps -> exact playback rate. Only these are supported; anything else fails
# loudly instead of being silently rounded (e.g. 23.976 must never be
# treated as a flat 24, and 29.97 must never be treated as a flat 30 - and
# by the same logic, a genuine flat 30 (e.g. a screen recording) must never
# be treated as 29.97; it's its own distinct, exact whole-number rate).
SUPPORTED_FPS = {
    23.976: Fraction(24000, 1001),
    29.97: Fraction(30000, 1001),
    30: Fraction(30, 1),
}
FPS_TOLERANCE = 0.001

# Availability slack appended after the last frame any clip references, so
# the placeholder asset's declared duration comfortably covers every clip's
# out point. Purely cosmetic bookkeeping - real duration comes from the
# actual media file once it's relinked in Resolve.
AVAILABILITY_SLACK_SECONDS = 5

# EDL reel names (<=8 chars, cmx_3600's default limit) for the two sources.
# Set explicitly via clip.metadata["cmx_3600"]["reel"] so Resolve's Media
# Pool relink list shows exactly two clean, stable names instead of
# whatever the placeholder file path's basename happens to be.
REEL_NAMES = {"host": "HOST", "movie": "MOVIE"}

OUTPUT_PATHS = {"fcpxml": "test/cut.fcpxml", "edl": "test/cut.edl"}

# Timelines start at 01:00:00:00 rather than zero - the Resolve/broadcast
# convention, leaving an hour of headroom before frame zero. This is both
# the <sequence tcStart> value and the amount every top-level spine offset
# is shifted by, and the two MUST agree: spine offsets are absolute
# positions on the sequence's own timeline, so a clip at offset 0s under
# tcStart 3600s sits an hour *before* the timeline starts.
TIMELINE_START_SECONDS = 3600

# Audio characteristics declared on every <asset>. FCPXML wants these
# alongside hasAudio="1" for an asset to count as having sound at all;
# Resolve reads the real channel count/rate off the media when it links,
# so these are declarations, not conversions - stereo 48kHz covers both
# sources here. See fix_up_fcpxml().
AUDIO_SOURCES = "1"
AUDIO_CHANNELS = "2"
AUDIO_RATE = "48000"


def resolve_rate(fps_value):
    """Map a sources.json fps value to its exact rate, or fail loudly."""
    for supported_fps, rate in SUPPORTED_FPS.items():
        if abs(fps_value - supported_fps) < FPS_TOLERANCE:
            return rate
    supported = ", ".join(str(f) for f in SUPPORTED_FPS)
    raise SystemExit(
        f"Unhandled fps {fps_value!r} in sources.json. "
        f"This tool only handles: {supported}. Refusing to guess/round."
    )


def _fcpx_xml_adapter_module():
    """Return the exact module object OTIO's adapter registry runs.

    OTIO loads adapter plugins from file path via its own manifest system,
    which produces a distinct module object from a plain `import
    opentimelineio_contrib.adapters.fcpx_xml` (same file, two module
    instances). We need the registry's instance specifically, since that's
    the one write_to_file() below actually calls into.
    """
    for adapter in otio.plugins.ActiveManifest().adapters:
        if adapter.name == "fcpx_xml":
            return adapter.module()
    raise SystemExit(
        "The 'fcpx_xml' adapter isn't registered. Check that "
        "opentimelineio==0.16.0 is installed (see requirements.txt)."
    )


def patch_frame_duration_table(rate):
    """Register the exact rate with the fcpx_xml adapter's lookup table.

    The bundled adapter maps a clip's frame rate to a <format
    frameDuration=...> string via a dict keyed on rounded labels like 23.98
    and 29.97 (see FRAMERATE_FRAMEDURATION in the adapter source). Our clips
    use the exact rational rate (24000/1001, not 23.98) so the export stays
    frame-accurate; without this patch the dict lookup misses and the
    <format> element is written with an empty frameDuration.
    """
    frame_duration = {
        Fraction(24000, 1001): "1001/24000s",
        Fraction(30000, 1001): "1001/30000s",
        Fraction(30, 1): "1/30s",
    }[rate]
    _fcpx_xml_adapter_module().FRAMERATE_FRAMEDURATION[float(rate)] = frame_duration


def seconds_to_frame(seconds, rate):
    """Convert seconds to a whole frame count at the given exact rate."""
    return int(round(seconds * float(rate)))


def resolve_true_case(path_str):
    """Return `path_str` with each component's real on-disk capitalisation.

    macOS filesystems are case-*insensitive* but the URLs we write are
    read case-*sensitively* by Resolve's importer. So a sources.json entry
    of "/Users/doug/movies/..." passes os.path.exists() and opens fine
    from Python even when the folder is really "/Users/doug/Movies" - and
    then Resolve reports the media as missing, because it looks the URL up
    literally. This walks the path resolving each component against what's
    actually on disk so the URL matches reality.

    Only applies when the file is present locally. A path that points at
    another machine's disk (generate on macOS, import on Windows - see
    README) can't be checked, so it's returned untouched.
    """
    if not os.path.exists(path_str):
        return path_str
    parts = path_str.strip("/").split("/")
    current = "/"
    for part in parts:
        try:
            entries = os.listdir(current)
        except OSError:
            return path_str
        if part in entries:
            match = part
        else:
            lowered = [e for e in entries if e.lower() == part.lower()]
            if len(lowered) != 1:
                return path_str
            match = lowered[0]
        current = os.path.join(current, match)
    return current


def to_media_target_url(path_str):
    """Convert a sources.json path into a file:// URL for the timeline.

    Uses forward slashes throughout so the URL is syntactically valid on
    both macOS and Windows, and percent-encodes everything but the slashes
    (spaces, parentheses, etc.) so the result is a valid URI - a raw space
    in a file:// URL isn't, and gets misparsed by some importers. This does
    NOT make cross-platform relinking automatic - if you generate on macOS
    and import on Windows, the exact path won't exist on the Windows box
    and Resolve will show the media as offline; you still relink manually
    (see test/VERIFY.md).

    For FCPXML, this URL is the actual `src` attribute Resolve reads, so
    getting the slashes and encoding right matters. For EDL, it only ends
    up in a `* FROM CLIP:` comment - EDL has no field for a full path at
    all, so relinking on EDL import is always manual by reel name (see
    REEL_NAMES), on every platform, regardless of this URL.
    """
    normalized = str(path_str).replace("\\", "/")
    if normalized.lower().startswith("file://"):
        return normalized
    if re.match(r"^[A-Za-z]:/", normalized):
        drive, rest = normalized[:2], normalized[2:]
        return "file:///" + drive + quote(rest)
    if normalized.startswith("/"):
        return "file://" + quote(normalized)
    raise SystemExit(
        f"Media path {path_str!r} in sources.json must be absolute "
        "(POSIX '/...' or Windows 'C:/...') so it can be written as a "
        "file:// URL."
    )


def video_source_for_layout(layout):
    """Pick which physical source clip a layout's segment's video is cut from.

    This test builds a single video track with one clip per segment, so
    each segment's video can only reference one media file. Layouts are
    assumed to follow a `<source>_<detail>` or `<detail>_<source>` naming
    convention (e.g. "movie_full", "pip_host"); anything not explicitly
    tagged "movie" falls back to the host source. Real PIP compositing
    (both sources on screen at once) is out of scope for this test.
    """
    tokens = layout.split("_")
    if "movie" in (tokens[0], tokens[-1]):
        return "movie"
    return "host"


def other_source(source_name):
    """The one physical source that isn't `source_name` (host <-> movie)."""
    return "movie" if source_name == "host" else "host"


def secondary_source_for_layout(layout):
    """Pick V2/A2's source for a layout: always whichever source isn't on V1.

    V1/A1 carry video_source_for_layout()'s pick (host, for every layout
    in this dataset); V2/A2 carry the other source - the movie - on every
    segment, regardless of what the layout is tagged. Layout tags decide
    how the segment should eventually be *composited*, not whether the
    footage is available to composite with, so the movie is laid in
    everywhere and the arranging happens in Resolve.

    The one thing that can still leave V2/A2 empty is physical: a segment
    playing before the movie started has no movie footage to reference at
    all. seconds_in_other_source() returns None there and build_timeline()
    falls back to a Gap.
    """
    return other_source(video_source_for_layout(layout))


def seconds_in_other_source(seconds, from_source, to_source, movie_offset_seconds):
    """Convert `seconds`, expressed in from_source's timeline, into
    to_source's timeline. Returns `seconds` unchanged if the two match, or
    None if to_source's timeline doesn't cover this moment yet (e.g. a
    segment before the movie started playing) - callers should fall back
    to a Gap rather than fabricate footage that doesn't exist.

    A segment's start/end in edit.json are always expressed in its primary
    video source's own timeline (see README's "Timeline seconds == source
    seconds"). Placing a clip from a *different* source at the same moment
    needs those seconds re-expressed in that source's timeline first. The
    only defined relationship is host vs. movie: the movie file's clock
    trails the host recording's clock by `movie_offset_seconds` (see
    sources.json), so movie_time = host_time - movie_offset_seconds. Any
    other pairing fails loudly instead of guessing.
    """
    if to_source == from_source:
        return seconds
    if movie_offset_seconds is None:
        raise SystemExit(
            "A segment needs a host/movie time mapping, but sources.json "
            "has no movie_offset_seconds to align them."
        )
    if from_source == "host" and to_source == "movie":
        result = seconds - movie_offset_seconds
    elif from_source == "movie" and to_source == "host":
        result = seconds + movie_offset_seconds
    else:
        raise SystemExit(
            f"No defined time mapping from source {from_source!r} to "
            f"{to_source!r}."
        )
    return result if result >= 0 else None


def build_media_references(segments, sources, rate):
    """Compute one ExternalReference per source, sized to cover all clips."""
    target_urls = {
        "host": to_media_target_url(sources["host_clip"]),
        "movie": to_media_target_url(sources["movie_clip"]),
    }
    movie_offset_seconds = sources.get("movie_offset_seconds")
    max_end_frame = {"host": 0, "movie": 0}
    for segment in segments:
        layout = segment["layout"]
        video_source = video_source_for_layout(layout)

        video_end_frame = seconds_to_frame(segment["end"], rate)
        max_end_frame[video_source] = max(max_end_frame[video_source], video_end_frame)

        secondary_source = secondary_source_for_layout(layout)
        if secondary_source is not None:
            secondary_end_seconds = seconds_in_other_source(
                segment["end"], video_source, secondary_source, movie_offset_seconds
            )
            if secondary_end_seconds is not None:
                secondary_end_frame = seconds_to_frame(secondary_end_seconds, rate)
                max_end_frame[secondary_source] = max(
                    max_end_frame[secondary_source], secondary_end_frame
                )

    slack_frames = seconds_to_frame(AVAILABILITY_SLACK_SECONDS, rate)
    references = {}
    for source_name, url in target_urls.items():
        available_frames = max_end_frame[source_name] + slack_frames
        references[source_name] = otio.schema.ExternalReference(
            target_url=url,
            available_range=otio.opentime.TimeRange(
                start_time=otio.opentime.RationalTime(0, float(rate)),
                duration=otio.opentime.RationalTime(available_frames, float(rate)),
            ),
        )
    return references


def validate_segments(segments, rate):
    """Check ordering/overlap and frame-convert start/end, failing loudly."""
    frame_ranges = []
    previous_end_seconds = None
    for index, segment in enumerate(segments):
        start_seconds = segment["start"]
        end_seconds = segment["end"]
        if end_seconds <= start_seconds:
            raise SystemExit(
                f"edit.json segment {index} has end <= start "
                f"({start_seconds} -> {end_seconds})."
            )
        if previous_end_seconds is not None and start_seconds < previous_end_seconds:
            raise SystemExit(
                f"edit.json segment {index} starts at {start_seconds}, "
                f"before the previous segment ends at {previous_end_seconds}. "
                "Segments must be in order and non-overlapping on a single track."
            )
        previous_end_seconds = end_seconds

        start_frame = seconds_to_frame(start_seconds, rate)
        end_frame = seconds_to_frame(end_seconds, rate)
        if end_frame <= start_frame:
            raise SystemExit(
                f"edit.json segment {index} rounds to a zero/negative-length "
                f"clip at {rate} fps ({start_frame} -> {end_frame})."
            )
        frame_ranges.append((start_frame, end_frame))
    return frame_ranges


def build_timeline(sources, segments, rate, mode):
    """Build the OTIO timeline.

    mode="inplace" keeps each segment at its source position, inserting a
    Gap to cover the distance since the previous segment ended - useful for
    reviewing selections against the original. mode="compact" appends
    segments back-to-back with no gaps, so a 2-hour source becomes however
    long the selected segments add up to. Either way, each clip's
    source_range (its in/out point *within* the source media) is unchanged
    - only whether Gaps are inserted between clips on the output track
    differs.

    Builds four tracks - V1, V2, A1, A2 - kept frame-for-frame aligned on
    the output timeline (same gaps, same positions, same durations). V1/A1
    carry video_source_for_layout()'s pick (host, for every layout in this
    dataset) on every segment. V2/A2 carry the movie source as a pair,
    wherever secondary_source_for_layout() says the layout is more than
    "hosts only" - a plain host segment gets no V2/A2 clip at all.
    """
    media_references = build_media_references(segments, sources, rate)
    frame_ranges = validate_segments(segments, rate)
    movie_offset_seconds = sources.get("movie_offset_seconds")

    v1 = otio.schema.Track(name="V1", kind=otio.schema.TrackKind.Video)
    v2 = otio.schema.Track(name="V2", kind=otio.schema.TrackKind.Video)
    all_tracks = (v1, v2)
    current_frame = 0

    for index, (segment, (start_frame, end_frame)) in enumerate(
        zip(segments, frame_ranges)
    ):
        if mode == "inplace":
            gap_frames = start_frame - current_frame
            if gap_frames > 0:
                for track in all_tracks:
                    track.append(
                        otio.schema.Gap(
                            source_range=otio.opentime.TimeRange(
                                start_time=otio.opentime.RationalTime(0, float(rate)),
                                duration=otio.opentime.RationalTime(
                                    gap_frames, float(rate)
                                ),
                            )
                        )
                    )

        layout = segment["layout"]
        clip_name = f"{index + 1:02d}_{layout}"
        duration_frames = end_frame - start_frame
        video_source = video_source_for_layout(layout)

        # V1 - the hosts, every segment. Audio isn't a separate track:
        # fix_up_fcpxml() turns each of these into an <asset-clip>, which
        # carries its asset's video *and* audio together. This is also the
        # only track --format edl reads (see write_timeline()).
        video_clip = otio.schema.Clip(
            name=clip_name,
            source_range=otio.opentime.TimeRange(
                start_time=otio.opentime.RationalTime(start_frame, float(rate)),
                duration=otio.opentime.RationalTime(duration_frames, float(rate)),
            ),
            media_reference=media_references[video_source],
        )
        video_clip.markers.append(
            otio.schema.Marker(
                name=layout,
                marked_range=otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(0, float(rate)),
                    duration=video_clip.duration(),
                ),
            )
        )
        # Only read by the cmx_3600 (EDL) adapter; the fcpx_xml adapter
        # ignores unrecognized metadata namespaces. See REEL_NAMES.
        video_clip.metadata["cmx_3600"] = {"reel": REEL_NAMES[video_source]}
        v1.append(video_clip)

        # V2 - the movie, carrying its own audio the same way V1 does.
        # Gap where there's no movie footage yet (see
        # seconds_in_other_source()), to keep later V2 clips positioned.
        secondary_source = secondary_source_for_layout(layout)
        secondary_start_seconds = (
            seconds_in_other_source(
                segment["start"], video_source, secondary_source, movie_offset_seconds
            )
            if secondary_source is not None
            else None
        )
        if secondary_start_seconds is None:
            v2.append(
                otio.schema.Gap(
                    source_range=otio.opentime.TimeRange(
                        start_time=otio.opentime.RationalTime(0, float(rate)),
                        duration=otio.opentime.RationalTime(
                            duration_frames, float(rate)
                        ),
                    )
                )
            )
        else:
            secondary_start_frame = seconds_to_frame(secondary_start_seconds, rate)
            secondary_clip = otio.schema.Clip(
                name=f"{clip_name}_{secondary_source}",
                source_range=otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(
                        secondary_start_frame, float(rate)
                    ),
                    duration=otio.opentime.RationalTime(
                        duration_frames, float(rate)
                    ),
                ),
                media_reference=media_references[secondary_source],
            )
            secondary_clip.metadata["cmx_3600"] = {
                "reel": REEL_NAMES[secondary_source]
            }
            v2.append(secondary_clip)

        current_frame = end_frame

    timeline = otio.schema.Timeline(name="tdos_pipeline_verify_cut")
    timeline.global_start_time = otio.opentime.RationalTime(0, float(rate))
    for track in all_tracks:
        timeline.tracks.append(track)
    return timeline


def parse_fcpx_seconds(value):
    """Parse an FCPXML time ("0s", "218/15s", "3600s") to a Fraction."""
    return Fraction(value.rstrip("s"))


def fcpx_seconds(value):
    """Render a Fraction/int as an FCPXML time string ("218/15s", "3600s")."""
    fraction = Fraction(value)
    if fraction.denominator == 1:
        return f"{fraction.numerator}s"
    return f"{fraction.numerator}/{fraction.denominator}s"


def fcpx_format_name(height, rate):
    """Build an FCPXML format name like "FFVideoFormat1080p30".

    Final Cut's own naming convention, which Resolve also recognises: the
    frame height, "p", then the rate with any decimal point dropped
    (23.976 -> 2398, 29.97 -> 2997, 30 -> 30).
    """
    rate_labels = {
        Fraction(24000, 1001): "2398",
        Fraction(30000, 1001): "2997",
        Fraction(30, 1): "30",
    }
    return f"FFVideoFormat{height}p{rate_labels[rate]}"


def rewrite_spine_as_asset_clips(spine, tc_format):
    """Rewrite the adapter's <clip>/<video>/<audio> spine into <asset-clip>.

    The adapter models a clip as a <clip> wrapping a <video ref=...>, and
    has no way to say "this clip's audio comes along too" - so a timeline
    that wants sound needs a separate OTIO audio track, which the adapter
    then emits as this:

        <clip name="01_hosts_full_audio" duration="218/15s" lane="-1">
            <gap name="Gap" duration="81944/15s">
                <audio ref="r2" duration="81944/15s"/>
            </gap>
        </clip>

    A <gap> spanning the whole 5462s asset, nested inside a 14.5s clip,
    with the audio hidden inside the gap. Resolve reads those ~190
    `name="Gap"` elements as a third piece of media to link, on top of the
    two real files, and reports "1 of 3 clips were not yet found" - there
    is no file called Gap.

    <asset-clip> is the right element: it references an asset directly and
    brings that asset's video *and* audio with it, which is exactly what
    Resolve itself exports. So each <clip><video ref=X/></clip> collapses
    to one <asset-clip ref=X/>, connected clips on other lanes become
    nested <asset-clip>s, and no gap-wrapped audio is needed at all.
    """
    for item in list(spine):
        if item.tag != "clip":
            continue
        video = item.find("video")
        if video is None:
            continue

        asset_clip = ET.Element("asset-clip")
        asset_clip.set("name", item.get("name", ""))
        asset_clip.set("ref", video.get("ref"))
        for attribute in ("offset", "duration", "start"):
            value = item.get(attribute)
            if value is not None:
                asset_clip.set(attribute, value)
        asset_clip.set("format", video.get("format") or "r1")
        if tc_format:
            asset_clip.set("tcFormat", tc_format)

        # Connected clips on other lanes: keep the ones that carry video
        # (the movie on lane 1) as nested <asset-clip>s, and drop the
        # gap-wrapped audio ones entirely - their audio now rides along
        # with the asset-clip that replaced them.
        for nested in item.findall("clip"):
            nested_video = nested.find("video")
            if nested_video is None:
                continue
            nested_clip = ET.SubElement(asset_clip, "asset-clip")
            nested_clip.set("name", nested.get("name", ""))
            nested_clip.set("ref", nested_video.get("ref"))
            for attribute in ("lane", "offset", "duration", "start"):
                value = nested.get(attribute)
                if value is not None:
                    nested_clip.set(attribute, value)
            nested_clip.set("format", nested_video.get("format") or "r1")

            # Pin the connected clip to its parent. A connected clip's
            # offset is expressed in the parent's own time base and, since
            # these are built to sit exactly on top of their parent for
            # the parent's whole length, it is the parent's `start` by
            # construction. The adapter derives it independently and lands
            # a frame early on the odd segment (2 of 89 here) - enough for
            # Resolve to treat that clip as not properly aligned and drop
            # its audio onto an extra track. Same for duration.
            if asset_clip.get("start") is not None:
                nested_clip.set("offset", asset_clip.get("start"))
            if asset_clip.get("duration") is not None:
                nested_clip.set("duration", asset_clip.get("duration"))

        for marker in item.findall("marker"):
            asset_clip.append(marker)

        spine.insert(list(spine).index(item), asset_clip)
        spine.remove(item)


def fix_up_fcpxml(output_path, event_name, rate, resolution):
    """Post-process the adapter's raw output into something Resolve takes:
    wrap <project> in <library><event>, drop the redundant bin items,
    name assets after their media, and set a 1-hour start timecode.

    The pinned fcpx_xml adapter writes <project> *and* every top-level bin
    item (one <asset-clip> per distinct clip name) as direct children of
    the <fcpxml> root, sibling to <resources> - never inside an <event>.
    Final Cut Pro tolerates <project> living there, but Resolve's importer
    doesn't - it fails outright with "Unable to find inherited value for
    key 'library'" on <project>, because it expects to inherit
    format/library context down through <library>/<event>/<project>.
    <asset-clip> bin items aren't valid loose at the document root either.
    See the inline comments below for what happens to each.

    Also sets tcStart="3600s" on <sequence> (Resolve/broadcast convention
    is to start timelines at 01:00:00:00, not 0, to leave room for
    negative-adjacent handles without going negative) - the adapter never
    writes this at all (it doesn't read `Timeline.global_start_time`), so
    it has to be added here too. tcFormat is "DF" only for 29.97fps (the
    one rate in SUPPORTED_FPS with a real drop-frame convention); "NDF"
    otherwise. "3600s" is deliberately a plain rational-seconds value, not
    a frame count - FCPXML times are always expressed as rational
    seconds, and the adapter's own gap-writing code uses this identical
    "3600s" idiom (see `_element_for_gap()` in the installed package) - so
    it's valid input at every supported project rate without needing any
    frame-rounding math here.
    """
    tree = ET.parse(output_path)
    root = tree.getroot()
    resources = root.find("resources")
    if resources is None:
        raise SystemExit(
            f"Expected a <resources> element in {output_path}, found none - "
            "the fcpx_xml adapter's output structure may have changed."
        )
    # Keep <project>; drop every other top-level child. Those others are
    # all <asset-clip> bin items - the adapter emits one per distinct clip
    # *name*, so ~200 of them, every one just re-pointing at the same two
    # <asset> resources (verified: the only refs in the whole file are the
    # two assets). Resolve turns each into its own Media Pool item, which
    # is what makes the pool look full of clips that aren't either source
    # file - they're named after segments ("03_panel"), not media. The
    # spine references the assets directly, so nothing in the timeline
    # needs these; dropping them leaves exactly one Media Pool item per
    # real source file, which is what test/VERIFY.md expects to relink.
    event = ET.Element("event", {"name": event_name})
    for child in list(root):
        if child is resources:
            continue
        root.remove(child)
        if child.tag == "project":
            event.append(child)
    project = event.find("project")
    if project is None:
        raise SystemExit(
            f"Expected a <project> element in {output_path}, found none - "
            "the fcpx_xml adapter's output structure may have changed."
        )
    # Name each asset after its actual media file. The adapter names an
    # <asset> after whichever clip happened to reference it first (so the
    # host source came out called "01_hosts_full"), which is what Resolve
    # then labels the Media Pool item - confusing when you're trying to
    # relink two known files.
    for asset in resources.findall("asset"):
        src = asset.get("src", "")
        if src:
            asset.set("name", unquote(src.rsplit("/", 1)[-1]))

        # Declare audio. The adapter derives hasAudio purely from whether a
        # clip sits on an OTIO *audio* track (see _add_asset() in the
        # installed adapter) - and this timeline deliberately has none, so
        # every asset comes out hasAudio="0" and imports silent no matter
        # what the media actually contains. An <asset-clip> only carries
        # sound when its asset declares sound, so set it here along with
        # the descriptors FCPXML expects to see next to it.
        asset.set("hasAudio", "1")
        asset.set("audioSources", AUDIO_SOURCES)
        asset.set("audioChannels", AUDIO_CHANNELS)
        asset.set("audioRate", AUDIO_RATE)

    library = ET.Element("library")
    library.append(event)
    root.append(library)

    sequence = project.find("sequence")
    if sequence is None:
        raise SystemExit(
            f"Expected a <sequence> element inside <project> in "
            f"{output_path}, found none - the fcpx_xml adapter's output "
            "structure may have changed."
        )
    sequence.set("tcStart", fcpx_seconds(TIMELINE_START_SECONDS))
    sequence.set("tcFormat", "DF" if rate == Fraction(30000, 1001) else "NDF")

    # Shift every top-level spine item to match tcStart. A spine child's
    # `offset` is its absolute position on the sequence's own timeline, so
    # once that timeline starts at 01:00:00:00 an item left at offset 0s
    # sits a full hour before the start - which Resolve won't place.
    # Only direct children of <spine> get shifted: a *nested* clip's
    # offset is anchored to its parent clip's `start` (its position within
    # the parent's own media), not to the sequence, so shifting those too
    # would desync every V2/A2 clip from the V1 clip it hangs off.
    spine = sequence.find("spine")
    if spine is None:
        raise SystemExit(
            f"Expected a <spine> element inside <sequence> in {output_path}, "
            "found none - the fcpx_xml adapter's output structure may have "
            "changed."
        )
    for item in spine:
        offset = item.get("offset")
        if offset is not None:
            item.set(
                "offset",
                fcpx_seconds(parse_fcpx_seconds(offset) + TIMELINE_START_SECONDS),
            )

    rewrite_spine_as_asset_clips(spine, sequence.get("tcFormat"))

    # Give <format> real dimensions and a real name. The adapter only fills
    # these in when it can ffprobe the media (see format_name() in the
    # installed adapter), and ffprobe isn't a dependency here - so without
    # this the single <format> both assets inherit comes out as
    # `<format id="r1" frameDuration="1/30s" name=""/>`: no width, no
    # height, and an empty name attribute. Resolve needs the frame size to
    # conform a clip, and an empty name is worse than an absent one, so
    # fill both from sources.json's `resolution` rather than leaving the
    # importer to guess.
    for format_element in resources.findall("format"):
        format_element.set("width", str(resolution["width"]))
        format_element.set("height", str(resolution["height"]))
        format_element.set("name", fcpx_format_name(resolution["height"], rate))

    ET.indent(tree, space="    ")
    body = ET.tostring(root, encoding="unicode")
    with open(output_path, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write("<!DOCTYPE fcpxml>\n\n")
        f.write(body)
        f.write("\n")


def write_timeline(timeline, output_format, rate, resolution):
    """Write the timeline to test/cut.<ext> in the requested format."""
    output_path = OUTPUT_PATHS[output_format]
    if output_format == "fcpxml":
        patch_frame_duration_table(rate)
        otio.adapters.write_to_file(timeline, output_path, adapter_name="fcpx_xml")
        fix_up_fcpxml(
            output_path,
            event_name=timeline.name,
            rate=rate,
            resolution=resolution,
        )
    elif output_format == "edl":
        # cmx_3600 is a core OTIO adapter (unlike fcpx_xml, it never lived
        # in opentimelineio_contrib), so this path doesn't touch any of the
        # 0.16.0-pinned/contrib-specific machinery above - just plain
        # otio.adapters.write_to_file(). See README for the caveat that
        # current (post-0.16.0) OTIO releases moved cmx_3600 out of the
        # core wheel into the separate `otio-cmx3600-adapter` package.
        #
        # cmx_3600's writer hard-requires exactly one video track (and
        # silently discards audio tracks - see README). V2 only exists for
        # PIP-style layouts and would push the count to two, so it's
        # dropped here; V1/A1/A2 go through unchanged. deepcopy() avoids
        # reparenting tracks that already belong to `timeline`.
        edl_timeline = otio.schema.Timeline(name=timeline.name)
        edl_timeline.global_start_time = timeline.global_start_time
        for track in timeline.tracks:
            if track.name != "V2":
                edl_timeline.tracks.append(track.deepcopy())
        otio.adapters.write_to_file(
            edl_timeline, output_path, adapter_name="cmx_3600", rate=float(rate)
        )
    else:
        raise SystemExit(f"Unhandled --format {output_format!r}.")
    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources", default="test/sources.json", help="Path to sources.json"
    )
    parser.add_argument(
        "--edit", default="test/edit.json", help="Path to edit.json"
    )
    parser.add_argument(
        "--format",
        choices=["both", "fcpxml", "edl"],
        default="both",
        help=(
            "Output format (default: both - writes test/cut.fcpxml and "
            "test/cut.edl from the same timeline in one run)."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["compact", "inplace"],
        default="compact",
        help=(
            "compact: append segments back-to-back, no gaps (default; the "
            "real use case - e.g. a 2-hour source becomes a 40-minute cut). "
            "inplace: keep segments at their source positions with gaps "
            "(for reviewing selections against the original)."
        ),
    )
    args = parser.parse_args()

    with open(args.sources) as f:
        sources = json.load(f)
    with open(args.edit) as f:
        segments = json.load(f)

    # Correct each media path's capitalisation against the disk before it
    # gets baked into a URL, and say so loudly - a case-only mismatch is
    # invisible from Python on macOS but makes Resolve report the media as
    # missing. See resolve_true_case().
    for key in ("host_clip", "movie_clip"):
        corrected = resolve_true_case(sources[key])
        if corrected != sources[key]:
            print(
                f"Note: corrected {key} case to match disk:\n"
                f"  {sources[key]}\n"
                f"  -> {corrected}\n"
                f"  (fix this in {args.sources} so it doesn't come back)"
            )
            sources[key] = corrected

    rate = resolve_rate(sources["fps"])
    timeline = build_timeline(sources, segments, rate, mode=args.mode)

    # One timeline, written out once per requested format. Neither writer
    # mutates `timeline` (the EDL path deepcopies the tracks it keeps), so
    # both read the same source of truth and can't drift apart.
    formats = ["fcpxml", "edl"] if args.format == "both" else [args.format]
    clip_count = sum(
        1 for item in timeline.tracks[0] if isinstance(item, otio.schema.Clip)
    )

    # Report movie coverage. movie_offset_seconds can be arbitrarily large,
    # and segments that land before the movie started simply get a Gap on
    # V2 rather than an error - correct, but silent, so a mistyped offset
    # would quietly strip the movie off most of the cut. Say what happened.
    secondary_track = next(
        (track for track in timeline.tracks if track.name == "V2"), None
    )
    if secondary_track is not None:
        with_movie = sum(
            1 for item in secondary_track if isinstance(item, otio.schema.Clip)
        )
        missing = clip_count - with_movie
        offset = sources.get("movie_offset_seconds")
        print(
            f"Movie on {with_movie}/{clip_count} segments "
            f"(movie_offset_seconds={offset})"
        )
        if missing:
            print(
                f"  {missing} segment(s) start before the movie did, so they "
                f"have hosts only.\n"
                f"  Those are the segments with start < {offset}s in "
                f"{args.edit}."
            )
        if with_movie == 0:
            print(
                "  WARNING: no segment gets the movie at all - "
                "movie_offset_seconds may be wrong (too large), or in the "
                "wrong direction. Use a negative value if the movie started "
                "BEFORE the host recording."
            )
    for output_format in formats:
        output_path = write_timeline(
            timeline, output_format, rate, sources["resolution"]
        )
        print(
            f"Wrote {clip_count} clips to {output_path} "
            f"(--format {output_format} --mode {args.mode})"
        )


if __name__ == "__main__":
    sys.exit(main())
