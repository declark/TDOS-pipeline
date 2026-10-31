#!/usr/bin/env python3
"""The TDOS pipeline as a desktop window.

Runs the same long-cut steps as the terminal - new_project, transcribe, the
research-film / select-cuts / review-cuts skills, check_cuts and
build_timeline - from buttons, and shows where each episode stands. Every
step is still the script or skill in this repo, started as a subprocess, so
the terminal workflow is unchanged.

Usage:
    python ui/app.py            (or double-click "TDOS Pipeline.bat")

Needs requirements-ui.txt installed, and Claude Code on PATH for the three
cut-selection stages.
"""

import functools
import json
import os
import re
import shutil
import sys
import threading
import webbrowser

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import webview  # noqa: E402

import projects  # noqa: E402
import render_shorts  # noqa: E402
import shorts_edit  # noqa: E402
from build_timeline import BuildError  # noqa: E402
from jobs import JobRunner  # noqa: E402
from media_server import MediaServer  # noqa: E402
from make_proxies import proxy_paths  # noqa: E402
from new_project import clean_path, project_path, slugify, write_project  # noqa: E402

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

MEDIA_FILE_TYPES = (
    "Media files (*.mov;*.mp4;*.mkv;*.avi;*.wav;*.m4a;*.mp3)",
    "All files (*.*)",
)

# --- the Claude stages --------------------------------------------------------
# Each is the repo's own skill, run headless. What a headless run may do without
# asking is listed here rather than skipping permission checks altogether; a
# denied call shows in the log, and this is the place to widen it.

CLAUDE_ALLOWED_TOOLS = [
    "Read", "Write", "Edit", "Glob", "Grep", "Skill", "WebSearch", "WebFetch",
    "Bash(python *)", "Bash(python3 *)", "Bash(py *)",
    "PowerShell(python *)", "PowerShell(py *)",
]

CLAUDE_SKILLS = {
    "research": ("Research", "research-film"),
    "select": ("Select cuts", "select-cuts"),
    "review": ("Review", "review-cuts"),
    "make_cuts": ("Research, select and review", "make-cuts"),
    "select_shorts": ("Select shorts", "select-shorts"),
    "short_feedback": ("Revise short", "select-shorts"),
}

MAX_FEEDBACK_CHARS = 4000

# Steps that rewrite cuts/<slug>.shorts.json; the editor can't save while one runs.
SHORTS_WRITERS = ("select_shorts", "short_feedback", "tighten_shorts")

NON_INTERACTIVE = (
    "This run was started from the desktop app, so nobody can answer questions. "
    "Don't ask any: where a skill says to ask the user, use the answers below, "
    "and if something else is missing, stop and say exactly what."
)


def claude_command():
    """The Claude Code executable, or None if it isn't installed."""
    found = shutil.which("claude")
    if not found:
        return None
    # npm's claude.cmd is a wrapper round this exe; calling the exe directly
    # keeps cmd.exe's quoting rules out of the argument list.
    exe = os.path.join(os.path.dirname(found), "node_modules", "@anthropic-ai",
                       "claude-code", "bin", "claude.exe")
    return exe if os.path.exists(exe) else found


def claude_prompt(action, slug, options):
    answers = []
    if action == "make_cuts":
        answers.append("Research sheet: {}.".format(
            "redo it even if one exists" if options.get("redo_research")
            else "keep the existing one if there is one"))
    if action == "research":
        answers.append("An existing research sheet may be replaced.")
    if action in ("select", "make_cuts"):
        answers.append("An existing cut list may be replaced.")
    if action == "select_shorts":
        answers.append("An existing shorts file may be replaced.")
    if action == "short_feedback":
        answers += [
            "",
            "This is a revision, not a fresh selection. cuts/{slug}.shorts.json already exists; "
            "a copy of it as it stands is in cuts/{slug}.shorts.prev.json.".format(slug=slug),
            "Revise only short {number} (\"{name}\") to address the feedback below, following "
            "config/SHORTS.md. Leave every other short and the order exactly as they are, write "
            "the result back to cuts/{slug}.shorts.json, then run "
            "`python src/check_cuts.py --cuts cuts/{slug}.shorts.json` and fix any FAIL.".format(
                slug=slug, number=options["number"], name=options["name"]),
            "",
            "Feedback from the hosts on short {}:".format(options["number"]),
            options["feedback"],
        ]
    lines = ["/{} {}".format(CLAUDE_SKILLS[action][1], slug), "", NON_INTERACTIVE]
    return "\n".join(lines + answers) + "\n"


