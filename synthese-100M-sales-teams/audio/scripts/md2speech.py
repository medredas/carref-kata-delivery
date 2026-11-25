"""Convert SYNTHESE.md into speech-friendly French text, one file per chapter.

Usage: python3 md2speech.py SYNTHESE.md OUT_DIR
Writes OUT_DIR/NN.txt and OUT_DIR/chapters.tsv (index<TAB>title).
"""
import os
import re
import sys

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
lines = open(src, encoding="utf-8").read().splitlines()

ABBR = [
    (r"\bRDV\b", "rendez-vous"), (r"\bCA\b", "chiffre d'affaires"),
    (r"\bSDR\b", "S D R"), (r"\bCRM\b", "C R M"), (r"\bVSL\b", "V S L"),
    (r"\bACQ\b", "A C Q"), (r"\bOTE\b", "O T E"), (r"\bKPI\b", "K P I"),
    (r"\bLTV\b", "L T V"), (r"\bLTGP\b", "L T G P"), (r"\bCAC\b", "C A C"),
    (r"\bHVAC\b", "H V A C"), (r"\bPNJ\b", "P N J"), (r"\bMQL\b", "M Q L"),
    (r"\bSQL\b", "S Q L"), (r"\bIA\b", "I A"), (r"\bSMS\b", "S M S"),
    (r"\bCTA\b", "C T A"), (r"\bFAQ\b", "F A Q"), (r"\bBC\b", "B C"),
    (r"\bB2B\b", "B to B"), (r"\bB2C\b", "B to C"), (r"\bUS\b", "États-Unis"),
    (r"Q&A", "questions-réponses"), (r"\bvs\.?\b", "contre"),
    (r"\bex\.", "par exemple"), (r"\bcf\.", "voir"), (r"\betc\.", "et cetera"),
    (r"\bk\$", "mille dollars"), (r"\blb\b", "livres"),
]

