#!/usr/bin/env python3
"""
Download 1-arc-second (30m) SRTM DEM tiles from NASA Earthdata using earthaccess.

Authentication (tried in order):
  1. Environment: EARTHDATA_USERNAME + EARTHDATA_PASSWORD (or in .env file)
  2. ~/.netrc: machine urs.earthdata.nasa.gov login <user> password <pass>
  3. Interactive prompt (only works in a terminal)

Register at: https://urs.earthdata.nasa.gov/users/new
"""

import os
import sys
import zipfile
import argparse
from pathlib import Path

import earthaccess

# Yunnan bounding box (default): W, S, E, N
DEFAULT_BBOX = (97, 21, 106, 29)


def main():
    parser = argparse.ArgumentParser(
        description="Download SRTM 1-arc-second DEM tiles for a bounding box."
    )
    parser.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        metavar=("W", "S", "E", "N"),
        default=list(DEFAULT_BBOX),
        help="Bounding box: west south east north (default: Yunnan)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "dem_1inch",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load .env into environment (earthaccess reads EARTHDATA_USERNAME/PASSWORD)
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"'))

    auth = earthaccess.login(persist=True)
    if not auth.authenticated:
        print(
            "ERROR: Earthdata authentication failed.\n"
            "Set EARTHDATA_USERNAME and EARTHDATA_PASSWORD in .env or environment.\n"
            "Register at: https://urs.earthdata.nasa.gov/users/new",
            file=sys.stderr,
        )
        sys.exit(1)

    bbox = tuple(args.bbox)
    print(f"Searching SRTMGL1 tiles for bbox {bbox} ...")

    granules = earthaccess.search_data(
        short_name="SRTMGL1",
        version="003",
        bounding_box=bbox,
    )
    print(f"Found {len(granules)} granules")

    if not granules:
        print("No granules found — check your bounding box.")
        return

    downloaded = earthaccess.download(
        granules,
        local_path=str(args.output_dir),
    )

    # Extract .hgt files from downloaded zips
    hgt_count = 0
    for f in args.output_dir.glob("*.hgt.zip"):
        try:
            with zipfile.ZipFile(f) as zf:
                for name in zf.namelist():
                    if name.endswith(".hgt"):
                        zf.extract(name, path=args.output_dir)
                        hgt_count += 1
            f.unlink()
        except zipfile.BadZipFile:
            print(f"  WARNING: bad zip {f.name}, skipping", file=sys.stderr)

    print(f"\nDone. {hgt_count} .hgt tiles extracted in {args.output_dir}")


if __name__ == "__main__":
    main()
