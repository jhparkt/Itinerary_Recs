"""
This is the collector module for OpenStreetMap (OSM) data using the Overpass API.
It defines constants for API mirrors and preset queries for various points of interest (POIs).
"""

import os
import requests
import time
import json
from typing import List
import argparse
import sys

# Declaring constants for the OpenStreetMap API --> Failsafes
MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

PRESETS = {
    "museums": [
        'nwr["tourism"="museum"]'
    ],
    "parks_beaches": [
        'nwr["leisure"="park"]',
        'nwr["natural"="beach"]'
    ],
    "food": [
        'nwr["amenity"~"^(restaurant|cafe|fast_food)$"]'
    ],
    "attractions": [
        'nwr["tourism"~"^(attraction|gallery|aquarium|zoo|viewpoint|theme_park)$"]'
    ],
    "all_basic": [  # Starter pack of common POIs --> Expand potentially
        'nwr["tourism"~"^(museum|gallery|aquarium|zoo|viewpoint|attraction|theme_park)$"]',
        'nwr["leisure"="park"]',
        'nwr["natural"="beach"]',
        'nwr["amenity"~"^(restaurant|cafe|fast_food)$"]',
        'nwr["historic"]'
    ],
}

# ------------ Query Constructors ------------
def area_clause(city_name: str) -> str:
    """Constructs the area clause for a given city name."""
    return f'area["name"="{city_name}"]["boundary"="administrative"]->.A;'

def make_query_city(city:str, selectors, timeout:int = 90) -> str:
    """Constructs a full Overpass API query for a given city and selectors."""
    where = f"{area_clause(city)}\n(\n" + "\n".join(
        f"  {sel}(area.A);" for sel in selectors
    ) + "\n);\n"
    return f"""[out:json][timeout:{timeout}];{where}out center tags;"""

# ------------ POST Request ------------

def post_overpass(query: str, mirrors: List[str], retries: int, backoff: float, per_req_timeout: int):
    
    last_err = None

    for m_ix, url in enumerate(mirrors, start=1):
        for attempt in range(1, retries + 2):  # e.g., retries=2 --> attempts 1..3

            print(f"[fetch] mirror {m_ix}/{len(mirrors)}: {url} (attempt {attempt})")
            t0 = time.perf_counter()

            try: # Successful request for current mirror
                r = requests.post(url, data={"data": query}, timeout=per_req_timeout)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                r.raise_for_status()
                print(f"[fetch] ✅ success in {elapsed_ms} ms")
                return r.json()
            
            except Exception as e: # Failed request for current mirror
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                print(f"[fetch] ❌ failed in {elapsed_ms} ms: {e}")
                last_err = e
                sleep_s = backoff * attempt
                print(f"[fetch] ⏳ backing off {sleep_s:.1f}s before retry")
                time.sleep(sleep_s)

        print("[fetch] trying next mirror ...")

    raise RuntimeError(f"All mirrors failed. Last error: {last_err}")


# ------- Runner -------
def main():
    ap = argparse.ArgumentParser(description="Fetch raw OSM (Overpass) data for a CITY boundary")
    ap.add_argument("--city", default="San Diego", help="City name to match administrative boundary (default: San Diego)")
    ap.add_argument("--preset", default="all_basic", choices=PRESETS.keys(), help="What to fetch (default: all_basic)")
    ap.add_argument("--out", default="./raw_data/raw_osm.json", help="Output file (raw Overpass JSON)")
    ap.add_argument("--timeout", type=int, default=90, help="Overpass query timeout seconds (default: 90)")
    ap.add_argument("--retries", type=int, default=2, help="Retries per mirror on failure (default: 2)")
    ap.add_argument("--backoff", type=float, default=3.0, help="Backoff seconds * attempt index (default: 3.0)")
    ap.add_argument("--per_req_timeout", type=int, default=180, help="HTTP request timeout seconds (default: 180)")
    ap.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds after success (politeness)")
    args = ap.parse_args()

    selectors = PRESETS[args.preset]
    q = make_query_city(args.city, selectors, timeout=args.timeout)

    print(f"[query] city={args.city!r} preset={args.preset!r} timeout={args.timeout}s")
    print(f"[query] total selectors: {len(selectors)}")
    print("[query] sending to Overpass…")

    data = post_overpass(
        q,
        mirrors=MIRRORS,
        retries=args.retries,
        backoff=args.backoff,
        per_req_timeout=args.per_req_timeout,
    )

    count = len(data.get("elements", []))
    print(f"[save] elements: {count}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"[save] wrote {args.out}")

    if args.sleep:
        print(f"[sleep] {args.sleep:.1f}s")
        time.sleep(args.sleep)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[exit] interrupted by user")
        sys.exit(1)