#!/usr/bin/env python3
"""Generate Garmin topo map profiles for all Geofabrik regions.

Encodes the complete Geofabrik download server hierarchy and generates
.conf files under profiles/ with deterministic FAMILY_IDs.
"""

import hashlib
import os
import shutil
import sys

BASE_URL = "https://download.geofabrik.de"
PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
CONTOUR_STEP = "50"
CONTOUR_LINE_CAT = "500,250"

# ---------------------------------------------------------------------------
# Geofabrik hierarchy data
# Each region: (display_name, slug) or (display_name, slug, [children])
# ---------------------------------------------------------------------------

AFRICA = [
    ("Algeria", "algeria"),
    ("Angola", "angola"),
    ("Benin", "benin"),
    ("Botswana", "botswana"),
    ("Burkina Faso", "burkina-faso"),
    ("Burundi", "burundi"),
    ("Cameroon", "cameroon"),
    ("Canary Islands", "canary-islands"),
    ("Cape Verde", "cape-verde"),
    ("Central African Republic", "central-african-republic"),
    ("Chad", "chad"),
    ("Comores", "comores"),
    ("Congo-Brazzaville", "congo-brazzaville"),
    ("Congo-Democratic Republic", "congo-democratic-republic"),
    ("Djibouti", "djibouti"),
    ("Egypt", "egypt"),
    ("Equatorial Guinea", "equatorial-guinea"),
    ("Eritrea", "eritrea"),
    ("Ethiopia", "ethiopia"),
    ("Gabon", "gabon"),
    ("Ghana", "ghana"),
    ("Guinea", "guinea"),
    ("Guinea-Bissau", "guinea-bissau"),
    ("Ivory Coast", "ivory-coast"),
    ("Kenya", "kenya"),
    ("Lesotho", "lesotho"),
    ("Liberia", "liberia"),
    ("Libya", "libya"),
    ("Madagascar", "madagascar"),
    ("Malawi", "malawi"),
    ("Mali", "mali"),
    ("Mauritania", "mauritania"),
    ("Mauritius", "mauritius"),
    ("Morocco", "morocco"),
    ("Mozambique", "mozambique"),
    ("Namibia", "namibia"),
    ("Niger", "niger"),
    ("Nigeria", "nigeria"),
    ("Rwanda", "rwanda"),
    ("Saint Helena, Ascension, and Tristan da Cunha", "saint-helena-ascension-and-tristan-da-cunha"),
    ("Sao Tome and Principe", "sao-tome-and-principe"),
    ("Senegal and Gambia", "senegal-and-gambia"),
    ("Seychelles", "seychelles"),
    ("Sierra Leone", "sierra-leone"),
    ("Somalia", "somalia"),
    ("South Africa", "south-africa"),
    ("South Sudan", "south-sudan"),
    ("Sudan", "sudan"),
    ("Swaziland", "swaziland"),
    ("Tanzania", "tanzania"),
    ("Togo", "togo"),
    ("Tunisia", "tunisia"),
    ("Uganda", "uganda"),
    ("Zambia", "zambia"),
    ("Zimbabwe", "zimbabwe"),
]

