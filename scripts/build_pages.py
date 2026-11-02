#!/usr/bin/env python3
"""Build situs statis untuk GitHub Pages ke folder ``docs/``.

GitHub Pages hanya menyajikan file statis (tidak ada ``server.py``), jadi
reader dijalankan dari salinan ``web/`` + ``data/`` yang sudah diproses:

  docs/
  ├── index.html, app.js, style.css, cover.jpg   ← dari web/
  └── data/
      ├── toc.json        daftar bab (bentuk sama dgn /api/toc)
      ├── glossary.json   glosarium (bentuk sama dgn /api/glossary)
      ├── id/*.json       terjemahan Indonesia
      └── en/*.json       teks asli Inggris

Jalankan:  python3 scripts/build_pages.py
Kemudian:  commit + push, GitHub Pages (main → /docs) memperbarui situsnya.
"""
import json
import pathlib
import shutil

BASE = pathlib.Path(__file__).resolve().parent.parent
WEB = BASE / "web"
DATA = BASE / "data"
GLOSSARY = BASE / "scripts" / "glossary.json"
OUT = BASE / "docs"


def toc_payload() -> dict:
    toc = json.loads((DATA / "toc.json").read_text(encoding="utf-8"))
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
    # pakai judul terjemahan kalau sudah ada (sama dgn server.py)
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


def glossary_payload() -> dict:
    data = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    terms = [
        {"key": t.get("key"), "id": t.get("id"), "note": t.get("note")}
        for t in data.get("terms", [])
    ]
    return {"terms": terms}


def write_json(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # 1. aset reader (tanpa perubahan)
    for name in ("index.html", "app.js", "style.css", "cover.jpg"):
        shutil.copy2(WEB / name, OUT / name)

    # 2. data chapter apa adanya
    shutil.copytree(DATA / "id", OUT / "data" / "id")
    shutil.copytree(DATA / "en", OUT / "data" / "en")

    # 3. payload yang biasanya dibuat server.py
    write_json(OUT / "data" / "toc.json", toc_payload())
    write_json(OUT / "data" / "glossary.json", glossary_payload())

    n_id = len(list((OUT / "data" / "id").glob("*.json")))
    n_en = len(list((OUT / "data" / "en").glob("*.json")))
    print(f"OK  docs/ dibuat: {n_id} bab (id), {n_en} bab (en)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
