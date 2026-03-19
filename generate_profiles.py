#!/usr/bin/env python3
"""Generate Garmin topo map profiles from the Geofabrik region index.

Fetches the Geofabrik index-v1-nogeom.json, builds the region hierarchy,
and generates .conf files under profiles/ with stable hash-based FAMILY_IDs.
"""

import hashlib
import json
import os
import shutil
import sys
import urllib.request

GEOFABRIK_INDEX_URL = "https://download.geofabrik.de/index-v1-nogeom.json"
PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
CONTOUR_STEP = "50"
CONTOUR_LINE_CAT = "500,250"

# Continents to skip as profiles (too large to build, only their children matter)
SKIP_CONTINENTS = {"africa", "asia", "australia-oceania", "central-america",
                   "europe", "north-america", "south-america"}

# Slug -> display name overrides for cases where titlecase isn't right.
# Only needed when slug-to-titlecase produces a wrong or ambiguous name.
DISPLAY_NAME_OVERRIDES = {
    # Continents / top-level directory names
    "australia-oceania": "Australia-Oceania",
    "central-america": "Central America",
    "north-america": "North America",
    "south-america": "South America",
    # Ambiguous names
    "us": "United States",
    "us/georgia": "Georgia (US State)",
    # Compound regions where slug loses info
    "haiti-and-domrep": "Haiti and Dominican Republic",
    "guernsey-jersey": "Guernsey and Jersey",
    "malaysia-singapore-brunei": "Malaysia, Singapore, and Brunei",
    "ireland-and-northern-ireland": "Ireland and Northern Ireland",
    "gcc-states": "GCC States",
    "saint-helena-ascension-and-tristan-da-cunha": "Saint Helena, Ascension, and Tristan da Cunha",
    "congo-brazzaville": "Congo-Brazzaville",
    "congo-democratic-republic": "Congo-Democratic Republic",
    "sao-tome-and-principe": "Sao Tome and Principe",
    "senegal-and-gambia": "Senegal and Gambia",
    "israel-and-palestine": "Israel and Palestine",
    "bosnia-herzegovina": "Bosnia-Herzegovina",
    "czech-republic": "Czech Republic",
    "provence-alpes-cote-d-azur": "Provence Alpes-Cote-d'Azur",
    "champagne-ardenne": "Champagne Ardenne",
    "franche-comte": "Franche Comte",
    "pays-de-la-loire": "Pays de la Loire",
    "nord-pas-de-calais": "Nord-Pas-de-Calais",
    "baden-wuerttemberg": "Baden-Wuerttemberg",
    "mecklenburg-vorpommern": "Mecklenburg-Vorpommern",
    "nordrhein-westfalen": "Nordrhein-Westfalen",
    "rheinland-pfalz": "Rheinland-Pfalz",
    "sachsen-anhalt": "Sachsen-Anhalt",
    "schleswig-holstein": "Schleswig-Holstein",
    "isle-of-man": "Isle of Man",
    "united-kingdom": "United Kingdom",
    "castilla-la-mancha": "Castilla-La Mancha",
    "castilla-y-leon": "Castilla y Leon",
    "islas-baleares": "Islas Baleares",
    "la-rioja": "La Rioja",
    "pais-vasco": "Pais Vasco",
    "new-caledonia": "New Caledonia",
    "new-zealand": "New Zealand",
    "papua-new-guinea": "Papua New Guinea",
    "pitcairn-islands": "Pitcairn Islands",
    "polynesie-francaise": "Polynesie Francaise",
    "solomon-islands": "Solomon Islands",
    "wallis-et-futuna": "Wallis et Futuna",
    "american-oceania": "American Oceania",
    "cook-islands": "Cook Islands",
    "ile-de-clipperton": "Ile de Clipperton",
    "marshall-islands": "Marshall Islands",
    "sierra-leone": "Sierra Leone",
    "south-africa": "South Africa",
    "south-sudan": "South Sudan",
    "canary-islands": "Canary Islands",
    "cape-verde": "Cape Verde",
    "central-african-republic": "Central African Republic",
    "equatorial-guinea": "Equatorial Guinea",
    "guinea-bissau": "Guinea-Bissau",
    "ivory-coast": "Ivory Coast",
    "burkina-faso": "Burkina Faso",
    "east-timor": "East Timor",
    "north-korea": "North Korea",
    "south-korea": "South Korea",
    "sri-lanka": "Sri Lanka",
    "inner-mongolia": "Inner Mongolia",
    "hong-kong": "Hong Kong",
    "faroe-islands": "Faroe Islands",
    "ile-de-france": "Ile-de-France",
    "languedoc-roussillon": "Languedoc-Roussillon",
    "basse-normandie": "Basse-Normandie",
    "haute-normandie": "Haute-Normandie",
    "midi-pyrenees": "Midi-Pyrenees",
    "poitou-charentes": "Poitou-Charentes",
    "rhone-alpes": "Rhone-Alpes",
    "nusa-tenggara": "Nusa-Tenggara",
    "kujawsko-pomorskie": "Kujawsko-Pomorskie",
    "warminsko-mazurskie": "Warminsko-Mazurskie",
    "isle-of-wight": "Isle of Wight",
    "east-sussex": "East Sussex",
    "east-yorkshire-with-hull": "East Yorkshire with Hull",
    "greater-london": "Greater London",
    "greater-manchester": "Greater Manchester",
    "north-yorkshire": "North Yorkshire",
    "south-yorkshire": "South Yorkshire",
    "tyne-and-wear": "Tyne and Wear",
    "west-midlands": "West Midlands",
    "west-sussex": "West Sussex",
    "west-yorkshire": "West Yorkshire",
    "el-salvador": "El Salvador",
    "costa-rica": "Costa Rica",
    "british-columbia": "British Columbia",
    "new-brunswick": "New Brunswick",
    "newfoundland-and-labrador": "Newfoundland and Labrador",
    "northwest-territories": "Northwest Territories",
    "nova-scotia": "Nova Scotia",
    "prince-edward-island": "Prince Edward Island",
    "district-of-columbia": "District of Columbia",
    "new-hampshire": "New Hampshire",
    "new-jersey": "New Jersey",
    "new-mexico": "New Mexico",
    "new-york": "New York",
    "north-carolina": "North Carolina",
    "north-dakota": "North Dakota",
    "puerto-rico": "Puerto Rico",
    "rhode-island": "Rhode Island",
    "south-carolina": "South Carolina",
    "south-dakota": "South Dakota",
    "us-virgin-islands": "US Virgin Islands",
    "west-virginia": "West Virginia",
    "falklands": "Falkland Islands",
    "centro-oeste": "Centro-Oeste",
    "central-fed-district": "Central Federal District",
    "crimean-fed-district": "Crimean Federal District",
    "far-eastern-fed-district": "Far Eastern Federal District",
    "north-caucasus-fed-district": "North Caucasus Federal District",
    "northwestern-fed-district": "Northwestern Federal District",
    "siberian-fed-district": "Siberian Federal District",
    "south-fed-district": "South Federal District",
    "ural-fed-district": "Ural Federal District",
    "volga-fed-district": "Volga Federal District",
    "nord-est": "Nord-Est",
    "nord-ovest": "Nord-Ovest",
    "noord-brabant": "Noord-Brabant",
    "noord-holland": "Noord-Holland",
    "zuid-holland": "Zuid-Holland",
}


