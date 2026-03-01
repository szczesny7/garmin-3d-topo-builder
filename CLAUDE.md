# china-maps

Automated pipeline to generate Garmin 3D topo maps from OpenStreetMap data and NASA SRTM 30m elevation data, using mkgmap and splitter.

## Structure

```
china-maps/
├── update_map.sh           # Main pipeline script (runs all phases)
├── download_1inch_dem.py   # SRTM DEM tile downloader (uses earthaccess)
├── requirements.txt        # Python deps (earthaccess)
├── .env                    # Earthdata credentials (EARTHDATA_USERNAME/PASSWORD)
├── bin/
│   ├── mkgmap/             # Auto-downloaded mkgmap distribution
│   └── splitter/           # Auto-downloaded splitter distribution
├── data/
│   ├── dem_1inch/          # SRTM 1" .hgt tiles (downloaded once, reused)
│   └── osm/               # yunnan-latest.osm.pbf (refreshed each run)
├── work/                   # Splitter temp output (cleaned each run)
└── output/                 # Final gmapsupp.img + .gmapi
```

## Quick Reference

| Task | Command |
|------|---------|
| Full build | `./update_map.sh` |
| Download DEM only | `.venv/bin/python download_1inch_dem.py` |
| DEM for custom bbox | `.venv/bin/python download_1inch_dem.py --bbox W S E N` |
| Force DEM re-download | `rm data/dem_1inch/*.hgt && ./update_map.sh` |
| Force tool re-download | `rm -rf bin/mkgmap bin/splitter && ./update_map.sh` |

## Pipeline Phases (update_map.sh)

1. **Tooling** — checks for `java`, auto-downloads latest mkgmap + splitter .zip distributions from mkgmap.org.uk into `bin/`
2. **Data** — `wget` Yunnan OSM from Geofabrik (always refreshed); triggers `download_1inch_dem.py` only if no `.hgt` files present (creates venv automatically)
3. **Build** — cleans `work/`, runs splitter (max-nodes=1200000), then mkgmap with 30m DEM and routing enabled
4. **Output** — `gmapsupp.img` for Garmin devices, `.gmapi` for BaseCamp

## Configuration

All configurable values are at the top of `update_map.sh`:
- `OSM_URL` — Geofabrik extract URL (currently Yunnan)
- `JAVA_HEAP` — JVM memory (default 4G)
- `SPLITTER_MAX_NODES` — tile size for splitter (default 1200000)
- `FAMILY_ID`, `SERIES_NAME`, `FAMILY_NAME` — Garmin map metadata

Yunnan bounding box for DEM is set in `download_1inch_dem.py` as `DEFAULT_BBOX = (97, 21, 106, 29)`.

## Prerequisites

- Java 11+ (OpenJDK)
- Python 3
- `wget`, `curl`, `unzip`
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
- **earthaccess search returns neighboring tiles** beyond the exact bbox — this is fine, more DEM coverage is better for mkgmap
