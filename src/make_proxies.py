#!/usr/bin/env python3
"""Make small, seekable copies of a project's two recordings for the shorts editor.

The originals are big (a 4K .mov runs past 10GB) and carry PCM audio, which
the desktop app's player can't seek smoothly or play at all. This writes,
beside each original:

    <media>.proxy.mp4    640 px wide H.264, a keyframe every half second, AAC
    <media>.peaks.json   the audio's loudness, 25 values a second, for waveforms

Time zero in the proxy is the original's first video frame - the same zero
src/render_shorts.py uses - so a time in a cut list means the same moment in
both. The editor plays proxies; renders still read the originals.

    python src/make_proxies.py --project cuts/<slug>.media.json
    python src/make_proxies.py --project cuts/<slug>.media.json --force

A proxy newer than its original is left alone unless --force. Needs PyAV and
numpy (requirements-transcribe.txt).
"""

import argparse
import json
import os
import sys
import time
from fractions import Fraction

from convert_movie import first_times, pick_audio

PROXY_WIDTH = 640
AUDIO_RATE = 48000
PEAKS_PER_SECOND = 25
PROJECT_MEDIA_KEYS = ("reaction_media", "movie_media")


def proxy_paths(media_path):
    """(proxy video, peaks) for an original."""
    base = os.path.splitext(media_path)[0]
    return base + ".proxy.mp4", base + ".peaks.json"


def up_to_date(media_path):
    source = os.path.getmtime(media_path)
    return all(os.path.exists(p) and os.path.getmtime(p) >= source for p in proxy_paths(media_path))


class Peaks:
    """RMS loudness per 1/PEAKS_PER_SECOND of the audio, in whole dBFS."""

    def __init__(self):
        import numpy

        self.per = AUDIO_RATE // PEAKS_PER_SECOND
        self.carry = numpy.zeros(0, dtype=numpy.float32)
        self.values = []

    def add(self, mono):
        import numpy

        data = numpy.concatenate([self.carry, mono])
        whole = len(data) // self.per * self.per
        if whole:
            power = (data[:whole].reshape(-1, self.per) ** 2).mean(axis=1)
            db = numpy.clip(numpy.round(10 * numpy.log10(numpy.maximum(power, 1e-10))), -90, 0)
            self.values.extend(int(v) for v in db)
        self.carry = data[whole:]


def make_proxy(media_path):
    import av
    import numpy

    proxy_path, peaks_path = proxy_paths(media_path)
    partial = proxy_path + ".partial.mp4"
    started = time.time()

    source = av.open(media_path)
    video = source.streams.video[0]
    video.thread_type = "AUTO"
    audio = pick_audio(source)
    first_pts, _ = first_times(media_path, video.index, None)
    zero = float(first_pts * video.time_base)
    rate = video.average_rate or Fraction(30)
    duration = float(source.duration or 0) / av.time_base
    height = int(round(PROXY_WIDTH * video.height / video.width / 2)) * 2

    out = av.open(partial, "w", format="mp4", options={"movflags": "+faststart"})
    out_video = out.add_stream("libx264", rate=rate, options={
        "preset": "veryfast", "crf": "28", "tune": "fastdecode",
        "g": str(max(1, int(round(float(rate) / 2)))), "keyint_min": "1"})
    out_video.width, out_video.height, out_video.pix_fmt = PROXY_WIDTH, height, "yuv420p"
    out_audio = None
    if audio is not None:
        out_audio = out.add_stream("aac", rate=AUDIO_RATE, layout="stereo")
        out_audio.bit_rate = 128000
    resampler = av.AudioResampler(format="flt", layout="stereo", rate=AUDIO_RATE)
    peaks = Peaks()

    last_pts = -1
    samples_written = 0     # audio samples out, counted from the video's zero
    next_report = 5

    def write_audio(stereo):
        nonlocal samples_written
        if not len(stereo):
            return
        frame = av.AudioFrame.from_ndarray(numpy.ascontiguousarray(stereo.T), format="fltp",
                                           layout="stereo")
        frame.sample_rate = AUDIO_RATE
        frame.pts = samples_written
        for packet in out_audio.encode(frame):
            out.mux(packet)
        peaks.add(stereo.mean(axis=1))
        samples_written += len(stereo)

    streams = [video] + ([audio] if audio is not None else [])
    for packet in source.demux(*streams):
        for frame in packet.decode():
            if frame.pts is None:
                continue
            seconds = float(frame.pts * frame.time_base) - zero
            if packet.stream is video:
                if seconds < -1e-3:
                    continue
                pts = max(int(round(seconds * float(rate))), last_pts + 1)
                last_pts = pts
                small = frame.reformat(width=PROXY_WIDTH, height=height, format="yuv420p",
                                       interpolation="BILINEAR")
                small.pts, small.time_base = pts, Fraction(1) / rate
                for out_packet in out_video.encode(small):
                    out.mux(out_packet)
                if duration and 100 * seconds / duration >= next_report:
                    print("  {:3d}%  ({:.0f}s elapsed)".format(next_report, time.time() - started),
                          flush=True)
                    next_report += 5
            else:
                for piece in resampler.resample(frame):
                    stereo = piece.to_ndarray().reshape(-1, 2)
                    # Line the audio up on the video's zero: drop what comes
                    # before it, fill a late start with silence.
                    at = int(round(seconds * AUDIO_RATE))
                    if samples_written == 0 and at > 0:
                        write_audio(numpy.zeros((at, 2), dtype=numpy.float32))
                    elif at < 0 and samples_written == 0:
                        stereo = stereo[min(-at, len(stereo)):]
                    write_audio(stereo)
                    seconds += len(piece.to_ndarray().reshape(-1, 2)) / AUDIO_RATE

    for out_packet in out_video.encode(None):
        out.mux(out_packet)
    if out_audio is not None:
        for out_packet in out_audio.encode(None):
            out.mux(out_packet)
    out.close()
    source.close()

    os.replace(partial, proxy_path)
    with open(peaks_path, "w", encoding="utf-8") as handle:
        json.dump({"rate": PEAKS_PER_SECOND, "db": peaks.values}, handle, separators=(",", ":"))
    print("  Wrote {} and {} in {:.0f}s.".format(
        os.path.basename(proxy_path), os.path.basename(peaks_path), time.time() - started))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True, help="Project config (cuts/<slug>.media.json).")
    parser.add_argument("--force", action="store_true", help="Remake proxies that are up to date.")
    args = parser.parse_args(argv)

    if not os.path.exists(args.project):
        print("ERROR: project file not found: {}".format(args.project), file=sys.stderr)
        return 1
    with open(args.project, "r", encoding="utf-8") as handle:
        media = json.load(handle)

    for key in PROJECT_MEDIA_KEYS:
        path = media.get(key)
        if not path or not os.path.exists(path):
            print("ERROR: {} not found ({!r}).".format(key, path), file=sys.stderr)
            return 1
    for key in PROJECT_MEDIA_KEYS:
        path = media[key]
        print("{}: {}".format(key, path), flush=True)
        if up_to_date(path) and not args.force:
            print("  Proxy is up to date.")
            continue
        try:
            make_proxy(path)
        except ImportError as error:
            print("ERROR: {} - pip install -r requirements-transcribe.txt".format(error), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
