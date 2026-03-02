# garmin-topo-forge

Automated pipeline to generate Garmin 3D topo maps from OpenStreetMap data and NASA SRTM 30m elevation data, using mkgmap and splitter. Profile-driven architecture supports any region.

## Structure

```
garmin-topo-forge/
├── profiles/               # Region profiles mirroring Geofabrik hierarchy
│   ├── Africa/
│   ├── Antarctica.conf
│   ├── Asia/
│   │   └── China/
│   │       └── Yunnan.conf
│   ├── Australia-Oceania/
│   ├── Central America/
│   ├── Europe/
│   │   └── Germany/
│   │       └── Bayern.conf
│   ├── North America/
│   │   └── United States/
│   │       └── California.conf
│   ├── Russia.conf
│   ├── Russia/
│   └── South America/
├── generate_profiles.py    # Generates all profiles from Geofabrik hierarchy
├── update_map.sh           # Main pipeline script (takes profile as $1)
├── download_1inch_dem.py   # SRTM DEM tile downloader (uses earthaccess)
├── requirements.txt        # Python deps (earthaccess, pyhgtmap)
├── .env                    # Earthdata credentials (EARTHDATA_USERNAME/PASSWORD)
├── bin/
│   ├── mkgmap/             # Auto-downloaded mkgmap distribution
│   └── splitter/           # Auto-downloaded splitter distribution
├── data/
│   └── {REGION_NAME}/      # Per-region data isolation
│       ├── dem_1inch/      # SRTM 1" .hgt tiles (downloaded once, reused)
│       ├── contours/       # Generated contour PBFs (from pyhgtmap, reused)
│       └── osm/            # Region OSM PBF (refreshed each run)
├── work/
│   └── {REGION_NAME}/      # Per-region build temp
└── output/
    └── {REGION_NAME}/      # Per-region final gmapsupp.img + .gmapi
```

## Quick Reference

| Task | Command |
|------|---------|
| Full build | `./update_map.sh profiles/Asia/China/Yunnan.conf` |
| Download DEM only | `.venv/bin/python download_1inch_dem.py --bbox W S E N --output-dir data/Yunnan/dem_1inch` |
| Force DEM re-download | `rm data/Yunnan/dem_1inch/*.hgt && ./update_map.sh profiles/Asia/China/Yunnan.conf` |
| Force contour regeneration | `rm -rf data/Yunnan/contours && ./update_map.sh profiles/Asia/China/Yunnan.conf` |
| Force tool re-download | `rm -rf bin/mkgmap bin/splitter && ./update_map.sh profiles/Asia/China/Yunnan.conf` |
| Regenerate all profiles | `python3 generate_profiles.py` |
| Build with custom contours | `CONTOUR_STEP_OVERRIDE=20 ./update_map.sh profiles/Asia/China/Yunnan.conf` |

## Profile Configuration

Region profiles live in `profiles/` mirroring the Geofabrik hierarchy (e.g., `profiles/Asia/China/Yunnan.conf`) and define:
- `REGION_NAME` — used for directory paths and Garmin map description (required)
- `OSM_URL` — Geofabrik extract URL (required)
- `FAMILY_ID` — Garmin family ID, must be unique per map (required)
- `CONTOUR_STEP` — contour line interval in meters (required)
- `CONTOUR_LINE_CAT` — major,medium contour categorization (required)
- `SERIES_NAME` — Garmin series name (optional, auto-derived from REGION_NAME)
- `FAMILY_NAME` — Garmin family name (optional, auto-derived from REGION_NAME)

BBOX is **not** in the profile — it is extracted dynamically from the OSM PBF header using `osmium fileinfo`.

## Pipeline Phases (update_map.sh)

