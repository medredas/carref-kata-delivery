# Reels Analyzer — voir, découper et transcrire vos Reels Instagram de vente

Un seul script Python qui, à partir de vos Reels (lien Instagram ou fichier vidéo) :

1. **télécharge / importe** la vidéo ;
2. **transcrit** la voix avec horodatage (Whisper, en local, gratuit) → `.srt`, `.vtt`, `.txt`, `.json` ;
3. **découpe** la vidéo en clips : *hook / corps / offre / CTA*, ou par plan, par phrase, ou à des temps choisis ;
4. **analyse** les éléments de vente : hook des 3 premières secondes, appel à l'action, prix/promo,
   urgence, preuve sociale, débit de parole, rythme de montage… + un **score /8** et un **récap CSV**
   pour comparer toutes vos vidéos (avec vues/likes quand Instagram les fournit) ;
5. *(optionnel)* demande à **Claude** une critique détaillée : note du hook, 3 hooks alternatifs,
   objections non traitées, meilleure formulation du CTA, plan de montage ;
6. génère une **visionneuse HTML** : vidéo + transcription cliquable (cliquer une phrase saute à ce
   moment) + vignettes des clips + checklist.

## Installation

```bash
# 1. ffmpeg  (macOS : brew install ffmpeg · Windows : winget install ffmpeg · Linux : apt install ffmpeg)
# 2. dépendances Python
cd reels-analyzer
pip install -r requirements.txt
```

## Utilisation rapide

```bash
# Depuis des liens Instagram (réutilise votre session du navigateur où vous êtes connecté)
python reels.py all https://www.instagram.com/reel/AAAA/ https://www.instagram.com/reel/BBBB/ \
    --cookies-from-browser chrome

# Depuis des fichiers déjà sur votre ordinateur (un fichier ou un dossier entier)
python reels.py all ~/Downloads/mes_reels/

# Avec l'analyse IA (clé API : https://console.anthropic.com)
export ANTHROPIC_API_KEY=sk-ant-...
python reels.py all ~/Downloads/mes_reels/ --ai
```

Puis ouvrez `reels_work/index.html` dans votre navigateur.

## Récupérer vos propres Reels

| Méthode | Quand l'utiliser |
|---|---|
| **Lien + `--cookies-from-browser chrome`** (ou `firefox`, `edge`, `safari`, `brave`) | Le plus simple. Soyez connecté à Instagram dans ce navigateur. |
| **Export officiel Instagram** : *Paramètres → Espace Comptes → Vos informations et autorisations → Télécharger vos informations* → choisissez « Contenu » / « Reels », format **JSON**, qualité **haute** | Récupérer **tous** vos reels d'un coup, sans dépendre du site. Décompressez l'archive puis : `python reels.py all chemin/vers/export/media/reels/` |
| **Enregistrer depuis l'app** (bouton … → Télécharger) | Une ou deux vidéos ponctuelles. |

Statistiques (vues, likes, commentaires) : récupérées automatiquement avec la méthode « lien ».
Pour les statistiques complètes (portée, enregistrements, partages), exportez-les depuis
*Tableau de bord professionnel → Statistiques* ou Meta Business Suite et collez-les dans `recap.csv`.

> N'utilisez l'outil que sur vos contenus ou ceux pour lesquels vous avez l'autorisation, et
> respectez les conditions d'utilisation d'Instagram.

## Commandes détaillées

```bash
python reels.py download <liens|fichiers|dossiers> [--cookies-from-browser chrome]
python reels.py transcribe [reel...] [--model small|medium|large-v3] [--lang fr|auto]
python reels.py cut        [reel...] [--mode vente|scenes|phrases|at] [--at 0:03,0:12.5]
python reels.py analyze    [reel...]
python reels.py ai         [reel...] [--effort low|medium|high]
python reels.py viewer
```

Sans nom de reel, chaque commande traite **tous** les reels du dossier de travail
(`reels_work/`, modifiable avec `-w`).

**Modes de découpage :**

- `vente` *(défaut)* : **hook** (premières secondes) · **corps** · **offre** (1re mention de prix/promo) · **CTA** (1er appel à l'action dans la 2e moitié). Les coupes tombent entre deux phrases.
- `scenes` : un clip par plan (détection automatique des changements d'image ; réglez avec `--threshold`).
- `phrases` : un clip par phrase transcrite — idéal pour recombiner ou tester des hooks.
- `at` : coupes manuelles, ex. `--at 0:03,0:12.5,0:25`.

**Qualité de transcription :** `small` est un bon compromis. Pour un accent fort, de la musique ou du
bruit, utilisez `--model medium` ou `--model large-v3` (plus lent ; le premier lancement télécharge le modèle).

## Ce qui est produit

```
reels_work/
├── index.html              ← visionneuse (ouvrir dans le navigateur)
├── recap.csv               ← une ligne par reel, à ouvrir dans Excel / Google Sheets
└── <id_du_reel>/
    ├── video.mp4
    ├── meta.json           ← légende, date, vues, likes, commentaires
    ├── transcript.srt/.vtt/.txt/.json
    ├── clips/              ← 01_hook.mp4, 02_corps.mp4, … + vignettes .jpg
    ├── analysis.json
    ├── rapport.md          ← checklist, hook, CTA, prix, découpage, transcription
    └── analyse_ia.md       ← (option --ai) critique et réécritures par Claude
```

## La checklist « vente » (score /8)

| Critère | Mesuré comment |
|---|---|
| Parle dans la 1re seconde | 1er mot transcrit ≤ 1 s |
| Hook qui interpelle | question, ou « tu / vous » dans les 3 premières secondes |
| Montage dynamique | durée moyenne d'un plan ≤ 3 s |
| Appel à l'action oral | « lien en bio », « clique », « commande », « écris-moi en DM »… |
| Offre / prix explicite | montant en €, %, « promo », « offert », « gratuit »… |
| Urgence ou rareté | « aujourd'hui », « stock limité », « derniers »… |
| Preuve sociale | « clientes », « avis », « résultat », « avant/après »… |
| Durée ≤ 45 s | durée de la vidéo |

Ce sont des repères pour **comparer vos vidéos entre elles** : triez `recap.csv` par vues et regardez
quels critères reviennent sur vos meilleurs reels. Les listes de mots sont en haut de `reels.py`
(`CTA_WORDS`, `URGENCY_WORDS`, `PROOF_WORDS`) : ajoutez les expressions propres à votre activité.

## Analyse IA

`python reels.py ai` envoie à Claude la transcription horodatée, la légende, les statistiques et les
indicateurs mesurés (pas la vidéo). Modèle par défaut : `claude-opus-5-5` (`--ai-model` pour changer).
Si le modèle décline une requête, l'API la relance automatiquement sur un modèle de repli
(paramètre `fallbacks`). Coût indicatif : quelques centimes par reel.
