#!/bin/bash
# Fetch the Schultheiß & Lewandowski 2019 mobile+desktop SERP eye-tracking dataset.
# Zenodo record: https://zenodo.org/records/3407551
# Total: ~43 GB across 16 files. Designed to run on the iMac, writing to its local disk.
#
# Usage:
#   ./fetch_schultheiss_lewandowski_2019.sh              # phase 0 only (metadata, ~29 MB)
#   ./fetch_schultheiss_lewandowski_2019.sh --scout      # D1_Students.zip only (~682 MB) + zip-listing
#   ./fetch_schultheiss_lewandowski_2019.sh --phase 1    # mobile raw (~40 GB)
#   ./fetch_schultheiss_lewandowski_2019.sh --phase 2    # desktop raw (~3.2 GB)
#   ./fetch_schultheiss_lewandowski_2019.sh --all        # everything
#   ./fetch_schultheiss_lewandowski_2019.sh --verify     # re-check MD5 of existing files
#   DEST=/path ./fetch_schultheiss_lewandowski_2019.sh   # override destination
#
# Safe to re-run: curl -C - resumes, MD5 re-verified each time.
# bash 3.2 compatible (no associative arrays).

set -u

DEST="${DEST:-$HOME/Downloads/schultheiss-lewandowski-2019}"
BASE="https://zenodo.org/api/records/3407551/files"

# Format: "<size-bytes>|<md5>|<filename>"
# URL is derived by URL-encoding the filename and appending /content.
PHASE_0='
2730344|70c1258508177dd8d5ccb650f3f7001d|AOI metrics.xlsx
50897|57e8dd0db7cf0f0bd2d49e3729faf411|Clicks.zip
26257543|f9d26c1774a11ae5bc16b581c90bd673|SERPs and Image Maps.zip
38632|fb3f7f7dbc54898036cb4b379fa7433c|Questionnaire.zip
17501|1d7fb1dae6bdfc4c5cac21ec50ca3692|Declaration of consent_en.docx
17826|d4371aa3b189b67cc2046649906bc69a|Declaration of consent_ger.docx
16008|c594a0b06a3e8829364938f02259e2fd|Privacy agreement_en.docx
16252|740936eceac8fa96ec2dcc9b881dfeeb|Privacy agreement_ger.docx
'

PHASE_1='
11431864558|65af286cca29de959986545acedaf146|M1_Students.zip
9394105653|ec61891f8688045599d0fad386cb14d6|M1_noStudents.zip
9935018333|bcfdad4ce1410b3831ab9651f89727a8|M2_Students.zip
9032333867|b0f67112d6d00b8b9e2cb496eb38cd15|M2_noStudents.zip
'

PHASE_2='
682124559|0cbcd9b591a9eab16d0ca0f88fc8e415|D1_Students.zip
909348459|d6dc2f5d73d974081e582d8babf5c884|D1_noStudents.zip
775567372|9c51e0afe41d57bc88cc6c5146dc88ed|D2_Students.zip
838564930|a7678d4e522b02e296042f17d314b3bb|D2_noStudents.zip
'

# Smallest single raw zip — use it to scout the per-subject data format
# before committing to the 40 GB mobile pull.
PHASE_SCOUT='
682124559|0cbcd9b591a9eab16d0ca0f88fc8e415|D1_Students.zip
'

# Parse args
PHASES="0"
VERIFY_ONLY=0
SCOUT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --phase)   PHASES="$2"; shift 2;;
    --all)     PHASES="0 1 2"; shift;;
    --scout)   SCOUT=1; PHASES=""; shift;;
    --verify)  VERIFY_ONLY=1; PHASES="0 1 2"; shift;;
    -h|--help) sed -n '2,12p' "$0"; exit 0;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

mkdir -p "$DEST"
cd "$DEST" || exit 1

# URL-encode a filename: spaces -> %20, keep the rest.
# Zenodo only uses %20 for these files; if that changes, switch to python3 urllib.
urlencode() {
  printf '%s' "$1" | sed -e 's/ /%20/g'
}

md5_of() {
  # macOS md5 (binary), fallback to md5sum
  if command -v md5 >/dev/null 2>&1; then
    md5 -q "$1"
  else
    md5sum "$1" | awk '{print $1}'
  fi
}

human_size() {
  awk -v b="$1" 'BEGIN {
    split("B KB MB GB TB", u)
    i=1; while (b>=1024 && i<5) { b/=1024; i++ }
    printf "%.1f %s", b, u[i]
  }'
}

fetch_one() {
  local size="$1" expected_md5="$2" name="$3"
  local url="$BASE/$(urlencode "$name")/content"
  local path="$DEST/$name"

  printf '\n--- %s  (%s) ---\n' "$name" "$(human_size "$size")"

  # Skip if already verified
  if [ -f "$path" ]; then
    local have_size; have_size=$(stat -f%z "$path" 2>/dev/null || stat -c%s "$path")
    if [ "$have_size" = "$size" ]; then
      local have_md5; have_md5=$(md5_of "$path")
      if [ "$have_md5" = "$expected_md5" ]; then
        echo "OK  already verified"
        return 0
      else
        echo "WARN size matches but MD5 differs: got $have_md5 expected $expected_md5"
        echo "     removing and re-downloading"
        rm -f "$path"
      fi
    fi
  fi

  if [ "$VERIFY_ONLY" = "1" ]; then
    echo "SKIP verify-only mode and file missing or incomplete"
    return 0
  fi

  # Resume-capable download with retry
  local attempts=0
  while [ $attempts -lt 5 ]; do
    attempts=$((attempts + 1))
    echo "download attempt $attempts ..."
    if curl -L --fail --retry 5 --retry-delay 10 -C - -o "$path" "$url"; then
      break
    else
      echo "curl failed, sleeping 15s before retry"
      sleep 15
    fi
  done

  # Verify
  local got_size; got_size=$(stat -f%z "$path" 2>/dev/null || stat -c%s "$path")
  if [ "$got_size" != "$size" ]; then
    echo "FAIL size mismatch: got $got_size expected $size"
    return 1
  fi
  local got_md5; got_md5=$(md5_of "$path")
  if [ "$got_md5" != "$expected_md5" ]; then
    echo "FAIL MD5 mismatch: got $got_md5 expected $expected_md5"
    return 1
  fi
  echo "OK  verified"
}

