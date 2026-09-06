"""Transcribe a media file to word-level timestamps for precise cut selection.

Runs faster-whisper (CTranslate2) over an audio/video file and writes a JSON
transcript with per-segment AND per-word start/end times in seconds. The word
timings are the point: segment selection can snap in/out points to word
boundaries instead of the hand-typed placeholder seconds in test/edit.json, so
cuts land on speech rather than mid-word.

    python src/transcribe.py path/to/reaction.mp4

Output defaults to the input path with a `.words.json` suffix
(reaction.mp4 -> reaction.words.json) next to the source.

An episode needs two clips transcribed - the hosts' reaction recording and
the movie itself - so --project reads both paths from a project config (see
src/new_project.py) and transcribes them one after another, each still
writing its own <media>.words.json next to its source:

    python src/transcribe.py --project cuts/repo-man.media.json

Notes on the choices here:
  - device=cpu / compute_type=int8: this box has an AMD GPU, and CTranslate2
    has no ROCm path on Windows, so CPU int8 is the only option. int8 is the
    fastest CPU mode and accurate enough for timing.
  - vad_filter: Silero VAD drops non-speech gaps before decoding. It both
    speeds things up and stops Whisper from hallucinating text over silence
    (a real problem on long movie stretches with music but no dialogue).
  - No ffmpeg needed: faster-whisper decodes the file via bundled PyAV.
"""

import argparse
import json
import os
import sys

from faster_whisper import WhisperModel


def transcribe(media, model_size, device, compute_type, language, vad):
    # Loading the model downloads it from HuggingFace on first use and caches
    # it under ~/.cache/huggingface; subsequent runs are offline.
    print(
        f"Loading model '{model_size}' ({device}/{compute_type})...",
        file=sys.stderr,
    )
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    # transcribe() returns a lazy generator - the actual decoding happens as we
    # iterate segments below, which is why progress prints there and not here.
    segments_iter, info = model.transcribe(
        media,
        language=language,          # None => autodetect
        word_timestamps=True,       # the whole reason we're here
        vad_filter=vad,
    )
    print(
        f"Language: {info.language} (p={info.language_probability:.2f}), "
        f"duration: {info.duration:.1f}s",
        file=sys.stderr,
    )

    segments = []
    for seg in segments_iter:
        words = [
            {
                "start": round(w.start, 3),
                "end": round(w.end, 3),
                "word": w.word,
                "prob": round(w.probability, 3),
            }
            for w in (seg.words or [])
        ]
        segments.append(
            {
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text.strip(),
                "words": words,
            }
        )
        # One line per segment so a long movie shows progress, not a dead prompt.
        print(f"  [{seg.start:7.2f} -> {seg.end:7.2f}] {seg.text.strip()}", file=sys.stderr)

    return {
        "media": os.path.abspath(media),
        "model": model_size,
        "language": info.language,
        "duration": round(info.duration, 3),
        "segments": segments,
    }


PROJECT_MEDIA_KEYS = ("reaction_media", "movie_media")


def clean_path(value):
    """Strip the quotes Windows' "Copy as path" wraps around a pasted path."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1]
    return value


def load_project_clips(path):
    if not os.path.exists(path):
        sys.exit(f"error: project file not found: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        config = json.load(handle)

    clips = [
        (key, clean_path(config[key])) for key in PROJECT_MEDIA_KEYS if config.get(key)
    ]
    if not clips:
        sys.exit(
            f"error: {path} has none of {PROJECT_MEDIA_KEYS} set"
        )
    return clips


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("media", nargs="?",
                        help="Audio or video file to transcribe. Omit when using --project.")
    parser.add_argument("--project", default=None,
                        help="Project config JSON (see src/new_project.py); transcribes "
                             "its reaction_media and movie_media, one after another.")
    parser.add_argument(
        "--model",
        default="small.en",
        help=(
            "Whisper model size. small.en (default) is a good speed/accuracy "
            "balance for English on CPU; base.en is faster, medium.en more "
            "accurate. Drop the .en for non-English (multilingual) audio."
        ),
    )
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                        help="Inference device (default: cpu - no NVIDIA GPU here).")
    parser.add_argument("--compute-type", default="int8",
                        help="CTranslate2 compute type (default: int8, fastest on CPU).")
    parser.add_argument("--language", default=None,
                        help="Force a language code (e.g. en). Default: autodetect.")
    parser.add_argument("--no-vad", action="store_true",
                        help="Disable the Silero VAD speech filter (on by default).")
    parser.add_argument("--output", default=None,
                        help="Output JSON path (default: <media>.words.json).")
    args = parser.parse_args()

    if args.project:
        if args.media or args.output:
            parser.error("--project can't be combined with a media path or --output")
        clips = [(key, path) for key, path in load_project_clips(args.project)]
    elif args.media:
        clips = [(None, args.media)]
    else:
        parser.error("a media path or --project is required")

    for key, media in clips:
        if not os.path.exists(media):
            sys.exit(f"error: media file not found: {media}")

        if key:
            print(f"\n--- {key}: {media} ---", file=sys.stderr)

        result = transcribe(
            media,
            model_size=args.model,
            device=args.device,
            compute_type=args.compute_type,
            language=args.language,
            vad=not args.no_vad,
        )

        out = args.output or (os.path.splitext(media)[0] + ".words.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nWrote {len(result['segments'])} segments -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
