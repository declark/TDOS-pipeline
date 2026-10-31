"""Serve rendered shorts to the app's own window so they can be played in it.

The page is a local file and can't read videos from arbitrary folders, so a
tiny HTTP server on 127.0.0.1 hands them over, with byte ranges so the player
can seek. It serves nothing but the files `resolve` returns, and only under a
random path token made up at start-up.
"""

import os
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONTENT_TYPES = {".mp4": "video/mp4", ".png": "image/png", ".wav": "audio/wav", ".mp3": "audio/mpeg",
                 ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".flac": "audio/flac"}
CHUNK = 256 * 1024


class MediaServer:
    def __init__(self, resolve):
        """`resolve(slug, number, kind)` -> a file path, or None."""
        self.token = secrets.token_urlsafe(16)
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                parts = self.path.split("?")[0].strip("/").split("/")
                path = None
                if len(parts) == 4 and parts[0] == server.token and parts[2].isdigit():
                    try:
                        path = resolve(parts[1], int(parts[2]), parts[3])
                    except Exception:
                        path = None
                if not path or not os.path.isfile(path):
                    self.send_error(404)
                    return

                size = os.path.getsize(path)
                first, last = 0, size - 1
                ranged = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range") or "")
                if ranged and (ranged.group(1) or ranged.group(2)):
                    if ranged.group(1):
                        first = int(ranged.group(1))
                        last = min(int(ranged.group(2)), last) if ranged.group(2) else last
                    else:
                        first = max(size - int(ranged.group(2)), 0)
                    if first > last:
                        self.send_error(416)
                        return
                    self.send_response(206)
                    self.send_header("Content-Range", "bytes {}-{}/{}".format(first, last, size))
                else:
                    self.send_response(200)
                self.send_header("Content-Type", CONTENT_TYPES.get(
                    os.path.splitext(path)[1].lower(), "application/octet-stream"))
                self.send_header("Content-Length", str(last - first + 1))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-store")
                # The page fetch()es the bleep sound from another origin; the token guards it.
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                try:
                    with open(path, "rb") as handle:
                        handle.seek(first)
                        left = last - first + 1
                        while left > 0:
                            data = handle.read(min(CHUNK, left))
                            if not data:
                                break
                            self.wfile.write(data)
                            left -= len(data)
                except (ConnectionError, OSError):
                    pass    # the player dropped the request, as it does when seeking

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.base_url = "http://127.0.0.1:{}/{}".format(self._server.server_address[1], self.token)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
