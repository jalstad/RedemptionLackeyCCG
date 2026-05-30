"""Thin localhost HTTP layer. Serves index.html and a small JSON API that
delegates to pipeline. Binds to 127.0.0.1 only. No business logic here."""
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from . import pipeline, version_bump, cropper

_INDEX = Path(__file__).resolve().parent / "index.html"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # quiet

    def _send(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def _read_json(self):
        body = self._read_body()
        return json.loads(body.decode("utf-8")) if body else {}

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, _INDEX.read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        route = urlparse(self.path)
        try:
            # /api/crop carries raw image bytes + query params, not JSON.
            if route.path == "/api/crop":
                q = parse_qs(route.query)
                data = self._read_body()
                try:
                    out = pipeline.crop_and_save(
                        filename=q.get("filename", [""])[0],
                        preset=q.get("preset", [cropper.DEFAULT_PRESET])[0],
                        data=data)
                    self._send(200, {"ok": True, "output_name": out})
                except (cropper.PillowMissing, cropper.CropError) as e:
                    self._send(200, {"ok": False, "error": str(e)})
                return

            payload = self._read_json()
            if self.path == "/api/check_image_names":
                self._send(200, pipeline.check_image_names(
                    names=payload.get("names", []),
                    pasted_text=payload.get("pasted_text", "")))
            elif self.path == "/api/current":
                from . import paths
                info = paths.PLUGININFO.read_text(encoding="utf-8")
                cur = version_bump.read_current_version(info)
                self._send(200, {"version": cur,
                                 "suggested": version_bump.bump(cur, "patch")})
            elif self.path == "/api/preview":
                self._send(200, pipeline.preview(
                    pasted_text=payload.get("pasted_text", ""),
                    version=payload["version"], yymmdd=payload["yymmdd"],
                    message=payload["message"]))
            elif self.path == "/api/apply":
                try:
                    result = pipeline.apply(
                        pasted_text=payload.get("pasted_text", ""),
                        version=payload["version"], yymmdd=payload["yymmdd"],
                        message=payload["message"])
                    self._send(200, {"ok": True, "images": result["images"]})
                except pipeline.ValidationError as e:
                    self._send(400, {"ok": False, "error": str(e)})
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:  # never leak a stack trace to the browser
            self._send(500, {"error": str(e)})


def main(port=8765):
    from . import paths
    if not paths.CARDDATA.exists():
        print("ERROR: RedemptionQuick/sets/carddata.txt not found. "
              "Run this tool from inside the plugin repository.")
        return
    httpd = HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"Redemption Update Tool running at {url}  (Ctrl+C to stop)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    httpd.serve_forever()


if __name__ == "__main__":
    main()
