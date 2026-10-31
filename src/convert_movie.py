#!/usr/bin/env python3
"""Convert a project's .mkv movie into a file DaVinci Resolve takes cleanly.

Resolve is unreliable with Matroska, and a film's 5.1 track is the wrong
shape for a reaction edit, so the very first step for an .mkv is to rewrite it
as <movie>.mov beside the original:

  - video: copied as-is when it is H.264 or HEVC (no quality loss, a couple of
    minutes for a feature). Anything else is re-encoded to H.264.
  - audio: the film's main track (not a commentary), downmixed to stereo
    48 kHz 16-bit PCM.
  - both start at exactly 0, in sync. An .mkv often starts one stream a few
    frames after the other; the audio is padded or trimmed to line up with
    the first video frame, so a time in the .mov is the same time in Resolve.

The project config is then pointed at the .mov (the original path is kept
under "movie_source"), so transcribe.py and everything after it work from the
converted file:

    python src/convert_movie.py --project cuts/repo-man.media.json

A movie that isn't an .mkv is left alone. Needs no ffmpeg install: it uses
PyAV, which comes with faster-whisper (requirements-transcribe.txt).
"""

import argparse
import itertools
import json
import os
import sys
from fractions import Fraction

COPY_CODECS = {"h264", "hevc"}
AUDIO_RATE = 48000
PROGRESS_STEP = 5      # percent
START_PROBE_PACKETS = 64   # the first frame shown is somewhere in the first few packets
MIN_REORDER_DELAY = 4      # frames; more than x264 / x265 reorder by default
STALE_TRANSCRIPT_SECONDS = 0.02   # under a frame: an old transcript is still good


def needs_converting(path):
    return os.path.splitext(path or "")[1].lower() == ".mkv"


def converted_path(path):
    return os.path.splitext(path)[0] + ".mov"


def pick_audio(container):
    """The film's own track: the first one that isn't a commentary."""
    streams = list(container.streams.audio)
    if not streams:
        return None
    for stream in streams:
        if "commentary" not in (stream.metadata.get("title") or "").lower():
            return stream
    return streams[0]


def first_times(source, video_index, audio_index):
    """(first video pts in its time base, first audio sample in seconds or None).

    Measured from the file rather than read from the header: a stream's
    declared start_time counts decode order and encoder priming, which is not
    when its first frame or sample is actually presented.
    """
    import av

    with av.open(source) as container:
        video = container.streams[video_index]
        early = [p.pts for p in itertools.islice(
            (p for p in container.demux(video) if p.pts is not None), START_PROBE_PACKETS)]
        if not early:
            sys.exit("error: {} has no readable video".format(source))
        video_start = min(early)
    if audio_index is None:
        return video_start, None
    with av.open(source) as container:
        audio = container.streams[audio_index]
        frame = next(container.decode(audio), None)
        audio_start = float(frame.pts * audio.time_base) if frame is not None else None
    return video_start, audio_start


class DecodeTimes:
    """Decode timestamps for copied video packets, worked out from their pts.

    Matroska stores presentation times only, and the reader leaves dts unset on
    some packets (the first keyframe among them), but a .mov needs one on every
    packet. This is the reorder buffer libavformat itself uses: with frames
    reordered by up to `delay`, each dts is the smallest pts still waiting.
    """

    def __init__(self, delay):
        self.delay = delay
        self.waiting = None

    def next(self, pts, duration):
        if self.waiting is None:
            self.waiting = [pts - i * duration for i in range(self.delay + 1)]
        else:
            self.waiting[0] = pts
        self.waiting.sort()
        return self.waiting[0]


