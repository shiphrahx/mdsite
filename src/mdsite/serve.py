"""serve mode: build, start a local HTTP server, watch the source for changes,
and live-reload the browser via Server-Sent Events."""

from __future__ import annotations

import socket
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Empty, Queue

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .build import build

# Browser-side snippet: open an SSE connection and reload on the "reload" event.
LIVE_RELOAD_SNIPPET = """<script>
(function () {
  try {
    var es = new EventSource('/__mdsite_reload');
    es.onmessage = function (e) { if (e.data === 'reload') location.reload(); };
  } catch (err) {}
})();
</script>"""


def _find_free_port(preferred: int) -> int:
    for port in [preferred] + list(range(preferred + 1, preferred + 50)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    # Fall back to an ephemeral port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _ReloadHub:
    """Fan-out reload signals to all connected SSE clients."""

    def __init__(self) -> None:
        self._clients: list[Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> Queue:
        q: Queue = Queue()
        with self._lock:
            self._clients.append(q)
        return q

    def unsubscribe(self, q: Queue) -> None:
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)

    def broadcast(self) -> None:
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            q.put("reload")


def _make_handler(root: Path, hub: _ReloadHub):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, *args):  # quiet
            pass

        def do_GET(self):  # noqa: N802
            if self.path == "/__mdsite_reload":
                self._serve_sse()
                return
            # Clean-URL support: map /foo/ -> /foo/index.html implicitly is
            # already handled by SimpleHTTPRequestHandler for directories.
            super().do_GET()

        def _serve_sse(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = hub.subscribe()
            try:
                # Initial comment to establish the stream.
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    try:
                        msg = q.get(timeout=15)
                        self.wfile.write(f"data: {msg}\n\n".encode())
                        self.wfile.flush()
                    except Empty:
                        # Heartbeat keeps the connection alive.
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                hub.unsubscribe(q)

    return Handler


class _RebuildHandler(FileSystemEventHandler):
    """Debounced rebuild on any source change."""

    def __init__(self, rebuild, ignore_under: Path | None = None,
                 debounce_s: float = 0.15):
        self._rebuild = rebuild
        self._ignore_under = ignore_under.resolve() if ignore_under else None
        self._debounce = debounce_s
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _ignored(self, path: str) -> bool:
        # Drop events inside the output dir, otherwise each rebuild's writes
        # retrigger a rebuild — an infinite loop when out is under src (e.g.
        # `mdsite serve .` with the default ./dist output).
        if self._ignore_under is None:
            return False
        try:
            p = Path(path).resolve()
        except (OSError, ValueError):
            return False
        return p == self._ignore_under or self._ignore_under in p.parents

    def on_any_event(self, event):
        if event.is_directory:
            return
        if self._ignored(getattr(event, "src_path", "")):
            return
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._rebuild)
            self._timer.daemon = True
            self._timer.start()


def serve(src_dir: str, opts: dict | None = None) -> None:
    opts = dict(opts or {})
    # The dev server roots the site at "/", so output URLs must be root-relative
    # regardless of any --base meant for production subfolder hosting. Otherwise
    # /docs/assets/... links 404 against a server rooted at /.
    if opts.get("base", "/") not in ("/", "", None):
        print(f"note: ignoring --base {opts['base']} in serve (dev server roots at /)")
    opts["base"] = "/"
    preferred = opts.pop("port", 3000)
    out = Path(opts.get("out", "./dist")).resolve()
    src = Path(src_dir).resolve()

    hub = _ReloadHub()

    def do_build():
        try:
            build(src_dir, opts, live_reload=LIVE_RELOAD_SNIPPET)
        except Exception as err:  # noqa: BLE001
            print(f"Error rebuilding: {err}")

    do_build()

    port = _find_free_port(preferred)
    handler = _make_handler(out, hub)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    httpd.daemon_threads = True

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    def rebuild_and_reload():
        print("Change detected — rebuilding…")
        do_build()
        hub.broadcast()

    observer = Observer()
    observer.schedule(
        _RebuildHandler(rebuild_and_reload, ignore_under=out), str(src), recursive=True
    )
    observer.start()

    url = f"http://127.0.0.1:{port}/"
    print(f"mdsite serving {url}  (watching {src})")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        observer.stop()
        observer.join(timeout=2)
        httpd.shutdown()
