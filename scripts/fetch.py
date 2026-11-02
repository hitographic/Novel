#!/usr/bin/env python3
"""Ambil daftar chapter + teks chapter (Prologue + Chapter 1-100) dari Webnovel.

Output:
  data/toc.json      -> daftar chapter terpilih
  data/en/NNN.json   -> teks asli Inggris per chapter (000=Prologue, 001..100)

Pakai curl_cffi (impersonate Chrome) agar lolos Cloudflare.
"""
import json
import pathlib
import re
import sys
import time

from bs4 import BeautifulSoup
from curl_cffi import requests as crq

BASE = pathlib.Path(__file__).resolve().parent.parent
DATA = BASE / "data"
EN_DIR = DATA / "en"
BOOK_ID = "30120306108140505"
BOOK_URL = f"https://www.webnovel.com/book/{BOOK_ID}"
MAX_N = 100  # ambil Chapter 1..100 (+ Prologue sebagai 000)
SLEEP_BETWEEN = 1.2  # detik, sopan ke server
DATE_RE = re.compile(
    r"\d+ (?:years?|months?|weeks?|days?|hours?|mins?|minutes?|seconds?) ago|just now"
)


def http_get(url: str, retries: int = 4) -> str:
    last = None
    for i in range(retries):
        try:
            r = crq.get(url, impersonate="chrome", timeout=40)
            if r.status_code == 200 and len(r.text) > 5000:
                return r.text
            last = f"status={r.status_code} len={len(r.text)}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        wait = 3 * (i + 1)
        print(f"    retry {i + 1}/{retries} ({last}) -> tunggu {wait}s", flush=True)
        time.sleep(wait)
    raise RuntimeError(f"gagal GET {url}: {last}")


def parse_toc() -> list[dict]:
    """Ambil semua link chapter dari halaman buku, lalu pilih Prologue + Ch 1..100."""
    html = http_get(BOOK_URL)
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, str] = {}
    for a in soup.select(f'a[href*="/book/{BOOK_ID}/"]'):
        m = re.search(rf"/book/{BOOK_ID}/(\d+)", a.get("href", ""))
        if not m:
            continue
        txt = a.get_text(strip=True)
        if not txt:
            continue
        found[m.group(1)] = txt

    selected = []
    for cid, txt in found.items():
        # format teks: "101Chapter 100: Lotus (8)1 years ago"
        m = re.match(r"^(\d+)(.*?)(?:%s)?$" % DATE_RE.pattern, txt)
        if not m:
            continue
        title = m.group(2).strip()
        if not title or title.lower() == "not chapter":
            continue
        if title == "Prologue":
            n = 0
        else:
            mc = re.match(r"^Chapter (\d+):", title)
            if not mc:
                continue
            n = int(mc.group(1))
            if n < 1 or n > MAX_N:
                continue
        selected.append({"n": n, "title": title, "chapter_id": cid,
                         "url": f"{BOOK_URL}/{cid}"})

    selected.sort(key=lambda x: x["n"])
    # pastikan unik & lengkap
    seen = set()
    uniq = []
    for c in selected:
        if c["n"] in seen:
            continue
        seen.add(c["n"])
        uniq.append(c)
    return uniq


def extract_paragraphs(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("div.cha-content") or soup.select_one("div.chapter_content")
    if content is None:
        return []
    out = []
    paras = content.select("div.cha-paragraph") or content.select("p")
    for p in paras:
        ps = p.find_all("p")
        nodes = ps if ps else [p]
        t = " ".join(re.sub(r"\s+", " ", x.get_text()).strip() for x in nodes)
        t = t.strip()
        if not t:
            continue
        low = t.lower()
        if "ko-fi.com" in low or "help me financially" in low:
            continue  # promo penulis di tiap chapter
        out.append(t)
    return out


def main() -> int:
    EN_DIR.mkdir(parents=True, exist_ok=True)
    print("Ambil daftar chapter...", flush=True)
    toc = parse_toc()
    print(f"  terpilih {len(toc)} chapter (Prologue + 1..{MAX_N})", flush=True)
    missing = [c["n"] for c in toc if c["n"] not in {0} and c["n"] > MAX_N]
    have = {c["n"] for c in toc}
    want = set(range(0, MAX_N + 1))
    if want - have:
        print(f"  PERINGATAN: tidak ketemu nomor {sorted(want - have)}", flush=True)

    (DATA / "toc.json").write_text(
        json.dumps(toc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    ok = fail = skip = 0
    for i, c in enumerate(toc, 1):
        path = EN_DIR / f"{c['n']:03d}.json"
        if path.exists():
            skip += 1
            continue
        print(f"[{i}/{len(toc)}] ch {c['n']:03d} {c['title']}", flush=True)
        try:
            html = http_get(c["url"])
            paras = extract_paragraphs(html)
            if not paras:
                raise RuntimeError("tidak ada paragraf terekstrak")
            path.write_text(
                json.dumps(
                    {**c, "paragraphs": paras},
                    ensure_ascii=False, indent=2
                ),
                encoding="utf-8",
            )
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"  GAGAL ch {c['n']}: {e}", flush=True)
        time.sleep(SLEEP_BETWEEN)

    print(f"Selesai. ok={ok} gagal={fail} lewat(sudah ada)={skip}", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
