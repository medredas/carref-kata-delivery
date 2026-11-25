# Version audio de la synthèse

`synthese-100M-sales-teams.mp3` : lecture de [`../SYNTHESE.md`](../SYNTHESE.md). Durée 1 h 11, MP3 mono 64 kbit/s, avec des chapitres intégrés (ID3).

| Début | Chapitre |
|---|---|
| 00:00 | Introduction |
| 00:14 | 0. Inventaire de la série |
| 02:19 | 1. Vue d'ensemble |
| 03:38 | 2. Vidéo 1 — Start Here : Sales Strategy |
| 22:07 | 3. Vidéo 2 — Recruiting |
| 33:17 | 4. Vidéo 3 — Training (Bootcamp) |
| 43:29 | 5. Vidéo 4 — Managing (Culture) |
| 64:21 | 6. Bonus : skills IA Call Notes & BANT Coach |
| 66:12 | 7. Vidéo bridge (workshop) |
| 67:32 | 8. Chiffres-clés |
| 69:40 | 9. Plan d'action |

## Comment il a été produit
- **Voix :** voix neuronale Microsoft Edge `fr-FR-VivienneMultilingualNeural`, via [edge-tts](https://github.com/rany2/edge-tts) (gratuit, sans clé API).
- **Pourquoi cette voix :** elle est « multilingue », donc elle prononce correctement les termes anglais (closer, setter, lead, pipeline…).
- **Autres voix françaises disponibles :**
  - `fr-FR-RemyMultilingualNeural` (homme, multilingue) ;
  - `fr-FR-DeniseNeural` (femme) ;
  - `fr-FR-HenriNeural` (homme) ;
  - `fr-FR-EloiseNeural` (femme).
- **Préparation du texte :** `scripts/md2speech.py` convertit le Markdown en texte lisible à l'oral (tableaux en phrases, M$ en « millions de dollars », symboles et abréviations développés), avec un fichier par chapitre.
- **Synthèse :** les chapitres sont découpés en morceaux d'environ 400 mots, générés en parallèle par `scripts/edge_tts_part.sh`, puis concaténés avec ffmpeg et les métadonnées de chapitres.
- **Historique :** une première version, réalisée avec Piper (synthèse locale), a été remplacée par celle-ci, de bien meilleure qualité.

Régénérer avec une autre voix :
```bash
pip install edge-tts
python3 scripts/md2speech.py ../SYNTHESE.md text
edge-tts -v fr-FR-RemyMultilingualNeural -f text/03.txt --write-media chapitre-03.mp3
```
