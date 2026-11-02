#!/usr/bin/env python3
"""Terjemahkan chapter EN -> ID memakai Google Translate (endpoint gtx),
lalu rapikan hasilnya:
  - klasifikasi paragraf: percakapan / pikiran / efek suara / narasi
  - normalisasi istilah kultivasi memakai scripts/glossary.json
  - sisipkan penanda catatan pada istilah penting (kemunculan pertama per chapter)
  - terjemahkan judul chapter

Output: data/id/NNN.json
"""
import argparse
import json
import pathlib
import re
import sys
import time
import urllib.parse

from curl_cffi import requests as crq

BASE = pathlib.Path(__file__).resolve().parent.parent
DATA = BASE / "data"
EN_DIR = DATA / "en"
ID_DIR = DATA / "id"
GLOSSARY_PATH = pathlib.Path(__file__).resolve().parent / "glossary.json"

GTX = (
    "https://translate.googleapis.com/translate_a/single"
    "?client=gtx&sl=en&tl=id&dt=t&q="
)
SLEEP_BETWEEN = 0.7  # detik antar request (Google izinkan 5/detik)
MAX_CHARS = 4500     # batas aman per request
PLACEHOLDER = "\x00{}\x00"


def gt(text: str, retries: int = 5) -> str:
    """Terjemahkan satu blok teks. Raise kalau gagal total."""
    url = GTX + urllib.parse.quote(text)
    last = "?"
    for i in range(retries):
        try:
            r = crq.get(url, impersonate="chrome", timeout=40)
            if r.status_code == 200:
                data = r.json()
                out = "".join(seg[0] for seg in data[0])
                if out.strip():
                    return out
                last = "respons kosong"
            else:
                last = f"status={r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"terjemahan gagal: {last}")


def _chunk(lines: list[str]) -> list[str]:
    """Terjemahkan sekelompok baris (dipisah newline). Jika jumlah baris
    hasil tidak cocok, bagi dua lalu coba lagi; terakhir per baris."""
    if len(lines) == 1:
        try:
            return [gt(lines[0])]
        except RuntimeError:
            return [lines[0]]  # biarkan Inggris daripada gagal total
    text = "\n".join(lines)
    for attempt in range(3):
        try:
            parts = gt(text).split("\n")
            if len(parts) == len(lines):
                return parts
        except RuntimeError:
            pass
        time.sleep(1.5 * (attempt + 1))
    mid = len(lines) // 2
    return _chunk(lines[:mid]) + _chunk(lines[mid:])


def translate_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        chunk: list[str] = []
        size = 0
        while i < len(lines) and size + len(lines[i]) + 1 <= MAX_CHARS:
            chunk.append(lines[i])
            size += len(lines[i]) + 1
            i += 1
        if not chunk:  # satu baris melebihi batas -> potong paksa
            chunk = [lines[i][:MAX_CHARS]]
            lines[i] = lines[i][MAX_CHARS:]
            if not lines[i].strip():
                i += 1
        out.extend(_chunk(chunk))
        time.sleep(SLEEP_BETWEEN)
    return out


def classify(src: str) -> str:
    """Klasifikasi berdasarkan teks ASLI Inggris (lebih andal)."""
    t = src.strip()
    if not t:
        return "n"
    if t[0] in "\"\u201c[" or t.startswith("\\["):
        return "d"  # percakapan
    if t[0] == "'":
        return "t"  # pikiran internal / monolog
    if len(t) <= 55 and not any(c in t for c in "\"'"):
        words = t.split()
        if len(words) <= 7 and (t.endswith("!") or t.endswith("...")):
            return "s"  # efek suara
    return "n"


def translate_title(en: str) -> str:
    try:
        t = gt(en)
    except RuntimeError:
        t = en
    t = re.sub(r"^Chapter\s*(\d)", r"Bab \1", t)  # GT kadang mempertahankan "Chapter"
    t = re.sub(r"^Chapter\b", "Bab", t)
    t = t.replace("Prologue", "Prolog") if t.strip() == "Prologue" else t
    time.sleep(SLEEP_BETWEEN)
    return t.strip()


