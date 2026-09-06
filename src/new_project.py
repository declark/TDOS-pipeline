#!/usr/bin/env python3
"""Create a new episode's project config, interactively.

Prompts for the movie name and the paths to the two clips that need
transcribing - the hosts' reaction recording and the movie file - and writes
them to cuts/<slug>.media.json, e.g. "Repo Man" -> cuts/repo-man.media.json.
That slug matches the one used by the cuts/<episode>.json file this episode
will eventually get (see cuts/repo-man.json), so the two files sit side by
side once cut selection starts.

transcribe.py --project cuts/<slug>.media.json reads this file back and
transcribes both clips.

Usage:
    python3 src/new_project.py
"""

import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUTS_DIR = os.path.join(REPO_ROOT, "cuts")


def slugify(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.strip().lower())
    return slug.strip("-")


def prompt(label, required=True):
    while True:
        value = input(label).strip()
        if value or not required:
            return value
        print("  Required.", file=sys.stderr)


def clean_path(value):
    """Strip the quotes Windows' "Copy as path" wraps around a pasted path."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1]
    return value.strip()


def main():
    title = prompt("Movie name: ")
    slug = slugify(title)
    if not slug:
        sys.exit("error: movie name has no usable characters for a filename")

    out_path = os.path.join(CUTS_DIR, "{}.media.json".format(slug))
    if os.path.exists(out_path):
        overwrite = prompt(
            "{} already exists - overwrite? [y/N]: ".format(out_path), required=False
        )
        if overwrite.lower() not in ("y", "yes"):
            sys.exit("Aborted, nothing written.")

    reaction_media = clean_path(prompt("Reaction recording path (hosts): "))
    movie_media = clean_path(prompt("Movie file path: "))

    for label, path in (("Reaction recording", reaction_media), ("Movie file", movie_media)):
        if not os.path.exists(path):
            print("  WARNING: {} not found at {!r} (saving anyway).".format(label, path),
                  file=sys.stderr)

    config = {
        "title": title,
        "reaction_media": reaction_media,
        "movie_media": movie_media,
    }

    os.makedirs(CUTS_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print("\nWrote {}".format(out_path))
    print("Next: python3 src/transcribe.py --project {}".format(out_path))


if __name__ == "__main__":
    main()
