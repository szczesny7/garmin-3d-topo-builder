#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ─── Profile Loading ─────────────────────────────────────────────────────────
PROFILE="${1:-}"
if [ -z "$PROFILE" ] || [ ! -f "$PROFILE" ]; then
    echo "Usage: $0 <profile.conf>"
    echo "  e.g. $0 profiles/Asia/China/Yunnan.conf"
    exit 1
fi

# shellcheck source=/dev/null
source "$PROFILE"

# Allow environment variable overrides for contour settings
[ -n "${CONTOUR_STEP_OVERRIDE:-}" ] && CONTOUR_STEP="$CONTOUR_STEP_OVERRIDE"
[ -n "${CONTOUR_LINE_CAT_OVERRIDE:-}" ] && CONTOUR_LINE_CAT="$CONTOUR_LINE_CAT_OVERRIDE"

# Validate required profile variables
for var in REGION_NAME OSM_URL FAMILY_ID CONTOUR_STEP CONTOUR_LINE_CAT; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: Profile is missing required variable: $var" >&2
        exit 1
    fi
done

# Auto-derive optional Garmin metadata from REGION_NAME if not set in profile
: "${SERIES_NAME:=OSM_${REGION_NAME}_1inch}"
: "${FAMILY_NAME:=OSM_${REGION_NAME}_3D}"

# ─── Derived Paths ───────────────────────────────────────────────────────────
DATA_DIR="data/${REGION_NAME}"
WORK_DIR="work/${REGION_NAME}"
OUT_DIR="output/${REGION_NAME}"
OSM_FILE="${DATA_DIR}/osm/${REGION_NAME}-latest.osm.pbf"

# ─── Configuration ───────────────────────────────────────────────────────────
MKGMAP_URL="https://www.mkgmap.org.uk/download/mkgmap.html"
SPLITTER_URL="https://www.mkgmap.org.uk/download/splitter.html"

JAVA_HEAP="8G"
PARALLEL_JOBS="$(sysctl -n hw.perflevel0.logicalcpu 2>/dev/null || nproc 2>/dev/null || echo 4)"
SPLITTER_MAX_NODES="1200000"

# ─── Helper functions ────────────────────────────────────────────────────────
log()   { echo "==> [$REGION_NAME] $*"; }
error() { echo "ERROR: $*" >&2; exit 1; }

check_java() {
    if ! command -v java &>/dev/null; then
        error "Java is required but not found. Install a JDK (e.g., openjdk 11+)."
    fi
    log "Java found: $(java -version 2>&1 | head -1)"
}

check_osmium() {
    if ! command -v osmium &>/dev/null; then
        error "osmium-tool is required but not found. Install it (e.g., brew install osmium-tool)."
    fi
}

# Extract latest version string (e.g. "r4924") from a mkgmap.org.uk download page
find_latest_version() {
    local page_url="$1"
    local name="$2"
    curl -sL "$page_url" \
        | grep -oE "href=\"[^\"]*${name}-r[0-9]+\.zip\"" \
        | grep -oE 'r[0-9]+' \
        | head -1
}

