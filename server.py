#!/usr/bin/env python3
"""Server web reader novel (localhost + jaringan lokal/HP).

Jalankan : python3 server.py [port]      (default 8000)
Buka     : http://localhost:8000         (di komputer ini)
           http://IP-KOMPUTER:8000       (di HP, satu jaringan Wi-Fi)
"""
import json
import pathlib
import socket
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

BASE = pathlib.Path(__file__).resolve().parent
WEB = BASE / "web"
DATA = BASE / "data"
GLOSSARY = BASE / "scripts" / "glossary.json"


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def classify(src: str) -> str:
    t = src.strip()
    if not t:
        return "n"
    if t[0] in "\"\u201c[" or t.startswith("\\["):
        return "d"
    if t[0] == "'":
        return "t"
    if len(t) <= 55 and not any(c in t for c in "\"'"):
        words = t.split()
        if len(words) <= 7 and (t.endswith("!") or t.endswith("...")):
            return "s"
    return "n"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    # --- helper ---------------------------------------------------------
    def _send(self, obj, code: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _toc(self):
        toc_path = DATA / "toc.json"
        if not toc_path.exists():
            return {"chapters": []}
        toc = json.loads(toc_path.read_text(encoding="utf-8"))
        chapters = []
        for c in toc:
            n = c["n"]
            chapters.append(
                {
                    "n": n,
                    "title_id": c["title"],
                    "title_en": c["title"],
                    "has_id": (DATA / "id" / f"{n:03d}.json").exists(),
                    "has_en": (DATA / "en" / f"{n:03d}.json").exists(),
                }
            )
        # pakai judul terjemahan kalau sudah ada
        for ch in chapters:
            p = DATA / "id" / f"{ch['n']:03d}.json"
            if p.exists():
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    ch["title_id"] = d.get("title_id", ch["title_id"])
                    ch["title_en"] = d.get("title_en", ch["title_en"])
                except Exception:  # noqa: BLE001
                    pass
        return {
            "book": {
                "title": "Kisah Sang Regresor tentang Kultivasi",
                "title_en": "A Regressor's Tale of Cultivation",
                "author": "NeverluckySMILE",
            },
            "chapters": chapters,
        }

    def _chapter(self, path: str):
        # /api/ch/123  atau  /api/ch/123?src=en
        parts = path.rstrip("/").split("/")
        try:
            n = int(parts[-1])
        except ValueError:
            self._send({"error": "nomor chapter tidak valid"}, 400)
            return
        src = "en" if "src=en" in self.path else "id"
        f = DATA / src / f"{n:03d}.json"
        if not f.exists():
            self._send({"error": f"chapter {n} ({src}) belum tersedia"}, 404)
            return
        try:
            self._send(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001
            self._send({"error": str(e)}, 500)

    def _glossary(self):
        if not GLOSSARY.exists():
            return {"terms": []}
        data = json.loads(GLOSSARY.read_text(encoding="utf-8"))
        # hanya field aman untuk UI
        terms = [
            {"key": t.get("key"), "id": t.get("id"), "note": t.get("note")}
            for t in data.get("terms", [])
        ]
        return {"terms": terms}

    # --- routing --------------------------------------------------------
    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/toc":
            self._send(self._toc())
        elif path == "/api/glossary":
            self._send(self._glossary())
        elif path.startswith("/api/ch/"):
            self._chapter(path)
        else:
            super().do_GET()

    def log_message(self, fmt, *args):  # senyapkan log biasa
        if args and str(args[1]).startswith("/api/"):
            return
        super().log_message(fmt, *args)


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    ip = lan_ip()
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("=" * 56, flush=True)
    print("  Novel Reader - Kisah Sang Regresor (Terjemahan Indonesia)", flush=True)
    print("=" * 56, flush=True)
    print(f"  Di komputer : http://localhost:{port}", flush=True)
    print(f"  Di HP       : http://{ip}:{port}   (satu Wi-Fi)", flush=True)
    print("=" * 56, flush=True)
    print("  Tekan Ctrl+C untuk berhenti.", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBerhenti.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
