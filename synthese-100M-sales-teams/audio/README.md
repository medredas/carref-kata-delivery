# Version audio de la synthèse

`synthese-100M-sales-teams.mp3` — lecture de [`../SYNTHESE.md`](../SYNTHESE.md), 1 h 14, MP3 mono 48 kbit/s, avec chapitres intégrés (ID3) :

| Début | Chapitre |
|---|---|
| 00:00 | Introduction |
| 00:16 | 0. Inventaire de la série |
| 02:20 | 1. Vue d'ensemble |
| 03:44 | 2. Vidéo 1 — Start Here : Sales Strategy |
| 23:01 | 3. Vidéo 2 — Recruiting |
| 34:42 | 4. Vidéo 3 — Training (Bootcamp) |
| 45:08 | 5. Vidéo 4 — Managing (Culture) |
| 66:58 | 6. Bonus : skills IA Call Notes & BANT Coach |
| 68:57 | 7. Vidéo bridge (workshop) |
| 70:18 | 8. Chiffres-clés |
| 72:31 | 9. Plan d'action |

## Comment il a été produit
- Synthèse vocale : [Piper](https://github.com/rhasspy/piper) (local, open source), voix française `fr_FR-siwis-medium`.
  Whisper sert à la reconnaissance vocale (audio → texte) et ne génère pas de voix ; il a été utilisé ici pour **vérifier** l'audio en le re-transcrivant.
- `scripts/md2speech.py` : convertit le Markdown en texte « lisible à l'oral » (tableaux → phrases, M$ → millions de dollars, symboles, abréviations), un fichier par chapitre.
- `scripts/phon.py` : réécrit phonétiquement les termes anglais (setter → « sètteur », closer → « clôzeur », lead → « lide »…) pour la voix française.

Régénérer :
```bash
pip install piper-tts
python3 scripts/md2speech.py ../SYNTHESE.md text && python3 scripts/phon.py text
for f in text/*.txt; do piper -m fr_FR-siwis-medium.onnx --sentence-silence 0.35 -f "${f%.txt}.wav" < "$f"; done
# puis concaténer les WAV (ffmpeg concat) et encoder en MP3
```