# Download mkgmap as .zip (needs lib/ dependencies alongside the jar)
download_mkgmap() {
    if [ -d "bin/mkgmap" ] && ls bin/mkgmap/mkgmap.jar &>/dev/null; then
        log "mkgmap already present in bin/mkgmap/"
        return
    fi
    local version
    version=$(find_latest_version "$MKGMAP_URL" "mkgmap")
    [ -n "$version" ] || error "Could not find mkgmap version on $MKGMAP_URL"

    log "Downloading mkgmap-${version}.zip ..."
    local tmp_zip
    tmp_zip=$(mktemp /tmp/mkgmap-XXXXXX.zip)
    curl -L -o "$tmp_zip" "https://www.mkgmap.org.uk/download/mkgmap-${version}.zip"

    local tmp_extract
    tmp_extract=$(mktemp -d /tmp/mkgmap-extract-XXXXXX)
    unzip -q "$tmp_zip" -d "$tmp_extract"
    rm -f "$tmp_zip"

    mkdir -p bin/mkgmap
    mv "$tmp_extract"/mkgmap-*/* bin/mkgmap/
    rm -rf "$tmp_extract"

    [ -f "bin/mkgmap/mkgmap.jar" ] || error "mkgmap.jar not found after extraction"
    log "mkgmap installed to bin/mkgmap/"
}

# Download splitter as .zip (needs lib/ dependencies alongside the jar)
download_splitter() {
    if [ -d "bin/splitter" ] && ls bin/splitter/splitter.jar &>/dev/null; then
        log "splitter already present in bin/splitter/"
        return
    fi
    local version
    version=$(find_latest_version "$SPLITTER_URL" "splitter")
    [ -n "$version" ] || error "Could not find splitter version on $SPLITTER_URL"

    log "Downloading splitter-${version}.zip ..."
    local tmp_zip
    tmp_zip=$(mktemp /tmp/splitter-XXXXXX.zip)
    curl -L -o "$tmp_zip" "https://www.mkgmap.org.uk/download/splitter-${version}.zip"

    local tmp_extract
    tmp_extract=$(mktemp -d /tmp/splitter-extract-XXXXXX)
    unzip -q "$tmp_zip" -d "$tmp_extract"
    rm -f "$tmp_zip"

    mkdir -p bin/splitter
    mv "$tmp_extract"/splitter-*/* bin/splitter/
    rm -rf "$tmp_extract"

    [ -f "bin/splitter/splitter.jar" ] || error "splitter.jar not found after extraction"
    log "splitter installed to bin/splitter/"
}

# ─── Phase 1: Tooling & Setup ───────────────────────────────────────────────
log "Phase 1: Checking tools"
check_java
check_osmium
download_mkgmap
download_splitter

MKGMAP_JAR="bin/mkgmap/mkgmap.jar"
SPLITTER_JAR="bin/splitter/splitter.jar"

[ -f "$MKGMAP_JAR" ]  || error "mkgmap.jar not found"
[ -f "$SPLITTER_JAR" ] || error "splitter.jar not found"

# ─── Phase 2: Data Acquisition ──────────────────────────────────────────────
log "Phase 2: Acquiring data"

# Create region-specific directories
mkdir -p "${DATA_DIR}/osm" "${DATA_DIR}/dem_1inch" "${DATA_DIR}/contours"
mkdir -p "$WORK_DIR"
mkdir -p "$OUT_DIR"

# OSM data — always fetch latest
log "Downloading OSM extract: ${REGION_NAME}-latest.osm.pbf"
wget -q --show-progress -O "$OSM_FILE" "$OSM_URL"

# Extract bounding box from OSM PBF header
log "Extracting bounding box from OSM PBF header..."
BBOX_RAW=$(osmium fileinfo -g header.boxes "$OSM_FILE")
# Strip parentheses and replace commas with spaces to get W S E N
BBOX=$(echo "$BBOX_RAW" | tr -d '()' | tr ',' ' ')
log "Detected BBOX: $BBOX"

# Python venv (needed for DEM download and contour generation)
if [ ! -f ".venv/bin/python" ]; then
    log "Creating Python virtual environment"
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi

# DEM data — only if folder is empty
if [ -z "$(ls "${DATA_DIR}/dem_1inch"/*.hgt 2>/dev/null)" ]; then
    log "DEM tiles not found — running download_1inch_dem.py"
    # shellcheck disable=SC2086
    .venv/bin/python download_1inch_dem.py --bbox $BBOX --output-dir "${DATA_DIR}/dem_1inch"
else
    log "DEM tiles already present in ${DATA_DIR}/dem_1inch/ — skipping download"
fi

# ─── Phase 3: Contour Generation ───────────────────────────────────────────
log "Phase 3: Generating contour lines from DEM"