run_phase() {
  local phase_num="$1" list="$2"
  printf '\n============================\nPHASE %s\n============================\n' "$phase_num"
  local failed=0
  local total=0
  echo "$list" | while IFS='|' read -r size md5 name; do
    [ -z "$name" ] && continue
    total=$((total + size))
  done
  echo "$list" | while IFS='|' read -r size md5 name; do
    [ -z "$name" ] && continue
    fetch_one "$size" "$md5" "$name" || failed=$((failed + 1))
  done
}

inspect_phase_0() {
  printf '\n============================\nPHASE 0 INSPECT\n============================\n'
  local unzip_dir="$DEST/unzipped"
  mkdir -p "$unzip_dir"

  for z in "Clicks.zip" "Questionnaire.zip" "SERPs and Image Maps.zip"; do
    local src="$DEST/$z"
    [ -f "$src" ] || { echo "skip (missing): $z"; continue; }
    local out="$unzip_dir/${z%.zip}"
    if [ -d "$out" ] && [ -n "$(ls -A "$out" 2>/dev/null)" ]; then
      echo "already unzipped: $z"
    else
      echo "unzipping: $z"
      mkdir -p "$out"
      unzip -q -o "$src" -d "$out"
    fi
  done

  echo ""
  echo "--- tree (top 2 levels, 40 entries max per dir) ---"
  if command -v tree >/dev/null 2>&1; then
    tree -L 2 --filelimit 40 "$unzip_dir"
  else
    # fallback for iMacs without `tree`
    ( cd "$unzip_dir" && find . -maxdepth 2 | head -200 )
  fi

  echo ""
  echo "--- AOI metrics.xlsx summary ---"
  local xlsx="$DEST/AOI metrics.xlsx"
  if [ -f "$xlsx" ] && command -v python3 >/dev/null 2>&1; then
    python3 - "$xlsx" <<'PY' 2>/dev/null || echo "(openpyxl not installed; skipping xlsx summary — pip3 install openpyxl to enable)"
import sys
try:
    from openpyxl import load_workbook
except ImportError:
    sys.exit(1)
wb = load_workbook(sys.argv[1], read_only=True, data_only=True)
for sheet in wb.sheetnames:
    ws = wb[sheet]
    print(f"  sheet: {sheet!r}  dims={ws.max_row}x{ws.max_column}")
    # Print header row if present
    for row in ws.iter_rows(min_row=1, max_row=1, values_only=True):
        header = [str(c)[:30] if c is not None else "" for c in row]
        print(f"    header: {header[:12]}{' ...' if len(header) > 12 else ''}")
        break
PY
  else
    echo "(no python3 or file missing; skipping)"
  fi

  echo ""
  echo "Unzipped content: $unzip_dir"
}

echo "Destination: $DEST"
echo "Phases:      $PHASES"
[ "$VERIFY_ONLY" = "1" ] && echo "Mode:        VERIFY ONLY (no downloads)"
df -h "$DEST" 2>/dev/null | tail -1

DID_PHASE_0=0
if [ "$SCOUT" = "1" ]; then
  run_phase SCOUT "$PHASE_SCOUT"
  # Peek inside to see the per-subject data format
  printf '\n============================\nSCOUT INSPECT\n============================\n'
  zip_path="$DEST/D1_Students.zip"
  if [ -f "$zip_path" ]; then
    echo "--- zip contents (first 80 entries) ---"
    unzip -l "$zip_path" | head -80
    echo ""
    echo "--- zip summary ---"
    unzip -l "$zip_path" | tail -5
    echo ""
    echo "--- file-type distribution ---"
    unzip -l "$zip_path" | awk 'NR>3 && NF>=4 {n=split($NF,a,"."); ext=(n>1)?a[n]:"(no-ext)"; c[ext]++} END {for (k in c) printf "  %-12s %d\n", k, c[k]}' | sort -k2 -rn | head -20
  else
    echo "scout download failed — $zip_path missing"
  fi
else
  for p in $PHASES; do
    case "$p" in
      0) run_phase 0 "$PHASE_0"; DID_PHASE_0=1;;
      1) run_phase 1 "$PHASE_1";;
      2) run_phase 2 "$PHASE_2";;
      *) echo "bad phase: $p" >&2;;
    esac
  done

  # Auto-inspect after Phase 0 (unless verify-only)
  if [ "$DID_PHASE_0" = "1" ] && [ "$VERIFY_ONLY" != "1" ]; then
    inspect_phase_0
  fi
fi

echo ""
echo "Done. Files in: $DEST"
ls -la "$DEST"
