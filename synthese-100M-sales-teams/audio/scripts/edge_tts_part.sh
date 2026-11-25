#!/bin/bash
f="$1"; o="${f%.txt}.mp3"
for i in 1 2 3 4; do
  edge-tts --proxy "$HTTPS_PROXY" -v fr-FR-VivienneMultilingualNeural -f "$f" --write-media "$o" >/dev/null 2>"${f%.txt}.log" && exit 0
  sleep $((i*10))
done
echo "FAIL $f"