CONTOUR_DIR="${DATA_DIR}/contours"
HGT_DIR="${DATA_DIR}/dem_1inch"
if [ -z "$(ls "$CONTOUR_DIR"/*.osm.pbf 2>/dev/null)" ]; then
    mkdir -p "$CONTOUR_DIR"
    log "Generating contours ..."
    .venv/bin/pyhgtmap \
        --pbf \
        --step="$CONTOUR_STEP" \
        --line-cat="$CONTOUR_LINE_CAT" \
        --no-zero-contour \
        --void-range-max=-500 \
        --max-nodes-per-tile=1000000 \
        --max-nodes-per-way=0 \
        --simplifyContoursEpsilon=0.00001 \
        --output-prefix="$CONTOUR_DIR"/contours \
        "$HGT_DIR"/*.hgt
    CONTOUR_COUNT=$(ls "$CONTOUR_DIR"/*.osm.pbf 2>/dev/null | wc -l | tr -d ' ')
    [ "$CONTOUR_COUNT" -gt 0 ] || error "pyhgtmap did not produce any contour PBFs"
    log "Contour lines generated: $CONTOUR_COUNT files"
else
    log "Contour PBFs already present in $CONTOUR_DIR/ — skipping generation"
fi

# ─── Phase 4: Build Pipeline ────────────────────────────────────────────────
log "Phase 4: Building map"

# Clean workspace
log "Cleaning ${WORK_DIR}/"
rm -rf "${WORK_DIR:?}"/*
mkdir -p "$WORK_DIR"

# Run splitter
log "Running splitter (max-nodes=$SPLITTER_MAX_NODES) ..."
java "-Xmx${JAVA_HEAP}" -jar "$SPLITTER_JAR" \
    --output-dir="$WORK_DIR" \
    --max-nodes="$SPLITTER_MAX_NODES" \
    --max-threads="$PARALLEL_JOBS" \
    "$OSM_FILE"

# Verify splitter produced template.args
[ -f "${WORK_DIR}/template.args" ] || error "Splitter did not produce ${WORK_DIR}/template.args"

# Run mkgmap (into work subdir, then extract final files to output/)
log "Running mkgmap with 1\" DEM ..."
MKGMAP_WORK="${WORK_DIR}/mkgmap"
rm -rf "$MKGMAP_WORK"
mkdir -p "$MKGMAP_WORK"

java "-Xmx${JAVA_HEAP}" -jar "$MKGMAP_JAR" \
    --output-dir="$MKGMAP_WORK" \
    --max-jobs="$PARALLEL_JOBS" \
    --gmapi \
    --gmapsupp \
    --route \
    --index \
    --dem="$HGT_DIR" \
    --dem-dists=3312,13248,26512,53024 \
    --overview-dem-dist=88360 \
    --family-id="$FAMILY_ID" \
    --series-name="$SERIES_NAME" \
    --family-name="$FAMILY_NAME" \
    --description="${REGION_NAME} 30m DEM $(date +%Y-%m-%d)" \
    -c "${WORK_DIR}/template.args" \
    "$CONTOUR_DIR"/*.osm.pbf

# Collect final output files
rm -rf "${OUT_DIR:?}"/*
mkdir -p "$OUT_DIR"
mv "${MKGMAP_WORK}/gmapsupp.img" "$OUT_DIR/"
mv "${MKGMAP_WORK}/${FAMILY_NAME}.gmap" "${OUT_DIR}/${FAMILY_NAME}.gmapi"

# ─── Phase 5: Done ──────────────────────────────────────────────────────────
log "Build complete!"
echo ""
echo "Output files:"
ls -lh "${OUT_DIR}/gmapsupp.img"
ls -dh "${OUT_DIR}"/*.gmapi
echo ""
echo "  gmapsupp.img  -> Copy to Garmin device SD card under /Garmin/"
echo "  *.gmapi       -> Open with Garmin BaseCamp on macOS"