ASIA = [
    ("Afghanistan", "afghanistan"),
    ("Armenia", "armenia"),
    ("Azerbaijan", "azerbaijan"),
    ("Bangladesh", "bangladesh"),
    ("Bhutan", "bhutan"),
    ("Cambodia", "cambodia"),
    ("China", "china", [
        ("Anhui", "anhui"),
        ("Beijing", "beijing"),
        ("Chongqing", "chongqing"),
        ("Fujian", "fujian"),
        ("Gansu", "gansu"),
        ("Guangdong", "guangdong"),
        ("Guangxi", "guangxi"),
        ("Guizhou", "guizhou"),
        ("Hainan", "hainan"),
        ("Hebei", "hebei"),
        ("Heilongjiang", "heilongjiang"),
        ("Henan", "henan"),
        ("Hong Kong", "hong-kong"),
        ("Hubei", "hubei"),
        ("Hunan", "hunan"),
        ("Inner Mongolia", "inner-mongolia"),
        ("Jiangsu", "jiangsu"),
        ("Jiangxi", "jiangxi"),
        ("Jilin", "jilin"),
        ("Liaoning", "liaoning"),
        ("Macau", "macau"),
        ("Ningxia", "ningxia"),
        ("Qinghai", "qinghai"),
        ("Shaanxi", "shaanxi"),
        ("Shandong", "shandong"),
        ("Shanghai", "shanghai"),
        ("Shanxi", "shanxi"),
        ("Sichuan", "sichuan"),
        ("Tianjin", "tianjin"),
        ("Tibet", "tibet"),
        ("Xinjiang", "xinjiang"),
        ("Yunnan", "yunnan"),
        ("Zhejiang", "zhejiang"),
    ]),
    ("East Timor", "east-timor"),
    ("GCC States", "gcc-states"),
    ("India", "india", [
        ("Central Zone", "central-zone"),
        ("Eastern Zone", "eastern-zone"),
        ("North-Eastern Zone", "north-eastern-zone"),
        ("Northern Zone", "northern-zone"),
        ("Southern Zone", "southern-zone"),
        ("Western Zone", "western-zone"),
    ]),
    ("Indonesia", "indonesia", [
        ("Java", "java"),
        ("Kalimantan", "kalimantan"),
        ("Maluku", "maluku"),
        ("Nusa-Tenggara", "nusa-tenggara"),
        ("Papua", "papua"),
        ("Sulawesi", "sulawesi"),
        ("Sumatra", "sumatra"),
    ]),
    ("Iran", "iran"),
    ("Iraq", "iraq"),
    ("Israel and Palestine", "israel-and-palestine"),
    ("Japan", "japan", [
        ("Chubu", "chubu"),
        ("Chugoku", "chugoku"),
        ("Hokkaido", "hokkaido"),
        ("Kansai", "kansai"),
        ("Kanto", "kanto"),
        ("Kyushu", "kyushu"),
        ("Shikoku", "shikoku"),
        ("Tohoku", "tohoku"),
    ]),
    ("Jordan", "jordan"),
    ("Kazakhstan", "kazakhstan"),
    ("Kyrgyzstan", "kyrgyzstan"),
    ("Laos", "laos"),
    ("Lebanon", "lebanon"),
    ("Malaysia, Singapore, and Brunei", "malaysia-singapore-brunei"),
    ("Maldives", "maldives"),
    ("Mongolia", "mongolia"),
    ("Myanmar", "myanmar"),
    ("Nepal", "nepal"),
    ("North Korea", "north-korea"),
    ("Pakistan", "pakistan"),
    ("Philippines", "philippines"),
    ("South Korea", "south-korea"),
    ("Sri Lanka", "sri-lanka"),
    ("Syria", "syria"),
    ("Taiwan", "taiwan"),
    ("Tajikistan", "tajikistan"),
    ("Thailand", "thailand"),
    ("Turkmenistan", "turkmenistan"),
    ("Uzbekistan", "uzbekistan"),
    ("Vietnam", "vietnam"),
    ("Yemen", "yemen"),
]

AUSTRALIA_OCEANIA = [
    ("American Oceania", "american-oceania"),
    ("Australia", "australia"),
    ("Cook Islands", "cook-islands"),
    ("Fiji", "fiji"),
    ("Ile de Clipperton", "ile-de-clipperton"),
    ("Kiribati", "kiribati"),
    ("Marshall Islands", "marshall-islands"),
    ("Micronesia", "micronesia"),
    ("Nauru", "nauru"),
    ("New Caledonia", "new-caledonia"),
    ("New Zealand", "new-zealand"),
    ("Niue", "niue"),
    ("Palau", "palau"),
    ("Papua New Guinea", "papua-new-guinea"),
    ("Pitcairn Islands", "pitcairn-islands"),
    ("Polynesie Francaise", "polynesie-francaise"),
    ("Samoa", "samoa"),
    ("Solomon Islands", "solomon-islands"),
    ("Tokelau", "tokelau"),
    ("Tonga", "tonga"),
    ("Tuvalu", "tuvalu"),
    ("Vanuatu", "vanuatu"),
    ("Wallis et Futuna", "wallis-et-futuna"),
]

