#!/usr/bin/env python3
"""
Local dashboard server for Natalism Watch.

Serves the dashboard and gives the in-page Refresh button something to call:
  GET  /                -> the dashboard
  GET  /api/data        -> current items from the store (fast, no network)
  POST /api/refresh     -> collect fresh items from the web, then return them

Run it:   python serve.py     (or double-click serve.bat)
It opens http://localhost:8765 in your browser automatically.
"""

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import collect

HOST = "127.0.0.1"
PORT = 8765

# Only one collection may run at a time (Reddit rate-limits; avoids overlap).
_refresh_lock = threading.Lock()


def _payload_json():
    """Open a fresh SQLite connection (per request — safe across threads)
    and return the current dashboard payload as JSON bytes."""
    config = collect.load_config()
    con = collect.init_db()
    try:
        payload = collect.build_payload(con, config)
    finally:
        con.close()
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _refresh_json():
    """Run a live collection, then return the refreshed payload."""
    config = collect.load_config()
    con = collect.init_db()
    try:
        new = collect.run_collection(con, config)
        collect.build_dashboard(con, config)  # keep the static file in sync too
        payload = collect.build_payload(con, config)
        payload["new_this_refresh"] = new
    finally:
        con.close()
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/dashboard.html", "/index.html"):
            try:
                with open(collect.DASHBOARD_PATH, "rb") as f:
                    body = f.read()
            except FileNotFoundError:
                # No dashboard yet — generate one from whatever is in the store.
                config = collect.load_config()
                con = collect.init_db()
                collect.build_dashboard(con, config)
                con.close()
                with open(collect.DASHBOARD_PATH, "rb") as f:
                    body = f.read()
            self._send(200, body, "text/html; charset=utf-8")
        elif self.path == "/api/data":
            self._send(200, _payload_json())
        else:
            self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        if self.path == "/api/refresh":
            if not _refresh_lock.acquire(blocking=False):
                self._send(429, b'{"error":"a refresh is already running"}')
                return
            try:
                body = _refresh_json()
                self._send(200, body)
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}).encode("utf-8"))
            finally:
                _refresh_lock.release()
        else:
            self._send(404, b'{"error":"not found"}')

    def log_message(self, fmt, *args):
        # Quieter console; collect.py already logs the interesting stuff.
        collect.log("http " + (fmt % args))


def main():
    # Make sure a dashboard exists before the browser opens.
    config = collect.load_config()
    con = collect.init_db()
    collect.build_dashboard(con, config)
    con.close()

    url = f"http://{HOST}:{PORT}/"
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    collect.log(f"Serving dashboard at {url}  (Ctrl+C to stop)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        collect.log("server stopped")
        server.server_close()


if __name__ == "__main__":
    main()