def claude_argv(command, status):
    # The transcripts sit beside the media, outside this repo.
    folders = sorted({os.path.dirname(clip["path"]) for clip in status["clips"] if clip["path"]})
    argv = [command, "-p", "--output-format", "stream-json", "--verbose",
            "--permission-mode", "acceptEdits"]
    if folders:
        argv += ["--add-dir"] + folders
    return argv + ["--allowedTools"] + CLAUDE_ALLOWED_TOOLS


TOOL_INPUT_KEYS = ("file_path", "path", "pattern", "query", "url", "skill", "description", "command")


def _tool_line(block):
    tool_input = block.get("input") or {}
    detail = next((str(tool_input[k]) for k in TOOL_INPUT_KEYS if tool_input.get(k)), "")
    detail = " ".join(detail.split())
    if len(detail) > 160:
        detail = detail[:157] + "..."
    return "  > {} {}".format(block.get("name", "tool"), detail).rstrip()


def _result_text(content):
    if isinstance(content, list):
        content = " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return " ".join(str(content or "").split())


def translate_claude(line):
    """One line of `claude -p --output-format stream-json` -> lines for the log."""
    try:
        event = json.loads(line)
    except ValueError:
        return [line]
    if not isinstance(event, dict):
        return [line]

    kind = event.get("type")
    out = []
    if kind == "assistant":
        for block in (event.get("message") or {}).get("content") or []:
            if block.get("type") == "text" and block.get("text", "").strip():
                out += [""] + block["text"].strip().splitlines()
            elif block.get("type") == "tool_use":
                out.append(_tool_line(block))
    elif kind == "user":
        content = (event.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                out.append("    ! {}".format(_result_text(block.get("content"))[:300]))
    elif kind == "result":
        denials = event.get("permission_denials") or []
        if denials:
            out += ["", "Tool calls refused for want of permission (see CLAUDE_ALLOWED_TOOLS "
                        "in ui/app.py):"]
            out += [_tool_line({"name": d.get("tool_name"), "input": d.get("tool_input")})
                    for d in denials]
        seconds = (event.get("duration_ms") or 0) / 1000.0
        summary = "{} in {:d}m {:02d}s".format(
            "Failed" if event.get("is_error") else "Finished", int(seconds // 60), int(seconds % 60))
        if event.get("total_cost_usd") is not None:
            summary += ", ${:.2f}".format(event["total_cost_usd"])
        out += ["", summary + "."]
    return out


# --- what the page can call ---------------------------------------------------


def reports_errors(method):
    """Turn a problem the user can fix into {"error": ...} for the page to show."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except (BuildError, OSError, ValueError, RuntimeError) as error:
            return {"error": str(error)}
    return wrapper


class Api:
    def __init__(self):
        self._jobs = JobRunner()
        self._media = MediaServer(_short_file)
        self._window = None
        self._quitting = False

    # -- projects --

    @reports_errors
    def list_projects(self):
        return {"projects": projects.list_projects()}

    @reports_errors
    def project(self, slug):
        status = projects.project_status(slug)
        status["blocked"] = projects.blockers(status, claude_command() is not None)
        return status

    @reports_errors
    def cuts(self, slug, which="final"):
        return projects.cuts_view(slug, which)

    @reports_errors
    def check(self, slug, which="final"):
        return projects.check_view(slug, which)

    @reports_errors
    def sheet(self, slug, kind):
        return projects.sheet_html(slug, kind)

    @reports_errors
    def shorts(self, slug):
        view = projects.shorts_view(slug)
        view["media_url"] = "{}/{}".format(self._media.base_url, slug)
        return view

    @reports_errors
    def set_shorts_options(self, slug, crop_percent, nudge_seconds):
        try:
            crop = float(crop_percent) / 100.0
            nudge = float(nudge_seconds or 0)
        except (TypeError, ValueError):
            raise ValueError("The hosts crop and the film nudge must be numbers.")
        if not 0.0 <= crop <= 1.0:
            raise ValueError("The hosts crop is a percentage, 0 (left) to 100 (right).")
        media = projects.read_media(slug)
        media["shorts_hosts_crop_x"] = crop
        media["shorts_sync_nudge_seconds"] = nudge
        projects.write_media(slug, media)
        return {}

    # -- the shorts editor --

    @reports_errors
    def short_editor(self, slug, number):
        view = shorts_edit.editor_view(slug, int(number))
        base = "{}/{}/0".format(self._media.base_url, slug)
        view["proxy_urls"] = {"us": base + "/proxy-hosts", "film": base + "/proxy-film"}
        view["bleep"]["sound_url"] = base + "/bleep-sound" if view["bleep"]["sound"] else None
        view["locked"] = self._shorts_locked(slug)
        return view

    @reports_errors
    def short_peaks(self, slug, who, start, end):
        return shorts_edit.peaks(slug, who, float(start), float(end))

    @reports_errors
    def short_words(self, slug, start, end):
        return shorts_edit.words(slug, float(start), float(end))

    @reports_errors
    def short_draft_state(self, slug, number, short):
        return shorts_edit.draft_state(slug, int(number), short)

    @reports_errors
    def short_find_swears(self, slug, number, short):
        return shorts_edit.find_swears(slug, int(number), short)

    @reports_errors
    def save_short(self, slug, number, short, version, render=False):
        locked = self._shorts_locked(slug)
        if locked:
            raise RuntimeError(locked)
        version = shorts_edit.save_short(slug, int(number), short, version)
        if render:
            self.start(slug, "render_shorts", {"number": int(number)})
        return {"version": version}

    def _shorts_locked(self, slug):
        """Why the shorts file can't be saved right now, or None."""
        info = self._jobs.poll(10 ** 9).get("job") if self._jobs.running() else None
        if info and info.get("slug") == slug and info.get("action") in SHORTS_WRITERS:
            return "{} is rewriting the shorts file; save once it's finished.".format(info.get("label"))
        return None

    @reports_errors
    def open_shorts_folder(self, slug):
        folder = projects.shorts_view(slug).get("out_dir")
        if not folder or not os.path.isdir(folder):
            raise ValueError("Nothing has been rendered yet.")
        os.startfile(folder)
        return {}

    @reports_errors
    def pick_file(self):
        dialog = getattr(webview, "FileDialog", None)
        picked = self._window.create_file_dialog(
            dialog.OPEN if dialog else webview.OPEN_DIALOG,
            allow_multiple=False, file_types=MEDIA_FILE_TYPES)
        return {"path": picked[0] if picked else None}

    @reports_errors
    def create_project(self, title, reaction_media, movie_media, offset=None, overwrite=False):
        title = (title or "").strip()
        slug = slugify(title)
        if not slug:
            raise ValueError("The movie name has no usable characters for a filename.")
        reaction_media, movie_media = clean_path(reaction_media or ""), clean_path(movie_media or "")
        if not reaction_media or not movie_media:
            raise ValueError("Both the reaction recording and the movie file are needed.")
        if os.path.exists(project_path(slug)) and not overwrite:
            return {"exists": True, "slug": slug}
        write_project(title, reaction_media, movie_media, _offset_value(offset))
        return {"slug": slug}

    @reports_errors
    def set_offset(self, slug, offset):
        value = _offset_value(offset)
        if value is None:
            raise ValueError("Enter the offset in seconds.")
        media = projects.read_media(slug)
        media["movie_offset_seconds"] = value
        projects.write_media(slug, media)
        return {"offset": value}

    # -- jobs --

    @reports_errors
    def start(self, slug, action, options=None):
        options = options or {}
        if self._jobs.running():
            raise RuntimeError("Another step is still running.")
        status = projects.project_status(slug)
        command = claude_command()
        reason = projects.blockers(status, command is not None).get(action)
        if reason:
            raise ValueError(reason)

        media_config = _in_repo(project_path(slug))
        cut_list = _in_repo(projects.cut_list_path(slug, "final"))
        title = status["title"]

        shorts_file = _in_repo(projects.shorts_path(slug))
        label = None
        if action == "short_feedback":
            options = self._feedback_options(slug, options)
            label = "Revise short {} - {}".format(options["number"], title)
            shutil.copyfile(projects.shorts_path(slug),
                            projects.cuts_file(slug, ".shorts.prev.json"))

        if action in CLAUDE_SKILLS:
            # The skills read the offset from the media config; an older project
            # may only have it in its cut list.
            media = projects.read_media(slug)
            if media.get("movie_offset_seconds") is None:
                media["movie_offset_seconds"] = status["offset"]
                projects.write_media(slug, media)
            self._jobs.start(
                label or "{} - {}".format(CLAUDE_SKILLS[action][0], title),
                claude_argv(command, status), slug=slug, action=action,
                stdin_text=claude_prompt(action, slug, options), translate=translate_claude)
        elif action in ("render_shorts", "preview_shorts"):
            argv = [sys.executable, "-u", os.path.join("src", "render_shorts.py"),
                    "--cuts", shorts_file]
            what = "Render" if action == "render_shorts" else "Preview"
            if options.get("number"):
                argv += ["--short", str(int(options["number"]))]
                what += " short {}".format(int(options["number"]))
            else:
                what += " shorts"
            if action == "preview_shorts":
                argv.append("--preview")
            self._jobs.start("{} - {}".format(what, title), argv, slug=slug, action=action)
        elif action == "make_proxies":
            self._jobs.start(
                "Make proxies - {}".format(title),
                [sys.executable, "-u", os.path.join("src", "make_proxies.py"), "--project", media_config],
                slug=slug, action=action)
        elif action == "convert":
            argv = [sys.executable, "-u", os.path.join("src", "convert_movie.py"),
                    "--project", media_config]
            if status["has"]["converted"]:
                argv.append("--force")      # "Run again" on a movie that's already converted
            self._jobs.start("Convert movie - {}".format(title), argv, slug=slug, action=action)
        elif action == "transcribe":
            self._jobs.start(
                "Transcribe - {}".format(title),
                [sys.executable, "-u", os.path.join("src", "transcribe.py"),
                 "--project", media_config],
                slug=slug, action=action)
        elif action in ("tighten", "tighten_shorts"):
            shorts = action == "tighten_shorts"
            self._jobs.start(
                "Tighten {}- {}".format("shorts " if shorts else "", title),
                [sys.executable, "-u", os.path.join("src", "tighten_cuts.py"),
                 "--cuts", shorts_file if shorts else cut_list],
                slug=slug, action=action)
        elif action in ("dry_run", "build"):
            argv = [sys.executable, "-u", os.path.join("src", "build_timeline.py"),
                    "--cuts", cut_list]
            if action == "dry_run":
                argv.append("--dry-run")
            self._jobs.start(
                "{} - {}".format("Dry run" if action == "dry_run" else "Build in Resolve", title),
                argv, slug=slug, action=action)
        else:
            raise ValueError("Unknown action {!r}.".format(action))
        return {"started": True}

    def _feedback_options(self, slug, options):
        feedback = " ".join(str(options.get("feedback") or "").split())
        if not feedback:
            raise ValueError("Write the feedback first.")
        number = int(options.get("number") or 0)
        names = {s["number"]: s["name"] for s in projects.shorts_view(slug)["shorts"]}
        if number not in names:
            raise ValueError("There is no short {}.".format(number))
        return {"number": number, "name": names[number], "feedback": feedback[:MAX_FEEDBACK_CHARS]}

    def job_poll(self, since=0, job_id=None):
        return self._jobs.poll(since, job_id)

    def job_cancel(self):
        return {"cancelled": self._jobs.cancel()}

    # -- the window --

    def open_external(self, url):
        if str(url).startswith(("http://", "https://")):
            webbrowser.open(url)
        return {}

    def quit(self):
        """Stop the running job and close. The page calls this after asking."""
        self._quitting = True
        self._jobs.cancel()
        self._window.destroy()
        return {}

    def _on_closing(self):
        if self._quitting or not self._jobs.running():
            return True
        # Returning False keeps the window open. The page asks, on its own
        # thread: this handler holds the UI thread until it returns.
        threading.Thread(
            target=self._window.evaluate_js, args=("window.confirmQuit && confirmQuit()",),
            daemon=True).start()
        return False

    def _on_closed(self):
        self._jobs.cancel()


def _short_file(slug, number, kind):
    """The file the window may fetch: a short's video or preview still, a proxy,
    or the bleep sound."""
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        return None
    if kind == "bleep-sound":
        return render_shorts.load_settings()["bleep"]["sound"] or None
    if kind in ("proxy-hosts", "proxy-film"):
        media = projects.read_media(slug)
        source = media.get("reaction_media" if kind == "proxy-hosts" else "movie_media")
        return proxy_paths(source)[0] if source else None
    extension = {"video": ".mp4", "preview": ".preview.png"}.get(kind)
    if extension is None:
        return None
    base = projects.short_files(slug).get(number)
    return base + extension if base else None


def _in_repo(path):
    """path relative to the repo, where the steps run, when it can be."""
    try:
        return os.path.relpath(path, REPO_ROOT)
    except ValueError:      # on another drive
        return path


def _offset_value(offset):
    if offset is None or str(offset).strip() == "":
        return None
    try:
        value = float(offset)
    except (TypeError, ValueError):
        raise ValueError("The movie offset must be a number of seconds.")
    if value < 0:
        raise ValueError("The movie offset can't be negative.")
    return value


def create_window():
    api = Api()
    window = webview.create_window(
        "TDOS Pipeline", os.path.join(WEB_DIR, "index.html"), js_api=api,
        width=1360, height=880, min_size=(980, 620))
    api._window = window
    window.events.closing += api._on_closing
    window.events.closed += api._on_closed
    return window


def main():
    create_window()
    webview.start()


if __name__ == "__main__":
    main()
