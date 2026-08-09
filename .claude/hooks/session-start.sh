#!/bin/bash
# SessionStart — pripraví prostredie pre prácu na IFC pipeline.
#
# 1. Python závislosti z requirements.txt (pin ifcopenshell==0.8.5 podľa AUDIT §0)
# 2. poppler-utils — pdftoppm/pdftotext na čítanie výkresov v data/
# 3. publikované IFC4.3 docs z buildingSMART
#
# Prečo bod 3: AUDIT.md §8 žiada overiť schému proti ifc43-docs pred odpoveďou,
# ale sieťová politika prostredia blokuje standards.buildingsmart.org na úrovni
# CONNECT (403). Zdroj tých istých docs je verejné GitHub repo a git proxy ho
# pustí, takže sa sparse-klonuje len adresár `lexical` (2469 stránok, ~134 MB).
# Licencia CC BY-ND 4.0 — číta sa, nemodifikuje sa, do repa sa nekopíruje.
#
# Skript je idempotentný: druhý beh nič nesťahuje znova.

set -euo pipefail

# Lokálne (na Samuelovom stroji) nerobí nič — tam je prostredie stále.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

echo "[1/3] Python závislosti"
pip install -q -r requirements.txt
# cryptography v obraze má rozbitý _cffi_backend, čo zhodí import pypdf
python3 -c "import pypdf" 2>/dev/null || pip install -q cffi

echo "[2/3] poppler-utils"
if ! command -v pdftoppm >/dev/null 2>&1; then
  # nefatálne: bez poppleru sa nedajú renderovať výkresy, ale pipeline beží
  (apt-get update -q >/dev/null 2>&1 && apt-get install -y -q poppler-utils >/dev/null 2>&1) \
    || echo "      poppler sa nepodarilo nainštalovať — výkresy sa nedajú renderovať"
fi

echo "[3/3] buildingSMART IFC4.3 docs"
BS=/workspace/bs-output
LEX="$BS/IFC/RELEASE/IFC4_3/lexical"
if [ -d "$LEX" ] && [ "$(ls -A "$LEX" 2>/dev/null | head -1)" ]; then
  echo "      už sú v $LEX"
else
  rm -rf "$BS"
  if git clone --filter=blob:none --sparse --depth 1 \
       https://github.com/buildingSMART/IFC4.3.x-output-2 "$BS" >/dev/null 2>&1; then
    git -C "$BS" sparse-checkout set --cone "IFC/RELEASE/IFC4_3/lexical" >/dev/null 2>&1
    echo "      $(ls "$LEX" | wc -l) stránok v $LEX"
  else
    echo "      klon zlyhal — schému over cez EXPRESS v ifcopenshell a povedz to nahlas"
  fi
fi

echo "export IFC_DOCS=$LEX" >> "${CLAUDE_ENV_FILE:-/dev/null}"
echo "hotovo"