def convert(source, target):
    """Write `target` from `source`. Returns how far the audio was moved, in
    seconds: positive if it was padded, negative if trimmed."""
    import av
    import numpy

    partial = os.path.splitext(target)[0] + ".converting.mov"
    if os.path.exists(partial):
        os.remove(partial)

    with av.open(source) as inp, av.open(partial, "w", format="mov") as out:
        if not inp.streams.video:
            sys.exit("error: {} has no video stream".format(source))
        vin = inp.streams.video[0]
        ain = pick_audio(inp)
        video_start, audio_start = first_times(
            source, vin.index, ain.index if ain is not None else None)
        if audio_start is None:
            ain = None
        duration = float(inp.duration or 0) / av.time_base
        video_codec = vin.codec_context.name
        copy_video = video_codec in COPY_CODECS

        if copy_video:
            vout = out.add_stream_from_template(vin)
            if video_codec == "hevc":
                vout.codec_context.codec_tag = "hvc1"   # the tag QuickTime-style readers expect
            print("Video: {} copied as-is.".format(video_codec))
        else:
            rate = vin.average_rate or Fraction(24000, 1001)
            vout = out.add_stream("libx264", rate=rate, options={"crf": "16", "preset": "medium"})
            vout.width, vout.height = vin.codec_context.width, vin.codec_context.height
            vout.pix_fmt = "yuv420p"
            print("Video: {} isn't one Resolve cuts well; re-encoding to H.264 (slow).".format(
                video_codec))

        if ain is not None:
            aout = out.add_stream("pcm_s16le", rate=AUDIO_RATE, layout="stereo")
            resampler = av.AudioResampler(format="s16", layout="stereo", rate=AUDIO_RATE)
            print("Audio: stream {} ({}, {}) downmixed to stereo PCM.".format(
                ain.index, ain.codec_context.name, ain.codec_context.layout.name))
        else:
            print("Audio: none in the source.")

        # Samples to add (audio starts after the first frame) or drop (before it).
        lead = 0
        if ain is not None:
            lead = round((audio_start - float(video_start * vin.time_base)) * AUDIO_RATE)
        lead_seconds = lead / AUDIO_RATE
        frame_ticks = max(1, round(1 / (vin.average_rate or Fraction(24000, 1001)) / vin.time_base))
        decode_times = DecodeTimes(max(vin.codec_context.has_b_frames, MIN_REORDER_DELAY))
        if lead:
            print("Audio starts {:.3f}s {} the video; {} to line up.".format(
                abs(lead) / AUDIO_RATE, "after" if lead > 0 else "before",
                "padded with silence" if lead > 0 else "trimmed"))
        samples_out = 0

        def write_audio(samples):
            """Encode interleaved stereo int16 samples, continuing from the last."""
            nonlocal samples_out
            if not len(samples):
                return
            frame = av.AudioFrame.from_ndarray(samples.reshape(1, -1), format="s16", layout="stereo")
            frame.sample_rate = AUDIO_RATE
            frame.pts = samples_out
            frame.time_base = Fraction(1, AUDIO_RATE)
            samples_out += len(samples)
            for packet in aout.encode(frame):
                out.mux(packet)

        def resampled(frame):
            nonlocal lead
            for piece in resampler.resample(frame):
                samples = piece.to_ndarray().reshape(-1, 2)
                if lead < 0:
                    drop = min(-lead, len(samples))
                    samples, lead = samples[drop:], lead + drop
                write_audio(samples)

        if lead > 0:
            write_audio(numpy.zeros((lead, 2), dtype=numpy.int16))

        next_report = PROGRESS_STEP
        streams = [vin] + ([ain] if ain is not None else [])
        for packet in inp.demux(streams):
            if packet.stream is vin:
                if packet.pts is not None and duration:
                    done = 100.0 * float((packet.pts - video_start) * vin.time_base) / duration
                    if done >= next_report:
                        print("  {:3d}%".format(min(int(done), 100)))
                        next_report = (int(done) // PROGRESS_STEP + 1) * PROGRESS_STEP
                if copy_video:
                    if packet.pts is None:      # the empty packet that ends the stream
                        continue
                    packet.pts -= video_start
                    packet.dts = decode_times.next(packet.pts, packet.duration or frame_ticks)
                    if packet.dts > packet.pts:
                        sys.exit("error: {} reorders frames further than expected; "
                                 "it can't be copied as-is.".format(source))
                    packet.stream = vout
                    out.mux(packet)
                else:
                    for frame in packet.decode():
                        frame.pts -= video_start
                        frame.pict_type = 0     # let the encoder choose
                        for encoded in vout.encode(frame.reformat(format="yuv420p")):
                            out.mux(encoded)
            else:
                for frame in packet.decode():
                    resampled(frame)

        if not copy_video:
            for encoded in vout.encode(None):
                out.mux(encoded)
        if ain is not None:
            resampled(None)
            for packet in aout.encode(None):
                out.mux(packet)

    os.replace(partial, target)
    with av.open(target) as check:
        print("Wrote {} ({:.1f} GB, {:.1f} min; the source is {:.1f} min).".format(
            target, os.path.getsize(target) / 1e9,
            float(check.duration or 0) / av.time_base / 60.0, duration / 60.0))
    return lead_seconds


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True,
                        help="Project config JSON (see src/new_project.py).")
    parser.add_argument("--force", action="store_true",
                        help="Convert again even if the .mov already exists.")
    args = parser.parse_args(argv)

    if not os.path.exists(args.project):
        sys.exit("error: project file not found: {}".format(args.project))
    with open(args.project, "r", encoding="utf-8") as handle:
        config = json.load(handle)

    source = config.get("movie_media") or ""
    if args.force and not needs_converting(source) and needs_converting(config.get("movie_source")):
        source = config["movie_source"]
    if not needs_converting(source):
        print("{} isn't an .mkv - nothing to convert.".format(source or "movie_media"))
        return 0
    if not os.path.exists(source):
        sys.exit("error: movie file not found: {}".format(source))

    target = converted_path(source)
    reaction = config.get("reaction_media") or ""
    if os.path.normcase(os.path.abspath(target)) == os.path.normcase(os.path.abspath(reaction)):
        sys.exit("error: the converted movie would overwrite the reaction recording ({}). "
                 "Rename one of them.".format(target))

    if os.path.exists(target) and not args.force:
        print("{} already exists - using it (--force to convert again).".format(target))
    else:
        print("Converting {}".format(source))
        moved = convert(source, target)
        # A transcript made from the .mkv shares the .mov's name, so it would be
        # picked up as this file's - with every time off by the audio's move.
        if abs(moved) >= STALE_TRANSCRIPT_SECONDS and os.path.exists(
                os.path.splitext(target)[0] + ".words.json"):
            print("NOTE: the existing transcript was made from the .mkv, whose audio ran "
                  "{:.3f}s {} this file's. Transcribe again before cutting from the .mov."
                  .format(abs(moved), "ahead of" if moved > 0 else "behind"))

    config["movie_media"] = target
    config["movie_source"] = source
    with open(args.project, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print("{} now points at the .mov.".format(args.project))
    print("Next: python src/transcribe.py --project {}".format(args.project))
    return 0


if __name__ == "__main__":
    sys.exit(main())