CENTRAL_AMERICA = [
    ("Bahamas", "bahamas"),
    ("Belize", "belize"),
    ("Costa Rica", "costa-rica"),
    ("Cuba", "cuba"),
    ("El Salvador", "el-salvador"),
    ("Guatemala", "guatemala"),
    ("Haiti and Dominican Republic", "haiti-and-domrep"),
    ("Honduras", "honduras"),
    ("Jamaica", "jamaica"),
    ("Nicaragua", "nicaragua"),
    ("Panama", "panama"),
]

EUROPE = [
    ("Albania", "albania"),
    ("Alps", "alps"),
    ("Andorra", "andorra"),
    ("Austria", "austria"),
    ("Azores", "azores"),
    ("Belarus", "belarus"),
    ("Belgium", "belgium"),
    ("Bosnia-Herzegovina", "bosnia-herzegovina"),
    ("Bulgaria", "bulgaria"),
    ("Croatia", "croatia"),
    ("Cyprus", "cyprus"),
    ("Czech Republic", "czech-republic"),
    ("Denmark", "denmark"),
    ("Estonia", "estonia"),
    ("Faroe Islands", "faroe-islands"),
    ("Finland", "finland"),
    ("France", "france", [
        ("Alsace", "alsace"),
        ("Aquitaine", "aquitaine"),
        ("Auvergne", "auvergne"),
        ("Basse-Normandie", "basse-normandie"),
        ("Bourgogne", "bourgogne"),
        ("Bretagne", "bretagne"),
        ("Centre", "centre"),
        ("Champagne Ardenne", "champagne-ardenne"),
        ("Corse", "corse"),
        ("Franche Comte", "franche-comte"),
        ("Guadeloupe", "guadeloupe"),
        ("Guyane", "guyane"),
        ("Haute-Normandie", "haute-normandie"),
        ("Ile-de-France", "ile-de-france"),
        ("Languedoc-Roussillon", "languedoc-roussillon"),
        ("Limousin", "limousin"),
        ("Lorraine", "lorraine"),
        ("Martinique", "martinique"),
        ("Mayotte", "mayotte"),
        ("Midi-Pyrenees", "midi-pyrenees"),
        ("Nord-Pas-de-Calais", "nord-pas-de-calais"),
        ("Pays de la Loire", "pays-de-la-loire"),
        ("Picardie", "picardie"),
        ("Poitou-Charentes", "poitou-charentes"),
        ("Provence Alpes-Cote-d'Azur", "provence-alpes-cote-d-azur"),
        ("Reunion", "reunion"),
        ("Rhone-Alpes", "rhone-alpes"),
    ]),
    ("Georgia", "georgia"),
    ("Germany", "germany", [
        ("Baden-Wuerttemberg", "baden-wuerttemberg"),
        ("Bayern", "bayern"),
        ("Berlin", "berlin"),
        ("Brandenburg", "brandenburg"),
        ("Bremen", "bremen"),
        ("Hamburg", "hamburg"),
        ("Hessen", "hessen"),
        ("Mecklenburg-Vorpommern", "mecklenburg-vorpommern"),
        ("Niedersachsen", "niedersachsen"),
        ("Nordrhein-Westfalen", "nordrhein-westfalen"),
        ("Rheinland-Pfalz", "rheinland-pfalz"),
        ("Saarland", "saarland"),
        ("Sachsen", "sachsen"),
        ("Sachsen-Anhalt", "sachsen-anhalt"),
        ("Schleswig-Holstein", "schleswig-holstein"),
        ("Thueringen", "thueringen"),
    ]),
    ("Greece", "greece"),
    ("Guernsey and Jersey", "guernsey-jersey"),
    ("Hungary", "hungary"),
    ("Iceland", "iceland"),
    ("Ireland and Northern Ireland", "ireland-and-northern-ireland"),
    ("Isle of Man", "isle-of-man"),
    ("Italy", "italy", [
        ("Centro", "centro"),
        ("Isole", "isole"),
        ("Nord-Est", "nord-est"),
        ("Nord-Ovest", "nord-ovest"),
        ("Sud", "sud"),
    ]),
    ("Kosovo", "kosovo"),
    ("Latvia", "latvia"),
    ("Liechtenstein", "liechtenstein"),
    ("Lithuania", "lithuania"),
    ("Luxembourg", "luxembourg"),
    ("Macedonia", "macedonia"),
    ("Malta", "malta"),
    ("Moldova", "moldova"),
    ("Monaco", "monaco"),
    ("Montenegro", "montenegro"),
    ("Netherlands", "netherlands", [
        ("Drenthe", "drenthe"),
        ("Flevoland", "flevoland"),
        ("Friesland", "friesland"),
        ("Gelderland", "gelderland"),
        ("Groningen", "groningen"),
        ("Limburg", "limburg"),
        ("Noord-Brabant", "noord-brabant"),
        ("Noord-Holland", "noord-holland"),
        ("Overijssel", "overijssel"),
        ("Utrecht", "utrecht"),
        ("Zeeland", "zeeland"),
        ("Zuid-Holland", "zuid-holland"),
    ]),
    ("Norway", "norway"),
    ("Poland", "poland", [
        ("Dolnoslaskie", "dolnoslaskie"),
        ("Kujawsko-Pomorskie", "kujawsko-pomorskie"),
        ("Lodzkie", "lodzkie"),
        ("Lubelskie", "lubelskie"),
        ("Lubuskie", "lubuskie"),
        ("Malopolskie", "malopolskie"),
        ("Mazowieckie", "mazowieckie"),
        ("Opolskie", "opolskie"),
        ("Podkarpackie", "podkarpackie"),
        ("Podlaskie", "podlaskie"),
        ("Pomorskie", "pomorskie"),
        ("Slaskie", "slaskie"),
        ("Swietokrzyskie", "swietokrzyskie"),
        ("Warminsko-Mazurskie", "warminsko-mazurskie"),
        ("Wielkopolskie", "wielkopolskie"),
        ("Zachodniopomorskie", "zachodniopomorskie"),
    ]),
    ("Portugal", "portugal"),
    ("Romania", "romania"),
    ("Serbia", "serbia"),
    ("Slovakia", "slovakia"),
    ("Slovenia", "slovenia"),
    ("Spain", "spain", [
        ("Andalucia", "andalucia"),
        ("Aragon", "aragon"),
        ("Asturias", "asturias"),
        ("Cantabria", "cantabria"),
        ("Castilla-La Mancha", "castilla-la-mancha"),
        ("Castilla y Leon", "castilla-y-leon"),
        ("Cataluna", "cataluna"),
        ("Ceuta", "ceuta"),
        ("Extremadura", "extremadura"),
        ("Galicia", "galicia"),
        ("Islas Baleares", "islas-baleares"),
        ("La Rioja", "la-rioja"),
        ("Madrid", "madrid"),
        ("Melilla", "melilla"),
        ("Murcia", "murcia"),
        ("Navarra", "navarra"),
        ("Pais Vasco", "pais-vasco"),
        ("Valencia", "valencia"),
    ]),
    ("Sweden", "sweden"),
    ("Switzerland", "switzerland"),
    ("Turkey", "turkey"),
    ("Ukraine", "ukraine"),
    ("United Kingdom", "united-kingdom", [
        ("Bermuda", "bermuda"),
        ("England", "england", [
            ("Bedfordshire", "bedfordshire"),
            ("Berkshire", "berkshire"),
            ("Bristol", "bristol"),
            ("Buckinghamshire", "buckinghamshire"),
            ("Cambridgeshire", "cambridgeshire"),
            ("Cheshire", "cheshire"),
            ("Cornwall", "cornwall"),
            ("Cumbria", "cumbria"),
            ("Derbyshire", "derbyshire"),
            ("Devon", "devon"),
            ("Dorset", "dorset"),
            ("Durham", "durham"),
            ("East Sussex", "east-sussex"),
            ("East Yorkshire with Hull", "east-yorkshire-with-hull"),
            ("Essex", "essex"),
            ("Gloucestershire", "gloucestershire"),
            ("Greater London", "greater-london"),
            ("Greater Manchester", "greater-manchester"),
            ("Hampshire", "hampshire"),
            ("Herefordshire", "herefordshire"),
            ("Hertfordshire", "hertfordshire"),
            ("Isle of Wight", "isle-of-wight"),
            ("Kent", "kent"),
            ("Lancashire", "lancashire"),
            ("Leicestershire", "leicestershire"),
            ("Lincolnshire", "lincolnshire"),
            ("Merseyside", "merseyside"),
            ("Norfolk", "norfolk"),
            ("North Yorkshire", "north-yorkshire"),
            ("Northamptonshire", "northamptonshire"),
            ("Northumberland", "northumberland"),
            ("Nottinghamshire", "nottinghamshire"),
            ("Oxfordshire", "oxfordshire"),
            ("Rutland", "rutland"),
            ("Shropshire", "shropshire"),
            ("Somerset", "somerset"),
            ("South Yorkshire", "south-yorkshire"),
            ("Staffordshire", "staffordshire"),
            ("Suffolk", "suffolk"),
            ("Surrey", "surrey"),
            ("Tyne and Wear", "tyne-and-wear"),
            ("Warwickshire", "warwickshire"),
            ("West Midlands", "west-midlands"),
            ("West Sussex", "west-sussex"),
            ("West Yorkshire", "west-yorkshire"),
            ("Wiltshire", "wiltshire"),
            ("Worcestershire", "worcestershire"),
        ]),
        ("Falkland Islands", "falklands"),
        ("Scotland", "scotland"),
        ("Wales", "wales"),
    ]),
]

