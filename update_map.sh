#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ─── Configuration ───────────────────────────────────────────────────────────
OSM_URL="https://download.geofabrik.de/asia/china/yunnan-latest.osm.pbf"
OSM_FILE="data/osm/yunnan-latest.osm.pbf"

MKGMAP_URL="https://www.mkgmap.org.uk/download/mkgmap.html"
SPLITTER_URL="https://www.mkgmap.org.uk/download/splitter.html"

JAVA_HEAP="8G"
PARALLEL_JOBS="$(sysctl -n hw.perflevel0.logicalcpu 2>/dev/null || nproc 2>/dev/null || echo 4)"
SPLITTER_MAX_NODES="1200000"
FAMILY_ID="9002"
SERIES_NAME="OSM_Yunnan_1inch"
FAMILY_NAME="OSM_Yunnan_3D"
CONTOUR_STEP="50"
CONTOUR_LINE_CAT="500,250"

# ─── Helper functions ────────────────────────────────────────────────────────
log()   { echo "==> $*"; }
error() { echo "ERROR: $*" >&2; exit 1; }

check_java() {
    if ! command -v java &>/dev/null; then
        error "Java is required but not found. Install a JDK (e.g., openjdk 11+)."
    fi
    log "Java found: $(java -version 2>&1 | head -1)"
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
download_mkgmap
download_splitter

MKGMAP_JAR="bin/mkgmap/mkgmap.jar"
SPLITTER_JAR="bin/splitter/splitter.jar"

[ -f "$MKGMAP_JAR" ]  || error "mkgmap.jar not found"
[ -f "$SPLITTER_JAR" ] || error "splitter.jar not found"

# ─── Phase 2: Data Acquisition ──────────────────────────────────────────────
log "Phase 2: Acquiring data"

# OSM data — always fetch latest
log "Downloading OSM extract: yunnan-latest.osm.pbf"
mkdir -p data/osm
wget -q --show-progress -O "$OSM_FILE" "$OSM_URL"

# Python venv (needed for DEM download and contour generation)
if [ ! -f ".venv/bin/python" ]; then
    log "Creating Python virtual environment"
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi

# DEM data — only if folder is empty
if [ -z "$(ls data/dem_1inch/*.hgt 2>/dev/null)" ]; then
    log "DEM tiles not found — running download_1inch_dem.py"
    .venv/bin/python download_1inch_dem.py
else
    log "DEM tiles already present in data/dem_1inch/ — skipping download"
fi

# ─── Phase 3: Contour Generation ───────────────────────────────────────────
log "Phase 3: Generating contour lines from DEM"
mkdir -p work

CONTOUR_DIR="data/contours"
HGT_DIR="data/dem_1inch"
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
log "Cleaning work/ directory"
rm -rf work/*
mkdir -p work

# Run splitter
log "Running splitter (max-nodes=$SPLITTER_MAX_NODES) ..."
java "-Xmx${JAVA_HEAP}" -jar "$SPLITTER_JAR" \
    --output-dir=work \
    --max-nodes="$SPLITTER_MAX_NODES" \
    --max-threads="$PARALLEL_JOBS" \
    "$OSM_FILE"

# Verify splitter produced template.args
[ -f work/template.args ] || error "Splitter did not produce work/template.args"

# Run mkgmap (into work/mkgmap/, then extract final files to output/)
log "Running mkgmap with 1\" DEM ..."
rm -rf work/mkgmap
mkdir -p work/mkgmap

java "-Xmx${JAVA_HEAP}" -jar "$MKGMAP_JAR" \
    --output-dir=work/mkgmap \
    --max-jobs="$PARALLEL_JOBS" \
    --gmapi \
    --gmapsupp \
    --route \
    --index \
    --dem="data/dem_1inch" \
    --dem-dists=3312,13248,26512,53024 \
    --overview-dem-dist=88360 \
    --family-id="$FAMILY_ID" \
    --series-name="$SERIES_NAME" \
    --family-name="$FAMILY_NAME" \
    --description="Yunnan 30m DEM $(date +%Y-%m-%d)" \
    -c work/template.args \
    "$CONTOUR_DIR"/*.osm.pbf

# Collect final output files
rm -rf output
mkdir -p output
mv work/mkgmap/gmapsupp.img output/
mv "work/mkgmap/${FAMILY_NAME}.gmap" "output/${FAMILY_NAME}.gmapi"

# ─── Phase 5: Done ──────────────────────────────────────────────────────────
log "Build complete!"
echo ""
echo "Output files:"
ls -lh output/gmapsupp.img
ls -dh output/*.gmapi
echo ""
echo "  gmapsupp.img  → Copy to Garmin device SD card under /Garmin/"
echo "  *.gmapi       → Open with Garmin BaseCamp on macOS"