def say(t: str) -> str:
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)          # links -> text
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"(?i)acquisition\.com", "acquisition point com", t)
    t = re.sub(r"`?(?<![\w])/[a-z0-9]+(?:-[a-z0-9]+)+`?", "", t)
    t = re.sub(r"`/salesstart`", "", t)
    t = re.sub(r"/(an|mois|jour|semaine|lead|vente|recrue)\b", r" par \1", t)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = t.replace("**", "").replace("__", "")
    t = re.sub(r"(?<!\w)\*(?!\s)([^*]+?)\*(?!\w)", r"\1", t)
    t = t.replace("★", "").replace("<br>", ". ")
    # money
    t = re.sub(r"\$100M", "cent millions de dollars", t)
    t = re.sub(r"(\d)\s*-\s*(\d+)\s*M\$", r"\1 à \2 millions de dollars", t)
    t = re.sub(r"(\d[\d,.]*)\s*M\$", r"\1 millions de dollars", t)
    t = re.sub(r"(\d)\s*-\s*(\d+)\s*k\$", r"\1 à \2 mille dollars", t)
    t = re.sub(r"(\d[\d,.]*)\s*k\$", r"\1 mille dollars", t)
    t = re.sub(r"(\d[\d  ,.]*)\s*\$", r"\1 dollars", t)
    # ratios / one-on-one
    t = re.sub(r"\b1:1\b", "tête-à-tête", t)
    t = re.sub(r"\b(\d+(?:,\d+)?):(\d+)\b", r"\1 pour \2", t)
    # days J1, J-3, J+2
    t = re.sub(r"\bJ\+(\d+)", r"jour plus \1", t)
    t = re.sub(r"\bJ-(\d+)", r"\1 jours avant", t)
    t = re.sub(r"\bJ(\d+)", r"jour \1", t)
    # times & units
    t = re.sub(r"(\d+)\s*h\s*(\d{2})\b", r"\1 heure \2", t)
    t = re.sub(r"(\d+)\s*-\s*(\d+)\s*h\b", r"\1 à \2 heures", t)
    t = re.sub(r"(\d+)\s*h\b", r"\1 heures", t)
    t = re.sub(r"\b1 heures\b", "1 heure", t)
    t = re.sub(r"\b1 millions\b", "1 million", t)
    t = re.sub(r"(\d+)\s*min\b", r"\1 minutes", t)
    t = re.sub(r"(\d+)\s*s\b", r"\1 secondes", t)
    # numeric ranges like 30-40 %
    t = re.sub(r"(\d+)\s*-\s*(\d+)(?=\s*(%|pour|jours|mois|ans|minutes|heures|secondes|deals|sets|appels|fois|$|\s))",
               r"\1 à \2", t)
    t = re.sub(r"\+\s*(\d)", r"plus \1", t)
    t = t.replace("%", " pour cent")
    for a, b in ABBR:
        t = re.sub(a, b, t)
    # symbols
    t = t.replace("→", ", puis ") if t.count("→") > 1 else t.replace("→", ", donc ")
    t = (t.replace("≈", "environ ").replace("≥", "au moins ")
          .replace("≤", "au plus ").replace("×", " fois ").replace("÷", " divisé par ")
          .replace("§", "section ").replace("—", ", ").replace("–", ", ")
          .replace("…", ".").replace("«", "").replace("»", "").replace("\"", ""))
    t = re.sub(r"(?<=\w)/(?=\w)", " ou ", t)
    t = t.replace(" / ", ", ").replace("/", ", ")
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = re.sub(r"([,;:])(?=\S)", r"\1 ", t)
    t = re.sub(r"\.(?=[A-ZÀ-Ý])", ". ", t)
    t = re.sub(r"\(\s+", "(", t); t = re.sub(r"\s+\)", ")", t); t = t.replace("()", "")
    t = re.sub(r"(\d)\. (\d)", r"\1.\2", t)
    t = re.sub(r"(\d), (\d)", r"\1,\2", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    t = re.sub(r"(, ){2,}", ", ", t)
    return t

def end(s: str) -> str:
    s = s.strip().rstrip(",;")
    return s if not s or s[-1] in ".!?:" else s + "."

chapters, cur_title, cur = [], "Introduction", []
table = []

def flush_table():
    global table
    if not table:
        return
    rows = [[say(c) for c in r] for r in table]
    head, body = rows[0], rows[1:]
    if len(body) == 1:                      # one data row: pair header/cell
        for h, c in zip(head, body[0]):
            cur.append(end(f"{h} : {c}"))
    else:
        for r in body:
            cells = [c for c in r if c]
            if not cells:
                continue
            if len(cells) == 1:
                cur.append(end(cells[0]))
            else:
                cur.append(end(cells[0] + " : " + ". ".join(cells[1:])))
    table = []

for raw in lines:
    line = raw.rstrip()
    if line.startswith("|"):
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        table.append(cells)
        continue
    flush_table()
    if not line or line.strip() == "---":
        continue
    if line.startswith("> ") and len(chapters) == 0 and not cur_title.startswith("0"):
        continue                                      # top source blockquote
    if line.startswith("Les anciennes sous-leçons"):
        continue                                      # list of URL slugs: not useful in audio
    if line.startswith("# "):
        cur.append(end(say(line[2:])))
        continue
    m = re.match(r"^## (.*)", line)
    if m:
        chapters.append((cur_title, cur))
        cur_title, cur = say(m.group(1)), []
        cur.append(end(cur_title))
        continue
    m = re.match(r"^#{3,4} (.*)", line)
    if m:
        cur.append(end(say(m.group(1))))
        continue
    line = re.sub(r"^\s*>\s?", "", line)
    line = re.sub(r"^\s*[-*]\s+", "", line)
    line = re.sub(r"^\s*(\d+)\.\s+", r"\1, ", line)
    cur.append(end(say(line)))
flush_table()
chapters.append((cur_title, cur))

with open(os.path.join(out, "chapters.tsv"), "w", encoding="utf-8") as idx:
    for i, (title, paras) in enumerate(chapters):
        text = "\n".join(p for p in paras if p and p != ".")
        if not text.strip():
            continue
        with open(os.path.join(out, f"{i:02d}.txt"), "w", encoding="utf-8") as f:
            f.write(text + "\n")
        idx.write(f"{i:02d}\t{title}\n")
        print(i, title, len(text.split()), "mots")
