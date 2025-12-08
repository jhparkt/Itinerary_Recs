import json
import math
import argparse
import os

def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def haversine_m(lat1, lon1, lat2, lon2):
    """Return meters between two lat/lon points."""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2)**2
    return 2 * R * math.asin(math.sqrt(h))


def safe_int(x):
    try:
        return int(str(x))
    except:
        return None

def main():
    ap = argparse.ArgumentParser(description="Join POIs with nearest parking (entrances + lots).")
    ap.add_argument("--pois", required=True,
                    help="Input POIs (already joined with GTFS).")
    ap.add_argument("--parking", required=True,
                    help="Normalized parking JSONL file.")
    ap.add_argument("--out", required=True,
                    help="Output JSONL with nearest_parking field.")
    ap.add_argument("--r_entrance", type=float, default=200.0,
                    help="Max distance to consider a parking entrance (meters).")
    ap.add_argument("--r_lot", type=float, default=350.0,
                    help="Fallback max distance to consider a parking lot (meters).")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    # ---- Load parking ----
    entrances = []
    lots = []

    for p in load_jsonl(args.parking):
        kind = (p.get("kind") or "").lower()
        if kind in ("parking_entrance", "parking_entrance:multi-storey", "entrance"):
            entrances.append(p)
        elif kind in ("parking", "parking_lot", "multi-storey", "garage", "street_parking"):
            lots.append(p)
        else:
            lots.append(p)

    print(f"[load] parking entrances={len(entrances)} lots={len(lots)}")

    # ---- Process POIs ----
    out_f = open(args.out, "w", encoding="utf-8")
    count = 0

    for poi in load_jsonl(args.pois):
        # POI coordinate extraction (your canonical format)
        coords = (
            poi.get("coordinates")
            or poi.get("coords")
            or poi.get("center")
        )

        if not coords:
            poi["nearest_parking"] = None
            out_f.write(json.dumps(poi, ensure_ascii=False) + "\n")
            count += 1
            continue

        plat, plon = coords["lat"], coords["lon"]

        # ----- Step 1: Find nearest entrance -----
        best_ent = None
        best_ent_d = 1e18

        for e in entrances:
            d = haversine_m(plat, plon, e["lat"], e["lon"])
            if d < best_ent_d:
                best_ent_d = d
                best_ent = e

        # Accept entrance only if close enough
        if best_ent and best_ent_d <= args.r_entrance:
            parking = best_ent
            parking_dist = best_ent_d
        else:
            # ----- Step 2: fallback to lots -----
            best_lot = None
            best_lot_d = 1e18

            for l in lots:
                d = haversine_m(plat, plon, l["lat"], l["lon"])
                if d < best_lot_d:
                    best_lot_d = d
                    best_lot = l

            if best_lot and best_lot_d <= args.r_lot:
                parking = best_lot
                parking_dist = best_lot_d
            else:
                parking = None

        # ----- Write result -----
        if parking:
            tags = parking.get("tags") or {}

            poi["nearest_parking"] = {
                "id": parking.get("id"),
                "kind": parking.get("kind"),
                "distance_m": round(parking_dist, 1),

                # Useful metadata
                "access": tags.get("access"),
                "fee": tags.get("fee"),
                "capacity_disabled": safe_int(tags.get("capacity:disabled")),
                "maxheight": tags.get("maxheight"),
                "parking": tags.get("parking"),
            }
        else:
            poi["nearest_parking"] = None

        out_f.write(json.dumps(poi, ensure_ascii=False) + "\n")
        count += 1

    out_f.close()
    print(f"[ok] wrote {args.out} ({count} POIs).")


if __name__ == "__main__":
    main()