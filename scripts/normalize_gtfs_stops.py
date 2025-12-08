import csv, json, os

GTFS_DIR = "data_collection/raw_data/gtfs"
OUT = "canonical/gtfs_stops.jsonl"

def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def main():
    stops = read_csv(os.path.join(GTFS_DIR, "stops.txt"))
    # Optional: routes/trips/stop_times later if you want route names per stop
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as w:
        for s in stops:
            rec = {
                "stop_id": s["stop_id"],
                "stop_name": s.get("stop_name"),
                "lat": float(s["stop_lat"]),
                "lon": float(s["stop_lon"]),
                # 0=unknown/not possible, 1=some vehicles accommodate, 2=no info (varies by feeds)
                "wheelchair_boarding": s.get("wheelchair_boarding"),
            }
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[ok] wrote {OUT} ({len(stops)} stops)")

if __name__ == "__main__":
    main()