1. **Tooling** — checks for `java` and `osmium`, auto-downloads latest mkgmap + splitter .zip distributions from mkgmap.org.uk into `bin/`
2. **Data** — downloads OSM extract from Geofabrik (always refreshed); extracts BBOX from PBF header via `osmium fileinfo`; sets up Python venv; triggers `download_1inch_dem.py` with dynamic BBOX only if no `.hgt` files present
3. **Contours** — runs `pyhgtmap` on DEM tiles to generate contour lines as split PBF tiles; cached in `data/{REGION_NAME}/contours/`
4. **Build** — cleans `work/{REGION_NAME}/`, runs splitter (max-nodes=1200000), then mkgmap with 30m DEM, contour lines, and routing enabled
5. **Output** — copies `gmapsupp.img` and `.gmapi` to `output/{REGION_NAME}/`; mkgmap's `.gmap` dir is renamed to `.gmapi` for BaseCamp compatibility

## Configuration (non-profile)

Hardcoded in `update_map.sh` (not region-specific):
- `JAVA_HEAP` — JVM memory (default 8G)
- `SPLITTER_MAX_NODES` — tile size for splitter (default 1200000)
- `PARALLEL_JOBS` — auto-detected from Apple Silicon P-core count

## Prerequisites

- Java 11+ (OpenJDK)
- Python 3
- `wget`, `curl`, `unzip`
- `osmium-tool` (for bounding box extraction from OSM PBF files)
- NASA Earthdata account with credentials in `.env`:
  ```
  EARTHDATA_USERNAME=your_username
  EARTHDATA_PASSWORD=your_password
  ```
  Register at: https://urs.earthdata.nasa.gov/users/new

## Key Decisions

- **mkgmap + splitter must be downloaded as .zip distributions** (not standalone .jar) — they need the `lib/` directory for protobuf and other dependencies
- **earthaccess** library handles NASA Earthdata auth and SRTM tile discovery/download — much simpler than hand-rolling HTTP requests to the NASA data servers
- **DEM tiles are downloaded as .hgt.zip and extracted** — mkgmap needs raw `.hgt` files in the DEM directory
- **OSM data is always re-downloaded** to get the latest edits; DEM tiles are static (SRTM from 2000) and only downloaded once
- **BBOX is extracted from OSM PBF header** using `osmium fileinfo -g header.boxes` — no manual bbox configuration needed
- **earthaccess search returns neighboring tiles** beyond the exact bbox — this is fine, more DEM coverage is better for mkgmap
- **mkgmap `--gmapi` produces a `.gmap` directory**, not `.gmapi` — the script renames it so macOS BaseCamp recognizes it
- **pyhgtmap** generates contour lines from SRTM HGT tiles as an OSM PBF file, which mkgmap renders using its default style rules for `contour=elevation` tags
- **Contour PBFs are cached per region** (not in `work/`) so they survive build workspace cleaning — SRTM data is static, so contours only need regenerating if the DEM tiles or contour settings change
- **Parallelism is auto-detected** from P-core count on Apple Silicon (`hw.perflevel0.logicalcpu`) — used by splitter (`--max-threads`) and mkgmap (`--max-jobs`)
- **pyhgtmap `-j` parallel mode deadlocks** with `--max-nodes-per-tile` — use single-threaded mode instead; contour generation uses `--hgtdir` to point at the DEM directory
- **Contour tiles are split** at 1M nodes per tile (`--max-nodes-per-tile=1000000`) to avoid mkgmap OOM on large single files
- **Data is isolated per region** under `data/{REGION_NAME}/` to prevent pyhgtmap and mkgmap conflicts when building multiple regions
- **Profiles mirror the Geofabrik download hierarchy** (e.g., `profiles/Asia/China/Yunnan.conf`) — generated by `generate_profiles.py` which encodes the full tree
- **FAMILY_ID is deterministic** — derived from continent base offset + alphabetical position by URL slug within the continent
- **Contour settings can be overridden** via `CONTOUR_STEP_OVERRIDE` and `CONTOUR_LINE_CAT_OVERRIDE` environment variables without editing profiles
- **Russia is top-level** in `profiles/Russia/` (matching Geofabrik's URL structure, not nested under Asia or Europe)
- **Georgia collision** is handled by naming the US state "Georgia (US State)" in its profile to avoid `data/` directory conflicts with the European country
