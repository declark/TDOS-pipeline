"""Run one pipeline step at a time as a subprocess and keep its output.

The page polls poll() for new lines, so nothing here talks to the window.
"""

import os
import subprocess
import sys
import threading

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class JobRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._proc = None
        self._lines = []
        self._info = None       # {"id", "label", "slug", "action"} of the latest job
        self._exit_code = None
        self._cancelled = False
        self._count = 0

    def running(self):
        with self._lock:
            return self._proc is not None

    def start(self, label, argv, slug=None, action=None, stdin_text=None, translate=None):
        """Start `argv`. `translate` maps one raw output line to display lines."""
        with self._lock:
            if self._proc is not None:
                raise RuntimeError("{} is still running.".format(self._info["label"]))

            env = dict(os.environ)
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            # Children (and the python that Claude runs) get this interpreter,
            # the one with faster-whisper installed.
            env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")

            proc = subprocess.Popen(
                argv,
                cwd=REPO_ROOT,
                env=env,
                stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._count += 1
            self._proc = proc
            self._lines = []
            self._exit_code = None
            self._cancelled = False
            self._info = {"id": self._count, "label": label, "slug": slug, "action": action}

        if stdin_text is not None:
            try:
                proc.stdin.write(stdin_text.encode("utf-8"))
                proc.stdin.close()
            except OSError:
                pass
        threading.Thread(target=self._read, args=(proc, translate), daemon=True).start()

    def _read(self, proc, translate):
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            try:
                shown = translate(line) if translate else [line]
            except Exception:
                shown = [line]
            with self._lock:
                self._lines.extend(shown)
        code = proc.wait()
        with self._lock:
            if self._cancelled:
                self._lines.append("")
                self._lines.append("Cancelled.")
            elif code != 0:
                self._lines.append("")
                self._lines.append("Exited with code {}.".format(code))
            self._exit_code = code
            self._proc = None

    def poll(self, since=0, job_id=None):
        """Lines from index `since` on, plus the job's state.

        A `job_id` that isn't the latest job's means the page is behind, so it
        gets the new job's output from the top.
        """
        with self._lock:
            if self._info is None:
                return {"job": None, "running": False, "lines": [], "next": 0}
            if job_id != self._info["id"]:
                since = 0
            return {
                "job": dict(self._info),
                "running": self._proc is not None,
                "cancelled": self._cancelled,
                "exit_code": self._exit_code,
                "lines": self._lines[since:],
                "next": len(self._lines),
            }

    def cancel(self):
        with self._lock:
            proc = self._proc
            if proc is None:
                return False
            self._cancelled = True
        # Kill the whole tree: Claude and the transcriber both start children.
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            proc.kill()
        return True