def apply_glossary(
    paras: list[str], terms: list[dict]
) -> tuple[list[str], list[dict]]:
    """Normalisasi istilah + sisipkan penanda catatan (kemunculan pertama)."""
    texts = list(paras)
    annotations: list[dict] = []

    # urutkan: varian terpanjang dulu supaya tidak ketimpa yang lebih pendek
    ordered = sorted(
        (t for t in terms if t.get("variants")),
        key=lambda t: max(len(v) for v in t["variants"]),
        reverse=True,
    )

    for term in ordered:
        boundary = term.get("boundary", "suffix_ok")
        alts = sorted({re.escape(v) for v in term["variants"]}, key=len, reverse=True)
        body = "|".join(alts)
        if boundary == "strict":
            pattern = re.compile(rf"(?<!\w)(?:{body})(?!\w)", re.IGNORECASE)
        else:  # suffix_ok: boleh diakhiri imbuhan Indonesia (-nya, -ku, ...)
            pattern = re.compile(rf"(?<!\w)(?:{body})", re.IGNORECASE)

        noted = False
        for i, txt in enumerate(texts):
            if not txt:
                continue

            def repl(m: "re.Match[str]") -> str:
                nonlocal noted
                if term.get("annotate") and not noted:
                    # jangan dobelkan penanda: kalau tepat setelah kecocokan ini
                    # sudah ada penanda dari istilah lain (mis. "Pemurnian Qi" lalu
                    # "Qi"), lewati — penanda pertama sudah lebih tepat.
                    if re.match(r"\x00\d+\x00", txt[m.end():]):
                        return term["id"]
                    noted = True
                    idx = len(annotations)
                    annotations.append({"t": term["id"], "n": term["note"]})
                    return term["id"] + PLACEHOLDER.format(idx)
                return term["id"]

            texts[i] = pattern.sub(repl, txt)

    # ubah placeholder menjadi elemen HTML penanda
    out = [
        re.sub(
            r"\x00(\d+)\x00",
            r'<span class="tn" data-i="\1" role="button" tabindex="0">?</span>',
            t,
        )
        for t in texts
    ]
    return out, annotations


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, default=None, help="terjemahkan 1 chapter saja")
    ap.add_argument("--force", action="store_true", help="timpa yang sudah ada")
    args = ap.parse_args()

    ID_DIR.mkdir(parents=True, exist_ok=True)
    glossary = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))["terms"]

    en_files = sorted(EN_DIR.glob("*.json"))
    if not en_files:
        print("Belum ada data/en. Jalankan fetch.py dulu.", file=sys.stderr)
        return 1
    if args.only is not None:
        en_files = [f for f in en_files if int(f.stem) == args.only]
        if not en_files:
            print(f"Chapter {args.only} tidak ada di data/en.", file=sys.stderr)
            return 1

    todo = []
    for f in en_files:
        out = ID_DIR / f.name
        if out.exists() and not args.force:
            continue
        todo.append(f)

    print(f"{len(todo)} chapter perlu diterjemahkan.", flush=True)
    ok = fail = 0
    for idx, f in enumerate(todo, 1):
        n = int(f.stem)
        src = json.loads(f.read_text(encoding="utf-8"))
        lines = src["paragraphs"]
        print(f"[{idx}/{len(todo)}] ch {n:03d} - {len(lines)} paragraf", flush=True)
        try:
            id_lines = translate_lines(lines)
            # pastikan jumlahnya cocok (pengaman)
            if len(id_lines) < len(lines):
                id_lines += [""] * (len(lines) - len(id_lines))
            elif len(id_lines) > len(lines):
                id_lines = id_lines[: len(lines)]

            kinds = [classify(p) for p in lines]
            paras, anns = apply_glossary(id_lines, glossary)
            title_id = translate_title(src["title"])

            payload = {
                "n": n,
                "title_en": src["title"],
                "title_id": title_id,
                "paragraphs": [
                    {"text": t, "kind": k} for t, k in zip(paras, kinds) if t.strip()
                ],
                "annotations": anns,
            }
            (ID_DIR / f.name).write_text(
                json.dumps(payload, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"  GAGAL ch {n:03d}: {e}", flush=True)

    print(f"Selesai. sukses={ok} gagal={fail}", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
