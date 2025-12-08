import json, os, sys

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from schemas.poi_schema import AccessiblePOI, Coords

# Minimal tag→category mapping (extend as needed)
CAT_RULES = [
    (("tourism","museum"), "museum"),
    (("tourism","gallery"), "gallery"),
    (("tourism","aquarium"), "aquarium"),
    (("tourism","zoo"), "zoo"),
    (("tourism","viewpoint"), "viewpoint"),
    (("tourism","attraction"), "attraction"),
    (("tourism","theme_park"), "theme_park"),
    (("leisure","park"), "park"),
    (("natural","beach"), "beach"),
    (("amenity","restaurant"), "food"),
    (("amenity","cafe"), "food"),
    (("amenity","fast_food"), "food"),
    (("historic", None), "historic"),
]

ACCESS_KEYS = [
    "wheelchair","toilets:wheelchair","entrance:wheelchair","surface",
    "tactile_paving","ramp","smoothness","incline","steps","elevator"
]

def guess_category(tags: dict) -> str | None:
    for (k,v), cat in CAT_RULES:
        if v is None and k in tags: return cat
        if tags.get(k) == v: return cat
    return None

def centroid_for(element: dict) -> tuple[float,float] | None:
    # node --> lat/lon; way/relation → use 'center' if provided by Overpass query
    if element.get("type") == "node":
        return element.get("lat"), element.get("lon")
    c = element.get("center")
    if c and "lat" in c and "lon" in c:
        return c["lat"], c["lon"]
    return None

def main(in_path="./raw_data/osm/raw_osm.json", out_path="./canonical/pois.jsonl"):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(in_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    count_in, count_out = 0, 0
    with open(out_path, "w", encoding="utf-8") as out:
        for el in raw.get("elements", []):
            count_in += 1
            tags = el.get("tags") or {}
            pt = centroid_for(el)
            if not pt: continue
            lat, lon = pt
            name = tags.get("name")
            category = guess_category(tags)
            # keep everything but prefer canonical accessibility keys
            acc = {k.replace("toilets:wheelchair","toilets_wheelchair")
                     .replace("entrance:wheelchair","entrance_wheelchair"): tags[k]
                   for k in ACCESS_KEYS if k in tags}

            rec = AccessiblePOI(
                id=f"osm:{el['type']}:{el['id']}",
                name=name,
                category=category,
                coords=Coords(lat=lat, lon=lon),
                wheelchair=acc.get("wheelchair"),
                entrance_wheelchair=acc.get("entrance_wheelchair"),
                toilets_wheelchair=acc.get("toilets_wheelchair"),
                surface=acc.get("surface"),
                tactile_paving=acc.get("tactile_paving"),
                ramp=acc.get("ramp"),
                smoothness=acc.get("smoothness"),
                incline=acc.get("incline"),
                steps=acc.get("steps"),
                elevator=acc.get("elevator"),
                tags=tags
            )
            out.write(rec.model_dump_json() + "\n")
            count_out += 1

    print(f"[normalize_osm] read {count_in} elements, wrote {count_out} canonical POIs → {out_path}")

if __name__ == "__main__":
    in_p = sys.argv[1] if len(sys.argv)>1 else "./raw_data/osm/raw_osm.json"
    out_p = sys.argv[2] if len(sys.argv)>2 else "./canonical/pois.jsonl"
    main(in_p, out_p)