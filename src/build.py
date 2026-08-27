#!/usr/bin/env python3
"""Build an OTIO timeline from edit.json/sources.json and export it as FCPXML."""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from fractions import Fraction
from urllib.parse import quote

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


def source_for_layout(layout):
    """Pick which physical source clip a layout's segment is cut from.

    This test builds a single video track with one clip per segment, so
    each segment can only reference one media file. Layouts are assumed to
    follow a `<source>_<detail>` or `<detail>_<source>` naming convention
    (e.g. "movie_full", "pip_host"); anything not explicitly tagged
    "movie" falls back to the host source. Real PIP compositing (both
    sources on screen at once) is out of scope for this test.
    """
    tokens = layout.split("_")
    if "movie" in (tokens[0], tokens[-1]):
        return "movie"
    return "host"


def build_media_references(segments, sources, rate):
    """Compute one ExternalReference per source, sized to cover all clips."""
    target_urls = {
        "host": to_media_target_url(sources["host_clip"]),
        "movie": to_media_target_url(sources["movie_clip"]),
    }
    max_end_frame = {"host": 0, "movie": 0}
    for segment in segments:
        source_name = source_for_layout(segment["layout"])
        end_frame = seconds_to_frame(segment["end"], rate)
        max_end_frame[source_name] = max(max_end_frame[source_name], end_frame)

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
    """
    media_references = build_media_references(segments, sources, rate)
    frame_ranges = validate_segments(segments, rate)

    track = otio.schema.Track(name="V1", kind=otio.schema.TrackKind.Video)
    current_frame = 0

    for index, (segment, (start_frame, end_frame)) in enumerate(
        zip(segments, frame_ranges)
    ):
        if mode == "inplace":
            gap_frames = start_frame - current_frame
            if gap_frames > 0:
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
        source_name = source_for_layout(layout)
        clip = otio.schema.Clip(
            name=f"{index + 1:02d}_{layout}",
            source_range=otio.opentime.TimeRange(
                start_time=otio.opentime.RationalTime(start_frame, float(rate)),
                duration=otio.opentime.RationalTime(
                    end_frame - start_frame, float(rate)
                ),
            ),
            media_reference=media_references[source_name],
        )
        clip.markers.append(
            otio.schema.Marker(
                name=layout,
                marked_range=otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(0, float(rate)),
                    duration=clip.duration(),
                ),
            )
        )
        # Only read by the cmx_3600 (EDL) adapter; the fcpx_xml adapter
        # ignores unrecognized metadata namespaces. See REEL_NAMES.
        clip.metadata["cmx_3600"] = {"reel": REEL_NAMES[source_name]}
        track.append(clip)
        current_frame = end_frame

    timeline = otio.schema.Timeline(name="tdos_pipeline_verify_cut")
    timeline.global_start_time = otio.opentime.RationalTime(0, float(rate))
    timeline.tracks.append(track)
    return timeline


def wrap_fcpxml_project_in_library(output_path, event_name):
    """Nest <project> inside <library><event>, which Resolve requires.

    The pinned fcpx_xml adapter writes <project> as a direct child of the
    <fcpxml> root, sibling to <resources>. Final Cut Pro tolerates that, but
    Resolve's importer doesn't - it fails with "Unable to find inherited
    value for key 'library'" because it expects to inherit format/library
    context down through <library>/<event>/<project>, and there's no
    <library> ancestor to inherit from. This rewrites the file to add the
    wrapper after the fact, since the adapter itself never had library/event
    involved in the first place.
    """
    tree = ET.parse(output_path)
    root = tree.getroot()
    project = root.find("project")
    if project is None:
        raise SystemExit(
            f"Expected a <project> element in {output_path}, found none - "
            "the fcpx_xml adapter's output structure may have changed."
        )
    root.remove(project)
    event = ET.Element("event", {"name": event_name})
    event.append(project)
    library = ET.Element("library")
    library.append(event)
    root.append(library)

    ET.indent(tree, space="    ")
    body = ET.tostring(root, encoding="unicode")
    with open(output_path, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write("<!DOCTYPE fcpxml>\n\n")
        f.write(body)
        f.write("\n")


def write_timeline(timeline, output_format, rate):
    """Write the timeline to test/cut.<ext> in the requested format."""
    output_path = OUTPUT_PATHS[output_format]
    if output_format == "fcpxml":
        patch_frame_duration_table(rate)
        otio.adapters.write_to_file(timeline, output_path, adapter_name="fcpx_xml")
        wrap_fcpxml_project_in_library(output_path, event_name=timeline.name)
    elif output_format == "edl":
        # cmx_3600 is a core OTIO adapter (unlike fcpx_xml, it never lived
        # in opentimelineio_contrib), so this path doesn't touch any of the
        # 0.16.0-pinned/contrib-specific machinery above - just plain
        # otio.adapters.write_to_file(). See README for the caveat that
        # current (post-0.16.0) OTIO releases moved cmx_3600 out of the
        # core wheel into the separate `otio-cmx3600-adapter` package.
        otio.adapters.write_to_file(
            timeline, output_path, adapter_name="cmx_3600", rate=float(rate)
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
        choices=["fcpxml", "edl"],
        default="fcpxml",
        help="Output format (default: fcpxml)",
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

    rate = resolve_rate(sources["fps"])
    timeline = build_timeline(sources, segments, rate, mode=args.mode)
    output_path = write_timeline(timeline, args.format, rate)

    clip_count = sum(
        1 for item in timeline.tracks[0] if isinstance(item, otio.schema.Clip)
    )
    print(
        f"Wrote {clip_count} clips to {output_path} "
        f"(--format {args.format} --mode {args.mode})"
    )


if __name__ == "__main__":
    sys.exit(main())