NORTH_AMERICA = [
    ("Canada", "canada", [
        ("Alberta", "alberta"),
        ("British Columbia", "british-columbia"),
        ("Manitoba", "manitoba"),
        ("New Brunswick", "new-brunswick"),
        ("Newfoundland and Labrador", "newfoundland-and-labrador"),
        ("Northwest Territories", "northwest-territories"),
        ("Nova Scotia", "nova-scotia"),
        ("Nunavut", "nunavut"),
        ("Ontario", "ontario"),
        ("Prince Edward Island", "prince-edward-island"),
        ("Quebec", "quebec"),
        ("Saskatchewan", "saskatchewan"),
        ("Yukon", "yukon"),
    ]),
    ("Greenland", "greenland"),
    ("Mexico", "mexico"),
    ("United States", "us", [
        ("Alabama", "alabama"),
        ("Alaska", "alaska"),
        ("Arizona", "arizona"),
        ("Arkansas", "arkansas"),
        ("California", "california"),
        ("Colorado", "colorado"),
        ("Connecticut", "connecticut"),
        ("Delaware", "delaware"),
        ("District of Columbia", "district-of-columbia"),
        ("Florida", "florida"),
        ("Georgia (US State)", "georgia"),
        ("Hawaii", "hawaii"),
        ("Idaho", "idaho"),
        ("Illinois", "illinois"),
        ("Indiana", "indiana"),
        ("Iowa", "iowa"),
        ("Kansas", "kansas"),
        ("Kentucky", "kentucky"),
        ("Louisiana", "louisiana"),
        ("Maine", "maine"),
        ("Maryland", "maryland"),
        ("Massachusetts", "massachusetts"),
        ("Michigan", "michigan"),
        ("Minnesota", "minnesota"),
        ("Mississippi", "mississippi"),
        ("Missouri", "missouri"),
        ("Montana", "montana"),
        ("Nebraska", "nebraska"),
        ("Nevada", "nevada"),
        ("New Hampshire", "new-hampshire"),
        ("New Jersey", "new-jersey"),
        ("New Mexico", "new-mexico"),
        ("New York", "new-york"),
        ("North Carolina", "north-carolina"),
        ("North Dakota", "north-dakota"),
        ("Ohio", "ohio"),
        ("Oklahoma", "oklahoma"),
        ("Oregon", "oregon"),
        ("Pennsylvania", "pennsylvania"),
        ("Puerto Rico", "puerto-rico"),
        ("Rhode Island", "rhode-island"),
        ("South Carolina", "south-carolina"),
        ("South Dakota", "south-dakota"),
        ("Tennessee", "tennessee"),
        ("Texas", "texas"),
        ("US Virgin Islands", "us-virgin-islands"),
        ("Utah", "utah"),
        ("Vermont", "vermont"),
        ("Virginia", "virginia"),
        ("Washington", "washington"),
        ("West Virginia", "west-virginia"),
        ("Wisconsin", "wisconsin"),
        ("Wyoming", "wyoming"),
    ]),
]