def slug_to_name(slug):
    """Convert a URL slug to a display name.

    Uses DISPLAY_NAME_OVERRIDES for known special cases,
    falls back to titlecase with hyphens replaced by spaces.
    """
    if slug in DISPLAY_NAME_OVERRIDES:
        return DISPLAY_NAME_OVERRIDES[slug]
    return slug.replace("-", " ").title()


def stable_family_id(url_path):
    """Derive a stable FAMILY_ID from the URL path via hash.

    Garmin FAMILY_ID is 16-bit (valid range 1-65535). We hash the URL path
    and map into 1-65535. This is stable across additions/removals.
    """
    h = hashlib.sha256(url_path.encode()).digest()
    raw = int.from_bytes(h[:2], "big")
    return (raw % 65535) + 1


def fetch_index():
    """Fetch and parse the Geofabrik region index."""
    with urllib.request.urlopen(GEOFABRIK_INDEX_URL) as resp:
        return json.loads(resp.read())


def url_path_from_pbf(pbf_url):
    """Extract the URL path used for directory structure and FAMILY_ID hashing.

    e.g. 'https://download.geofabrik.de/europe/alps-latest.osm.pbf'
      -> 'europe/alps'
    """
    path = pbf_url.replace("https://download.geofabrik.de/", "")
    return path.replace("-latest.osm.pbf", "")


