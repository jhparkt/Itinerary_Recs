import json, os, argparse

KEEP_TAGS = {
    "access", "fee", "capacity", "capacity:disabled",
    "maxheight", "parking", "name", "operator", "covered"
}

def classify_kind(tags):
    if tags.get("amenity") == "parking_entrance":
        return "parking_entrance"
    if tags.get("amenity") == "parking":
        return "parking"
    if tags.get("parking_space") == "disabled":
        return "disabled_space"
    if tags.get("parking") == "street_side":
        return "street_parking"
    return "other"

def elem_to_record(el):
    tags = el.get("tags") or {}
    typ  = el.get("type")
    if typ == "node":
        lat, lon = el.get("lat"), el.get("lon")
    else:
        c = el.get("center") or {}
        lat, lon = c.get("lat"), c.get("lon")
    if lat is None or lon is None:
        return None

    keep = {k: tags.get(k) for k in KEEP_TAGS}
    return {
        "id": f'osm:{typ}:{el.get("id")}',
        "kind": classify_kind(tags),
        "lat": lat,
        "lon": lon,
        "tags": keep
    }

def main():
    ap = argparse.ArgumentParser(description="Normalize raw Overpass parking JSON → JSONL")
    ap.add_argument("--in", required=True, dest="in_path", help="raw_data/raw_parking.json")
    ap.add_argument("--out", required=True, dest="out_path", help="canonical/parking.jsonl")
    args = ap.parse_args()

    with open(args.in_path, encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(os.path.dirname(args.out_path), exist_ok=True)

    seen = set(); kept = 0
    with open(args.out_path, "w", encoding="utf-8") as w:
        for el in data.get("elements", []):
            rec = elem_to_record(el)
            if not rec:
                continue
            if rec["id"] in seen:
                continue
            seen.add(rec["id"])
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
            kept += 1
    print(f"[ok] wrote {args.out_path} ({kept} records)")

if __name__ == "__main__":
    main()