RUSSIA = [
    ("Central Federal District", "central-fed-district"),
    ("Crimean Federal District", "crimean-fed-district"),
    ("Far Eastern Federal District", "far-eastern-fed-district"),
    ("Kaliningrad", "kaliningrad"),
    ("North Caucasus Federal District", "north-caucasus-fed-district"),
    ("Northwestern Federal District", "northwestern-fed-district"),
    ("Siberian Federal District", "siberian-fed-district"),
    ("South Federal District", "south-fed-district"),
    ("Ural Federal District", "ural-fed-district"),
    ("Volga Federal District", "volga-fed-district"),
]

SOUTH_AMERICA = [
    ("Argentina", "argentina"),
    ("Bolivia", "bolivia"),
    ("Brazil", "brazil", [
        ("Centro-Oeste", "centro-oeste"),
        ("Nordeste", "nordeste"),
        ("Norte", "norte"),
        ("Sudeste", "sudeste"),
        ("Sul", "sul"),
    ]),
    ("Chile", "chile"),
    ("Colombia", "colombia"),
    ("Ecuador", "ecuador"),
    ("Guyana", "guyana"),
    ("Paraguay", "paraguay"),
    ("Peru", "peru"),
    ("Suriname", "suriname"),
    ("Uruguay", "uruguay"),
    ("Venezuela", "venezuela"),
]

