#!/usr/bin/env python3
"""
reels.py — Voir, découper et transcrire des Reels Instagram pour analyser des vidéos de vente.

Pipeline :
  download    Télécharge des reels (URL) ou importe des fichiers vidéo locaux
  transcribe  Transcription horodatée (Whisper, local, gratuit) -> .srt / .txt / .json
  cut         Découpe en clips (par plans, par phrases, par structure de vente, ou à des temps donnés)
  analyze     Indicateurs "vente" (hook, CTA, prix, urgence, débit, rythme de montage...) + récap CSV
  ai          (optionnel) Analyse détaillée par Claude : hook, structure, CTA, réécritures
  viewer      Génère une page HTML pour regarder chaque reel avec transcription cliquable
  all         Enchaîne tout

Exemple :
  python reels.py all https://www.instagram.com/reel/XXXX/ --cookies-from-browser chrome
  python reels.py all ./mes_videos/*.mp4
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
DEFAULT_WORKDIR = Path("reels_work")

# --------------------------------------------------------------------------------------
# Utilitaires
# --------------------------------------------------------------------------------------


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def need_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        sys.exit("ffmpeg/ffprobe introuvable. Installez-le : https://ffmpeg.org/download.html")


def duration_of(video: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(video)])
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def fmt_ts(t: float, sep: str = ",") -> str:
    """Secondes -> 00:00:00,000 (SRT) ou 00:00:00.000 (VTT)."""
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def short_ts(t: float) -> str:
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:04.1f}"


def parse_time(s: str) -> float:
    """'12', '12.5', '0:12', '1:02.5' -> secondes."""
    parts = [float(p) for p in s.strip().split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def reel_dirs(paths: list[str], workdir: Path) -> list[Path]:
    """Résout les arguments en dossiers de reels déjà présents dans le workdir."""
    if not paths:
        return sorted(d for d in workdir.iterdir() if (d / "video.mp4").exists()) if workdir.exists() else []
    out = []
    for p in paths:
        cand = Path(p)
        if cand.is_dir() and (cand / "video.mp4").exists():
            out.append(cand)
        elif (workdir / p / "video.mp4").exists():
            out.append(workdir / p)
        else:
            print(f"  ! ignoré (pas un reel du workdir) : {p}")
    return out


def load_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------------------
# 1. Téléchargement / import
# --------------------------------------------------------------------------------------


def slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:60] or "reel"


def import_local(src: Path, workdir: Path) -> Path:
    d = workdir / slug(src.stem)
    d.mkdir(parents=True, exist_ok=True)
    dst = d / "video.mp4"
    if src.suffix.lower() == ".mp4":
        shutil.copy2(src, dst)
    else:  # conversion en mp4 pour la lecture navigateur
        run(["ffmpeg", "-y", "-i", str(src), "-c:v", "libx264", "-c:a", "aac", str(dst)])
    meta = d / "meta.json"
    if not meta.exists():
        save_json(meta, {"id": d.name, "source": str(src)})
    return d


def download_urls(urls: list[str], workdir: Path, cookies_from_browser: str | None,
                  cookies: str | None) -> list[Path]:
    try:
        import yt_dlp
    except ImportError:
        sys.exit("yt-dlp manquant : pip install -r requirements.txt")

    opts = {
        "outtmpl": str(workdir / "%(id)s" / "video.%(ext)s"),
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
        "merge_output_format": "mp4",
        "writeinfojson": False,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "ignoreerrors": True,
    }
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    if cookies:
        opts["cookiefile"] = cookies

    dirs = []
    with yt_dlp.YoutubeDL(opts) as ydl:
        for url in urls:
            info = ydl.extract_info(url, download=True)
            if not info:
                print(f"  ! échec : {url} (connexion requise ? essayez --cookies-from-browser chrome)")
                continue
            entries = info.get("entries") or [info]
            for e in entries:
                if not e:
                    continue
                d = workdir / e["id"]
                save_json(d / "meta.json", {
                    "id": e.get("id"),
                    "url": e.get("webpage_url") or url,
                    "auteur": e.get("uploader") or e.get("channel"),
                    "legende": e.get("description"),
                    "date": e.get("upload_date"),
                    "vues": e.get("view_count"),
                    "likes": e.get("like_count"),
                    "commentaires": e.get("comment_count"),
                    "duree": e.get("duration"),
                })
                dirs.append(d)
                print(f"  ✓ {d.name}")
    return dirs


def cmd_download(args) -> list[Path]:
    need_ffmpeg()
    args.workdir.mkdir(parents=True, exist_ok=True)
    urls, dirs = [], []
    for item in args.inputs:
        p = Path(item)
        if item.startswith(("http://", "https://")):
            urls.append(item)
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.suffix.lower() in VIDEO_EXT:
                    dirs.append(import_local(f, args.workdir))
                    print(f"  ✓ importé {f.name}")
        elif p.is_file() and p.suffix.lower() in VIDEO_EXT:
            dirs.append(import_local(p, args.workdir))
            print(f"  ✓ importé {p.name}")
        else:
            print(f"  ! entrée non reconnue : {item}")
    if urls:
        dirs += download_urls(urls, args.workdir, args.cookies_from_browser, args.cookies)
    return dirs


# --------------------------------------------------------------------------------------
# 2. Transcription (faster-whisper, 100 % local)
# --------------------------------------------------------------------------------------

_MODEL_CACHE: dict = {}


def load_audio(video: Path, sr: int = 16000):
    """Audio mono 16 kHz en float32, décodé par ffmpeg (évite les incompatibilités de PyAV)."""
    import numpy as np
    out = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(video),
                          "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True)
    if out.returncode != 0:
        sys.exit(f"ffmpeg n'a pas pu lire l'audio de {video} : {out.stderr.decode(errors='ignore')[:300]}")
    return np.frombuffer(out.stdout, np.int16).astype(np.float32) / 32768.0


def transcribe_one(d: Path, model_name: str, language: str | None, force: bool) -> dict:
    out_json = d / "transcript.json"
    if out_json.exists() and not force:
        return load_json(out_json)
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper manquant : pip install -r requirements.txt")

    if model_name not in _MODEL_CACHE:
        print(f"  … chargement du modèle Whisper '{model_name}' (1er lancement = téléchargement)")
        _MODEL_CACHE[model_name] = WhisperModel(model_name, device="auto", compute_type="int8")
    model = _MODEL_CACHE[model_name]

    segments, info = model.transcribe(
        load_audio(d / "video.mp4"), language=language, word_timestamps=True,
        vad_filter=True, beam_size=5,
    )
    segs = []
    for s in segments:
        segs.append({
            "start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
            "words": [{"start": round(w.start, 2), "end": round(w.end, 2), "word": w.word}
                      for w in (s.words or [])],
        })
    data = {"language": info.language, "duration": duration_of(d / "video.mp4"), "segments": segs}
    write_transcript_files(d, data)
    return data


def write_transcript_files(d: Path, data: dict) -> None:
    save_json(d / "transcript.json", data)
    segs = data["segments"]
    srt = [f"{i}\n{fmt_ts(s['start'])} --> {fmt_ts(s['end'])}\n{s['text']}\n"
           for i, s in enumerate(segs, 1)]
    (d / "transcript.srt").write_text("\n".join(srt), encoding="utf-8")
    vtt = ["WEBVTT\n"] + [f"{fmt_ts(s['start'], '.')} --> {fmt_ts(s['end'], '.')}\n{s['text']}\n"
                         for s in segs]
    (d / "transcript.vtt").write_text("\n".join(vtt), encoding="utf-8")
    txt = [f"[{short_ts(s['start'])}] {s['text']}" for s in segs]
    (d / "transcript.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")


def cmd_transcribe(args) -> None:
    for d in reel_dirs(args.reels, args.workdir):
        data = transcribe_one(d, args.model, None if args.lang == "auto" else args.lang, args.force)
        print(f"  ✓ {d.name} : {len(data['segments'])} phrases ({data['language']})")


# --------------------------------------------------------------------------------------
# 3. Découpage
# --------------------------------------------------------------------------------------


def detect_scenes(video: Path, threshold: float) -> list[float]:
    """Temps (s) des changements de plan détectés par ffmpeg."""
    out = run(["ffmpeg", "-hide_banner", "-i", str(video), "-filter:v",
               f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"])
    return [round(float(t), 2) for t in re.findall(r"pts_time:([0-9.]+)", out.stderr)]


CTA_WORDS = [
    "lien en bio", "lien dans la bio", "en bio", "clique", "cliquez", "commande", "commandez",
    "achète", "achetez", "réserve", "réservez", "inscris", "inscrivez", "abonne", "abonnez",
    "écris-moi", "écrivez-moi", "envoie-moi", "envoyez-moi", "en dm", "en mp", "message privé",
    "commente", "commentez", "code promo", "avec le code", "rendez-vous sur", "rends-toi",
    "rendez-vous en", "profite", "profitez", "télécharge", "téléchargez", "contacte", "contactez",
    "link in bio", "click", "order", "buy", "shop now", "dm me", "comment",
]
URGENCY_WORDS = [
    "aujourd'hui", "maintenant", "dès maintenant", "tout de suite", "derniers", "dernières",
    "dernier jour", "plus que", "limité", "limitée", "stock", "ce soir", "cette semaine",
    "dernière chance", "offre limitée", "fin de l'offre", "vite", "ne rate pas", "ne ratez pas", "exclusif",
    "now", "today", "limited", "last chance",
]
PROOF_WORDS = [
    "clients", "clientes", "avis", "témoignage", "résultat", "résultats", "avant/après",
    "avant après", "déjà", "vendu", "vendus", "étoiles", "recommand", "best-seller", "garanti",
    "satisfait", "remboursé",
]
PRICE_RE = re.compile(
    r"(\d+[.,]?\d*\s?(€|euros?|eur\b|\$|dollars?|%|pour ?cent))|(\bprix\b|\bgratuit\w*|\bpromo\w*|"
    r"\bréduction\w*|\bremise\b|\bsoldes?\b|\boffert\w*|\bfree\b|\boff\b)",
    re.IGNORECASE,
)
YOU_RE = re.compile(r"\b(tu|toi|ton|ta|tes|t'|vous|votre|vos|you|your)\b", re.IGNORECASE)


def find_words(text: str, words: list[str]) -> list[str]:
    low = text.lower()
    return sorted({w for w in words if re.search(r"(?<!\w)" + re.escape(w), low)})


def sales_sections(tr: dict, duration: float) -> list[tuple[str, float, float]]:
    """Découpe heuristique : HOOK / CORPS / OFFRE / CTA à partir de la transcription."""
    segs = tr.get("segments", [])
    if not segs:
        hook_end = min(3.0, duration)
        return [("hook", 0.0, hook_end), ("corps", hook_end, duration)]

    # Hook : jusqu'à la fin de la 1re phrase qui dépasse 2 s ; si elle est trop longue (> 6 s),
    # on coupe à la fin de la phrase précédente, sinon à 3 s. Toujours sur une frontière de phrase.
    ends = [s["end"] for s in segs]
    hook_end = next((e for e in ends if e >= 2.0), ends[-1])
    if hook_end > 6.0:
        hook_end = max((e for e in ends if e <= 6.0), default=3.0)
    hook_end = min(hook_end, duration)

    # CTA : première phrase contenant un mot d'appel à l'action dans les 50 % finaux
    cta_start = None
    for s in segs:
        if s["start"] >= duration * 0.5 and find_words(s["text"], CTA_WORDS):
            cta_start = s["start"]
            break
    # Offre : première phrase après le hook qui parle de prix / promo
    offer_start = None
    for s in segs:
        if s["start"] >= hook_end and PRICE_RE.search(s["text"]) and (cta_start is None or s["start"] < cta_start):
            offer_start = s["start"]
            break

    bounds = [("hook", 0.0)]
    if offer_start is None or offer_start > hook_end + 0.5:
        bounds.append(("corps", hook_end))
    if offer_start is not None:
        bounds.append(("offre", max(offer_start, hook_end)))
    if cta_start is not None and cta_start > bounds[-1][1] + 0.5:
        bounds.append(("cta", cta_start))
    sections = []
    for i, (name, start) in enumerate(bounds):
        end = bounds[i + 1][1] if i + 1 < len(bounds) else duration
        if end - start > 0.2:
            sections.append((name, round(start, 2), round(end, 2)))
    return sections


def cut_clip(video: Path, start: float, end: float, out: Path, thumb: Path | None) -> None:
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", str(video),
         "-t", f"{max(end - start, 0.1):.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-c:a", "aac", "-movflags", "+faststart", str(out)])
    if thumb:
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{(start + end) / 2:.3f}",
             "-i", str(video), "-frames:v", "1", "-vf", "scale=320:-2", str(thumb)])


def cut_one(d: Path, mode: str, at: str | None, threshold: float) -> list[dict]:
    video = d / "video.mp4"
    dur = duration_of(video)
    tr = load_json(d / "transcript.json", {"segments": []})

    if mode == "scenes":
        cuts = [t for t in detect_scenes(video, threshold) if 0.3 < t < dur - 0.3]
        pts = [0.0] + cuts + [dur]
        ranges = [(f"plan{i + 1:02d}", a, b) for i, (a, b) in enumerate(zip(pts, pts[1:]))]
    elif mode == "phrases":
        if not tr["segments"]:
            sys.exit(f"{d.name} : pas de transcription, lancez d'abord 'transcribe'.")
        ranges = [(f"phrase{i + 1:02d}", s["start"], s["end"]) for i, s in enumerate(tr["segments"])]
    elif mode == "at":
        if not at:
            sys.exit("--at requis avec --mode at (ex. --at 0:03,0:12,0:25)")
        pts = [0.0] + sorted(parse_time(x) for x in at.split(",")) + [dur]
        ranges = [(f"part{i + 1:02d}", a, b) for i, (a, b) in enumerate(zip(pts, pts[1:])) if b > a]
    else:  # vente
        ranges = sales_sections(tr, dur)

    clips_dir = d / "clips"
    if clips_dir.exists():
        shutil.rmtree(clips_dir)
    clips_dir.mkdir()
    clips = []
    for i, (name, a, b) in enumerate(ranges, 1):
        stem = f"{i:02d}_{name}" if not name[-1].isdigit() else name
        cut_clip(video, a, b, clips_dir / f"{stem}.mp4", clips_dir / f"{stem}.jpg")
        text = " ".join(s["text"] for s in tr["segments"] if s["end"] > a + 0.05 and s["start"] < b - 0.05)
        clips.append({"name": name, "file": f"clips/{stem}.mp4", "thumb": f"clips/{stem}.jpg",
                      "start": round(a, 2), "end": round(b, 2), "text": text})
    save_json(d / "clips.json", {"mode": mode, "clips": clips})
    return clips


def cmd_cut(args) -> None:
    need_ffmpeg()
    for d in reel_dirs(args.reels, args.workdir):
        clips = cut_one(d, args.mode, args.at, args.threshold)
        print(f"  ✓ {d.name} : {len(clips)} clips ({args.mode}) -> {d / 'clips'}")


# --------------------------------------------------------------------------------------
# 4. Analyse "vente"
# --------------------------------------------------------------------------------------


def analyze_one(d: Path, threshold: float) -> dict:
    video = d / "video.mp4"
    dur = duration_of(video)
    tr = load_json(d / "transcript.json", {"segments": []})
    meta = load_json(d / "meta.json", {})
    segs = tr["segments"]
    full = " ".join(s["text"] for s in segs)
    words = re.findall(r"\w+(?:'\w+)?", full)
    speech_time = sum(s["end"] - s["start"] for s in segs)

    scenes = load_json(d / "scenes.json")
    if scenes is None:
        scenes = detect_scenes(video, threshold)
        save_json(d / "scenes.json", scenes)

    hook_segs = [s for s in segs if s["start"] < 3.0]
    hook_text = " ".join(s["text"] for s in hook_segs)
    last_part = " ".join(s["text"] for s in segs if s["start"] >= dur * 0.5)
    cta = find_words(last_part, CTA_WORDS) or find_words(full, CTA_WORDS)
    cta_seg = next((s for s in segs if find_words(s["text"], CTA_WORDS)), None)
    caption = meta.get("legende") or ""

    a = {
        "id": d.name,
        "duree_s": round(dur, 1),
        "nb_mots": len(words),
        "mots_par_minute": round(len(words) / (speech_time / 60)) if speech_time > 1 else 0,
        "part_de_parole_%": round(100 * speech_time / dur) if dur else 0,
        "1er_mot_a_s": round(segs[0]["start"], 2) if segs else None,
        "hook_texte_0_3s": hook_text,
        "hook_question": "?" in hook_text,
        "hook_interpelle_le_client": bool(YOU_RE.search(hook_text)),
        "nb_plans": len(scenes) + 1,
        "duree_moy_plan_s": round(dur / (len(scenes) + 1), 2) if dur else 0,
        "coupe_dans_les_3s": any(t < 3.0 for t in scenes),
        "cta_mots": cta,
        "cta_a_s": cta_seg["start"] if cta_seg else None,
        "cta_dans_legende": find_words(caption, CTA_WORDS),
        "prix_promo": sorted({m.group(0).strip() for m in PRICE_RE.finditer(full)}),
        "urgence": find_words(full, URGENCY_WORDS),
        "preuve_sociale": find_words(full, PROOF_WORDS),
        "tutoiement_vouvoiement_%": round(100 * len(YOU_RE.findall(full)) / len(words), 1) if words else 0,
        "vues": meta.get("vues"),
        "likes": meta.get("likes"),
        "commentaires": meta.get("commentaires"),
    }
    checks = {
        "Parle dans la 1re seconde": a["1er_mot_a_s"] is not None and a["1er_mot_a_s"] <= 1.0,
        "Hook qui interpelle (question / tu-vous)": a["hook_question"] or a["hook_interpelle_le_client"],
        "Montage dynamique (plan moyen ≤ 3 s)": 0 < a["duree_moy_plan_s"] <= 3.0,
        "Appel à l'action oral": bool(cta),
        "Offre / prix explicite": bool(a["prix_promo"]),
        "Urgence ou rareté": bool(a["urgence"]),
        "Preuve sociale": bool(a["preuve_sociale"]),
        "Durée ≤ 45 s": dur <= 45,
    }
    a["checklist"] = checks
    a["score_vente"] = f"{sum(checks.values())}/{len(checks)}"
    save_json(d / "analysis.json", a)
    write_report(d, a, tr, meta)
    return a


def write_report(d: Path, a: dict, tr: dict, meta: dict) -> None:
    L = [f"# Analyse vente — {a['id']}", ""]
    if meta.get("url"):
        L.append(f"Source : {meta['url']}  ")
    stats = [f"{k} : {meta[k]}" for k in ("vues", "likes", "commentaires") if meta.get(k) is not None]
    if stats:
        L.append(" · ".join(stats) + "  ")
    L += [f"**Score vente : {a['score_vente']}** · durée {a['duree_s']} s · {a['nb_plans']} plans "
          f"(moy. {a['duree_moy_plan_s']} s) · {a['mots_par_minute']:.0f} mots/min", "",
          "## Checklist", ""]
    L += [f"- {'✅' if ok else '❌'} {k}" for k, ok in a["checklist"].items()]
    L += ["", "## Hook (0–3 s)", "", f"> {a['hook_texte_0_3s'] or '(aucune parole)'}", "",
          "## Éléments détectés", "",
          f"- Appel à l'action : {', '.join(a['cta_mots']) or '—'}"
          + (f" (à {short_ts(a['cta_a_s'])})" if a["cta_a_s"] is not None else ""),
          f"- CTA dans la légende : {', '.join(a['cta_dans_legende']) or '—'}",
          f"- Prix / promo : {', '.join(a['prix_promo']) or '—'}",
          f"- Urgence : {', '.join(a['urgence']) or '—'}",
          f"- Preuve sociale : {', '.join(a['preuve_sociale']) or '—'}",
          f"- Adresse directe au client (tu/vous) : {a['tutoiement_vouvoiement_%']} % des mots", ""]
    clips = load_json(d / "clips.json")
    if clips:
        L += [f"## Découpage ({clips['mode']})", "", "| Clip | Début | Fin | Texte |", "|---|---|---|---|"]
        L += [f"| [{c['name']}]({c['file']}) | {short_ts(c['start'])} | {short_ts(c['end'])} | "
              f"{c['text'].replace('|', '/')} |" for c in clips["clips"]]
        L.append("")
    L += ["## Transcription", ""]
    L += [f"- `{short_ts(s['start'])}` {s['text']}" for s in tr.get("segments", [])] or ["(vide)"]
    (d / "rapport.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def write_summary(workdir: Path, analyses: list[dict]) -> None:
    if not analyses:
        return
    cols = ["id", "score_vente", "vues", "likes", "commentaires", "duree_s", "nb_plans", "duree_moy_plan_s",
            "mots_par_minute", "1er_mot_a_s", "hook_question", "hook_interpelle_le_client",
            "cta_a_s", "cta_mots", "prix_promo", "urgence", "preuve_sociale", "hook_texte_0_3s"]
    with open(workdir / "recap.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cols)
        for a in analyses:
            w.writerow([", ".join(v) if isinstance(v := a.get(c), list) else ("" if v is None else v)
                        for c in cols])


def cmd_analyze(args) -> None:
    need_ffmpeg()
    analyses = []
    for d in reel_dirs(args.reels, args.workdir):
        a = analyze_one(d, args.threshold)
        analyses.append(a)
        print(f"  ✓ {d.name} : score {a['score_vente']} -> {d / 'rapport.md'}")
    write_summary(args.workdir, analyses)
    if analyses:
        print(f"  ✓ récapitulatif : {args.workdir / 'recap.csv'}")


# --------------------------------------------------------------------------------------
# 5. Analyse IA (optionnelle) avec Claude
# --------------------------------------------------------------------------------------

AI_SYSTEM = """Tu es un expert en marketing vidéo court (Reels, TikTok, Shorts) et en copywriting de vente.
On te donne la transcription horodatée d'un Reel Instagram de vente, sa légende, ses statistiques et des
indicateurs mesurés automatiquement. Rédige en français une analyse actionnable, en Markdown, avec :
1. Résumé en 3 lignes (produit, cible, promesse).
2. Structure détectée (Hook / Problème / Solution / Preuve / Offre / CTA) avec les horodatages.
3. Le hook (0-3 s) : note /10, pourquoi, et 3 hooks alternatifs prêts à tourner.
4. Points forts et points faibles, chacun relié à un moment précis de la vidéo.
5. CTA et offre : clarté, urgence, friction ; propose une meilleure formulation.
6. Objections du client non traitées.
7. Plan de montage conseillé (où couper, raccourcir, ajouter texte à l'écran / sous-titres).
8. Top 3 des changements à fort impact pour la prochaine vidéo.
Sois concret et bref ; cite les phrases exactes de la transcription."""


def ai_one(d: Path, model: str, effort: str) -> Path:
    try:
        import anthropic
    except ImportError:
        sys.exit("SDK anthropic manquant : pip install anthropic")
    tr = load_json(d / "transcript.json", {"segments": []})
    a = load_json(d / "analysis.json") or analyze_one(d, 0.3)
    meta = load_json(d / "meta.json", {})
    transcript = "\n".join(f"[{short_ts(s['start'])}–{short_ts(s['end'])}] {s['text']}" for s in tr["segments"])
    user = (f"## Légende Instagram\n{meta.get('legende') or '(inconnue)'}\n\n"
            f"## Statistiques\nvues={meta.get('vues')} likes={meta.get('likes')} "
            f"commentaires={meta.get('commentaires')}\n\n"
            f"## Indicateurs mesurés\n```json\n{json.dumps(a, ensure_ascii=False, indent=1)}\n```\n\n"
            f"## Transcription horodatée\n{transcript or '(aucune parole détectée)'}")

    try:
        client = anthropic.Anthropic()
    except TypeError:  # aucune clé / profil trouvé
        sys.exit("Aucune clé Claude trouvée : exportez ANTHROPIC_API_KEY=sk-ant-... (console.anthropic.com).")
    try:
        with client.beta.messages.stream(
            model=model,
            max_tokens=64000,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # si le modèle décline, l'API relance sur le modèle de repli recommandé
            system=AI_SYSTEM,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            msg = stream.get_final_message()
    except anthropic.AuthenticationError:
        sys.exit("Clé API invalide ou absente : exportez ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        sys.exit("Limite de débit atteinte, réessayez dans un instant.")
    except anthropic.APIStatusError as e:
        sys.exit(f"Erreur API Claude ({e.status_code}) : {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("Impossible de joindre l'API Claude (réseau).")

    if msg.stop_reason == "refusal":
        text = "_L'analyse IA a été refusée par le modèle pour cette vidéo._"
    else:
        text = "".join(b.text for b in msg.content if b.type == "text")
    out = d / "analyse_ia.md"
    out.write_text(f"# Analyse IA — {d.name}\n\n{text}\n", encoding="utf-8")
    return out


def cmd_ai(args) -> None:
    for d in reel_dirs(args.reels, args.workdir):
        print(f"  ✓ {d.name} -> {ai_one(d, args.ai_model, args.effort)}")


# --------------------------------------------------------------------------------------
# 6. Visionneuse HTML
# --------------------------------------------------------------------------------------

VIEWER_HTML = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analyse des Reels</title>
<style>
:root{--bg:#f6f6f4;--card:#fff;--ink:#1b1b1b;--muted:#6b6b6b;--line:#e3e3df;--accent:#c2410c;--ok:#15803d;--ko:#b91c1c;--hl:#fff1e6}
@media (prefers-color-scheme:dark){:root{--bg:#141414;--card:#1e1e1e;--ink:#eee;--muted:#9a9a9a;--line:#2e2e2e;--accent:#fb923c;--ok:#4ade80;--ko:#f87171;--hl:#3a2416}}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--ink)}
header{padding:16px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center;flex-wrap:wrap}
h1{font-size:18px;margin:0}select{font:inherit;padding:6px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);max-width:100%}
main{display:grid;grid-template-columns:minmax(260px,380px) 1fr;gap:16px;padding:16px;max-width:1300px;margin:auto}
@media (max-width:800px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
video{width:100%;border-radius:10px;background:#000;max-height:70vh}
.tr p{margin:0;padding:6px 8px;border-radius:6px;cursor:pointer}.tr p:hover{background:var(--hl)}
.tr p.on{background:var(--hl);border-left:3px solid var(--accent)}.ts{color:var(--muted);font-variant-numeric:tabular-nums;margin-right:6px}
.clips{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px}
.clip{cursor:pointer;font-size:13px}.clip img{width:100%;border-radius:8px;aspect-ratio:9/16;object-fit:cover;background:#000}
.clip b{display:block;text-transform:uppercase;color:var(--accent);font-size:12px}
.score{font-size:28px;font-weight:700;color:var(--accent)}ul.check{list-style:none;padding:0;margin:8px 0}
.y{color:var(--ok)}.n{color:var(--ko)}.kv{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;font-size:14px}.kv span:nth-child(odd){color:var(--muted)}
h2{font-size:15px;margin:18px 0 8px}.stack>*+*{margin-top:16px}a{color:var(--accent)}
</style></head><body>
<header><h1>Analyse des Reels</h1><select id="pick"></select><span id="nav"></span></header>
<main><div class="stack"><div class="card"><video id="v" controls playsinline></video>
<p style="margin:8px 0 0;color:var(--muted);font-size:13px">Astuce : cliquez une phrase ou un clip pour sauter à ce moment.</p></div>
<div class="card" id="score"></div></div>
<div class="stack"><div class="card"><h2 style="margin-top:0">Découpage</h2><div class="clips" id="clips"></div></div>
<div class="card"><h2 style="margin-top:0">Transcription</h2><div class="tr" id="tr"></div></div></div></main>
<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id), v = $("v");
const fmt = t => { const m = Math.floor(t/60), s = (t%60).toFixed(1).padStart(4,"0"); return m+":"+s; };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let cur = null, endAt = null;
DATA.forEach((r,i) => $("pick").add(new Option(`${r.id}  ·  score ${r.analysis?.score_vente ?? "?"}`, i)));
$("pick").onchange = e => show(+e.target.value);
function seek(t, end){ v.currentTime = t; endAt = end ?? null; v.play(); }
function show(i){
  cur = DATA[i]; v.src = cur.id + "/video.mp4"; endAt = null;
  $("tr").innerHTML = (cur.transcript?.segments ?? []).map((s,k) =>
    `<p data-k="${k}" data-t="${s.start}"><span class="ts">${fmt(s.start)}</span>${esc(s.text)}</p>`).join("") || "<p>(pas de transcription)</p>";
  $("tr").querySelectorAll("p[data-t]").forEach(p => p.onclick = () => seek(+p.dataset.t));
  $("clips").innerHTML = (cur.clips?.clips ?? []).map((c,k) =>
    `<div class="clip" data-k="${k}"><img src="${cur.id}/${c.thumb}" alt=""><b>${esc(c.name)}</b>${fmt(c.start)}–${fmt(c.end)}
     <div style="color:var(--muted)">${esc(c.text).slice(0,90)}</div><a href="${cur.id}/${c.file}" download onclick="event.stopPropagation()">télécharger</a></div>`).join("") || "<p>(pas de clips — lancez <code>cut</code>)</p>";
  $("clips").querySelectorAll(".clip").forEach(el => el.onclick = () => { const c = cur.clips.clips[+el.dataset.k]; seek(c.start, c.end); });
  const a = cur.analysis;
  $("score").innerHTML = !a ? "<p>(pas d'analyse — lancez <code>analyze</code>)</p>" :
    `<div class="score">${a.score_vente}</div><div style="color:var(--muted)">score de la checklist vente</div>
     <ul class="check">${Object.entries(a.checklist).map(([k,ok]) => `<li><span class="${ok?"y":"n"}">${ok?"✔":"✘"}</span> ${esc(k)}</li>`).join("")}</ul>
     <div class="kv"><span>Hook 0–3 s</span><span>${esc(a.hook_texte_0_3s) || "—"}</span>
     <span>Durée</span><span>${a.duree_s} s · ${a.nb_plans} plans</span><span>Débit</span><span>${a.mots_par_minute} mots/min</span>
     <span>CTA</span><span>${esc(a.cta_mots.join(", ")) || "—"}</span><span>Prix/promo</span><span>${esc(a.prix_promo.join(", ")) || "—"}</span>
     <span>Urgence</span><span>${esc(a.urgence.join(", ")) || "—"}</span><span>Preuve</span><span>${esc(a.preuve_sociale.join(", ")) || "—"}</span>
     ${a.vues != null ? `<span>Vues</span><span>${a.vues}</span>` : ""}</div>
     <p style="font-size:13px"><a href="${cur.id}/rapport.md">rapport.md</a> · <a href="${cur.id}/transcript.srt">sous-titres .srt</a>
     ${cur.has_ai ? ` · <a href="${cur.id}/analyse_ia.md">analyse IA</a>` : ""}</p>`;
}
v.ontimeupdate = () => {
  if (endAt != null && v.currentTime >= endAt) { v.pause(); endAt = null; }
  const segs = cur?.transcript?.segments ?? [];
  $("tr").querySelectorAll("p[data-k]").forEach(p => { const s = segs[+p.dataset.k];
    p.classList.toggle("on", v.currentTime >= s.start && v.currentTime < s.end); });
};
if (DATA.length) show(0); else document.querySelector("main").innerHTML = "<p style='padding:16px'>Aucun reel trouvé.</p>";
</script></body></html>
"""


def cmd_viewer(args) -> Path:
    data = []
    for d in reel_dirs([], args.workdir):
        data.append({
            "id": d.name,
            "transcript": load_json(d / "transcript.json"),
            "clips": load_json(d / "clips.json"),
            "analysis": load_json(d / "analysis.json"),
            "has_ai": (d / "analyse_ia.md").exists(),
        })
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    if not data:
        sys.exit(f"Aucun reel dans {args.workdir} — lancez d'abord 'download'.")
    out = args.workdir / "index.html"
    out.write_text(VIEWER_HTML.replace("__DATA__", payload), encoding="utf-8")
    print(f"  ✓ visionneuse : {out.resolve()}  (ouvrez-la dans votre navigateur)")
    return out


# --------------------------------------------------------------------------------------
# 7. Tout enchaîner
# --------------------------------------------------------------------------------------


def cmd_all(args) -> None:
    print("1/5 Téléchargement / import")
    dirs = cmd_download(args)
    if not dirs:
        sys.exit("Aucune vidéo à traiter.")
    args.reels = [str(d) for d in dirs]
    print("2/5 Transcription")
    cmd_transcribe(args)
    print("3/5 Découpage")
    cmd_cut(args)
    print("4/5 Analyse vente")
    cmd_analyze(args)
    if args.ai:
        print("   Analyse IA (Claude)")
        cmd_ai(args)
    print("5/5 Visionneuse")
    cmd_viewer(args)


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-w", "--workdir", type=Path, default=DEFAULT_WORKDIR,
                   help="dossier de travail (défaut : reels_work)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def dl_opts(sp):
        sp.add_argument("inputs", nargs="+", help="URL(s) de reels, fichiers vidéo ou dossiers")
        sp.add_argument("--cookies-from-browser", metavar="NAVIGATEUR",
                        help="réutilise votre session Instagram (chrome, firefox, edge, safari, brave)")
        sp.add_argument("--cookies", metavar="FICHIER", help="fichier cookies.txt (format Netscape)")

    def tr_opts(sp):
        sp.add_argument("--model", default="small",
                        help="modèle Whisper : tiny, base, small, medium, large-v3 (défaut : small)")
        sp.add_argument("--lang", default="fr", help="langue parlée, ou 'auto' (défaut : fr)")
        sp.add_argument("--force", action="store_true", help="refait la transcription")

    def cut_opts(sp):
        sp.add_argument("--mode", choices=["vente", "scenes", "phrases", "at"], default="vente",
                        help="vente = hook/corps/offre/CTA (défaut) ; scenes = par plan ; "
                             "phrases = une phrase par clip ; at = aux temps de --at")
        sp.add_argument("--at", help="temps de coupe pour --mode at, ex. 0:03,0:12.5,25")

    def scene_opt(sp):
        sp.add_argument("--threshold", type=float, default=0.3,
                        help="sensibilité de détection des changements de plan (0.2–0.5, défaut 0.3)")

    def ai_opts(sp, flag: bool):
        if flag:
            sp.add_argument("--ai", action="store_true", help="ajoute l'analyse détaillée par Claude")
        sp.add_argument("--ai-model", default="claude-opus-5-5", help="modèle Claude (défaut : claude-opus-5-5)")
        sp.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])

    sp = sub.add_parser("download", help="télécharger des reels ou importer des vidéos")
    dl_opts(sp)
    sp.set_defaults(func=cmd_download)

    sp = sub.add_parser("transcribe", help="transcrire (Whisper local)")
    sp.add_argument("reels", nargs="*", help="dossiers de reels (défaut : tous)")
    tr_opts(sp)
    sp.set_defaults(func=cmd_transcribe)

    sp = sub.add_parser("cut", help="découper en clips")
    sp.add_argument("reels", nargs="*", help="dossiers de reels (défaut : tous)")
    cut_opts(sp)
    scene_opt(sp)
    sp.set_defaults(func=cmd_cut)

    sp = sub.add_parser("analyze", help="indicateurs de vente + récap CSV")
    sp.add_argument("reels", nargs="*", help="dossiers de reels (défaut : tous)")
    scene_opt(sp)
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("ai", help="analyse détaillée par Claude (ANTHROPIC_API_KEY requis)")
    sp.add_argument("reels", nargs="*", help="dossiers de reels (défaut : tous)")
    ai_opts(sp, flag=False)
    sp.set_defaults(func=cmd_ai)

    sp = sub.add_parser("viewer", help="générer la visionneuse HTML")
    sp.set_defaults(func=cmd_viewer)

    sp = sub.add_parser("all", help="tout enchaîner")
    dl_opts(sp)
    tr_opts(sp)
    cut_opts(sp)
    scene_opt(sp)
    ai_opts(sp, flag=True)
    sp.set_defaults(func=cmd_all)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