def url_path_to_profile_path(url_path, display_name):
    """Convert a URL path to a profile filesystem path.

    e.g. 'europe/germany/bayern', 'Bayern' -> 'Europe/Germany/Bayern.conf'
         'north-america/us/california', 'California' -> 'North America/United States/California.conf'

    Uses the provided display_name for the leaf (last segment) to handle
    overrides like 'Georgia (US State)'.
    """
    parts = url_path.split("/")
    dir_parts = [slug_to_name(p) for p in parts[:-1]]
    return os.path.join(*dir_parts, f"{display_name}.conf") if dir_parts else f"{display_name}.conf"


def write_profile(path, region_name, osm_url, family_id):
    """Write a single .conf profile file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(f'REGION_NAME="{region_name}"\n')
        f.write(f'OSM_URL="{osm_url}"\n')
        f.write(f'FAMILY_ID="{family_id}"\n')
        f.write(f'CONTOUR_STEP="{CONTOUR_STEP}"\n')
        f.write(f'CONTOUR_LINE_CAT="{CONTOUR_LINE_CAT}"\n')


def main():
    print("Fetching Geofabrik region index...")
    index_data = fetch_index()

    # Clean and recreate profiles directory
    if os.path.exists(PROFILES_DIR):
        shutil.rmtree(PROFILES_DIR)
    os.makedirs(PROFILES_DIR)

    all_family_ids = {}
    total = 0

    for feature in sorted(index_data["features"],
                          key=lambda f: f["properties"]["id"]):
        props = feature["properties"]
        region_id = props["id"]
        pbf_url = props.get("urls", {}).get("pbf")

        if not pbf_url:
            continue

        url_path = url_path_from_pbf(pbf_url)
        slug = url_path.split("/")[-1]

        # Skip large continent-level extracts
        if region_id in SKIP_CONTINENTS:
            continue

        # For the display name, check overrides by region_id first (e.g.
        # "us/georgia" -> "Georgia (US State)"), then fall back to slug
        if region_id in DISPLAY_NAME_OVERRIDES:
            display_name = DISPLAY_NAME_OVERRIDES[region_id]
        else:
            display_name = slug_to_name(slug)
        rel_path = url_path_to_profile_path(url_path, display_name)

        family_id = stable_family_id(url_path)

        # Handle hash collisions by linear probing
        while family_id in all_family_ids:
            print(
                f"WARNING: FAMILY_ID {family_id} collision between "
                f"{rel_path} and {all_family_ids[family_id]}, rehashing",
                file=sys.stderr,
            )
            family_id = (family_id % 65535) + 1
        all_family_ids[family_id] = rel_path

        full_path = os.path.join(PROFILES_DIR, rel_path)
        write_profile(full_path, display_name, pbf_url, family_id)
        total += 1

    print(f"Generated {total} profiles under {PROFILES_DIR}/")


if __name__ == "__main__":
    main()