# ---------------------------------------------------------------------------
# Continent definitions
# ---------------------------------------------------------------------------

CONTINENTS = [
    {"name": "Africa", "slug": "africa",
     "toplevel": False, "regions": AFRICA},
    {"name": "Antarctica", "slug": "antarctica",
     "toplevel": True, "regions": []},
    {"name": "Asia", "slug": "asia",
     "toplevel": False, "regions": ASIA},
    {"name": "Australia-Oceania", "slug": "australia-oceania",
     "toplevel": False, "regions": AUSTRALIA_OCEANIA},
    {"name": "Central America", "slug": "central-america",
     "toplevel": False, "regions": CENTRAL_AMERICA},
    {"name": "Europe", "slug": "europe",
     "toplevel": False, "regions": EUROPE},
    {"name": "North America", "slug": "north-america",
     "toplevel": False, "regions": NORTH_AMERICA},
    {"name": "Russia", "slug": "russia",
     "toplevel": True, "regions": RUSSIA},
    {"name": "South America", "slug": "south-america",
     "toplevel": False, "regions": SOUTH_AMERICA},
]


def stable_family_id(url_path):
    """Derive a stable FAMILY_ID from the URL path via hash.

    Garmin FAMILY_ID is 16-bit (valid range 1-65535). We hash the URL path
    and map into 1-65535. This is stable across additions/removals.
    """
    h = hashlib.sha256(url_path.encode()).digest()
    # Use first 2 bytes for a 16-bit value, then map to 1-65535
    raw = int.from_bytes(h[:2], "big")
    return (raw % 65535) + 1


# ---------------------------------------------------------------------------
# Profile generation logic
# ---------------------------------------------------------------------------

def collect_profiles(continent):
    """Flatten hierarchy into list of (profile_rel_path, url_path, display_name)."""
    profiles = []
    name = continent["name"]
    slug = continent["slug"]

    # Top-level continents (Russia, Antarctica) get their own profile
    if continent["toplevel"]:
        profiles.append((f"{name}.conf", slug, name))

    def walk(regions, dir_prefix, url_prefix):
        for region in regions:
            rname = region[0]
            rslug = region[1]
            children = region[2] if len(region) > 2 else []

            profile_rel = os.path.join(dir_prefix, f"{rname}.conf")
            url_path = f"{url_prefix}/{rslug}"

            profiles.append((profile_rel, url_path, rname))

            if children:
                walk(children, os.path.join(dir_prefix, rname), url_path)

    walk(continent["regions"], name, slug)
    return profiles


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
    # Clean and recreate profiles directory
    if os.path.exists(PROFILES_DIR):
        shutil.rmtree(PROFILES_DIR)
    os.makedirs(PROFILES_DIR)

    all_family_ids = {}
    total = 0

    for continent in CONTINENTS:
        profiles = collect_profiles(continent)

        for rel_path, url_path, display_name in profiles:
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

            osm_url = f"{BASE_URL}/{url_path}-latest.osm.pbf"
            full_path = os.path.join(PROFILES_DIR, rel_path)

            write_profile(full_path, display_name, osm_url, family_id)
            total += 1

    print(f"Generated {total} profiles under {PROFILES_DIR}/")


if __name__ == "__main__":
    main()
