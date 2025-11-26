import json, math, os, argparse

"""Join POIs with nearest GTFS stops within a max walking distance."""
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0  # meters
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlmb/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pois", required=True)
    ap.add_argument("--stops", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max_walk", type=int, default=1200)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    stops = list(load_jsonl(args.stops))
    print(f"[info] Loaded {len(stops)} GTFS stops")

    w = open(args.out, "w", encoding="utf-8")
    n = 0

    for poi in load_jsonl(args.pois):
        coords = poi.get("coordinates") or poi.get("coords") or poi.get("center")
        if not coords:
            w.write(json.dumps(poi, ensure_ascii=False) + "\n")
            continue

        plat, plon = coords["lat"], coords["lon"]
        best_stop = None
        best_dist = 1e18

        for s in stops:
            d = haversine_m(plat, plon, s["lat"], s["lon"])
            if d < best_dist:
                best_dist = d
                best_stop = s

        if best_stop and best_dist <= args.max_walk:
            poi["nearest_stop"] = {
                "stop_id": best_stop["stop_id"],
                "stop_name": best_stop["stop_name"],
                "distance_m": round(best_dist, 1),
                "wheelchair_boarding": best_stop.get("wheelchair_boarding"),
            }
        else:
            poi["nearest_stop"] = None

        w.write(json.dumps(poi, ensure_ascii=False) + "\n")
        n += 1

    w.close()
    print(f"[ok] wrote {args.out} ({n} POIs processed)")

if __name__ == "__main__":
    main()