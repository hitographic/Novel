#!/usr/bin/env python3
"""Perbaiki terjemahan yang sudah ada (idempoten, aman dijalankan berkali-kali):

1. Hapus penanda istilah ganda (istilah pendek ikut mencocok di dalam istilah
   panjang, mis. "Pemurnian Qi[?][?]" -> "Pemurnian Qi[?]"; penanda pertama
   dipertahankan karena milik istilah yang lebih tepat).
2. Normalisasi terjemahan GT yang meleset (mis. "Pembuluh Darah Naga"
   -> "Urat Naga").
3. Terjemahkan ulang paragraf yang masih berupa bahasa Inggris (akibat
   gagal sementara saat proses batch).

Jalankan SETELAH translate.py selesai:  python3 scripts/repair.py
"""
import glob
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from translate import gt, translate_title, SLEEP_BETWEEN  # noqa: E402
import time  # noqa: E402

BASE = pathlib.Path(__file__).resolve().parent.parent
ID_DIR = BASE / "data" / "id"

# koreksi spesifik hasil terjemahan Google yang meleset
FIXES = [
    (re.compile(r"pembuluh darah naga", re.I), "Urat Naga"),
]

# kata fungsional bahasa Inggris (tidak muncul dalam teks Indonesia)
ENG = set(
    """the and was were with that this from they have been would could their
    there when which what who then than his her them will should about into
    over after before because only also other some more most not but one all
    can very just like said made each such two what when where how why""".split()
)


def looks_english(text: str) -> bool:
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if len(words) < 8:
        return False
    hits = sum(1 for w in words if w in ENG)
    return hits >= 3 and hits / len(words) >= 0.12


SPAN_RE = re.compile(r'<span class="tn" data-i="\d+"[^>]*>\?</span>')
ADJACENT_RE = re.compile(
    r'(</span><span class="tn" data-i="\d+"[^>]*>\?</span>)'
)


def collapse_double_markers(text: str) -> str:
    """Gabungkan penanda berdampingan: pertahankan yang TERAKHIR
    (milik istilah panjang yang diproses lebih dulu = paling tepat)."""
    prev = None
    while prev != text:
        prev = text
        # pola: [penandaA][penandaB] -> buang A (penanda pertama)
        text = re.sub(
            r'<span class="tn" data-i="\d+"[^>]*>\?</span>'
            r'(?=<span class="tn" data-i="\d+"[^>]*>\?</span>)',
            "",
            text,
        )
    return text


def main() -> int:
    files = sorted(glob.glob(str(ID_DIR / "*.json")))
    if not files:
        print("Belum ada data/id.", file=sys.stderr)
        return 1

    n_fix_double = n_fix_term = n_fix_lang = 0
    for f in files:
        p = pathlib.Path(f)
        d = json.loads(p.read_text(encoding="utf-8"))
        changed = False

        for para in d["paragraphs"]:
            t = para["text"]

            # 1) penanda ganda
            new = collapse_double_markers(t)
            if new != t:
                n_fix_double += 1
                t = new
                changed = True

            # 2) koreksi istilah
            for pat, repl in FIXES:
                new = pat.sub(repl, t)
                if new != t:
                    n_fix_term += 1
                    t = new
                    changed = True

            # 3) paragraf masih Inggris -> terjemahkan ulang
            if looks_english(t):
                # buang penanda lama sebelum terjemah ulang
                bare = SPAN_RE.sub("", t)
                try:
                    t2 = gt(bare)
                    time.sleep(SLEEP_BETWEEN)
                    if not looks_english(t2):
                        para["text"] = t2
                        n_fix_lang += 1
                        changed = True
                        continue
                except RuntimeError as e:
                    print(f"  gagal terjemah ulang {p.name}: {e}", file=sys.stderr)
            para["text"] = t

        if changed:
            p.write_text(
                json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8"
            )

    print(
        f"Selesai. penanda ganda diperbaiki={n_fix_double}, "
        f"koreksi istilah={n_fix_term}, paragraf diterjemahkan ulang={n_fix_lang}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
