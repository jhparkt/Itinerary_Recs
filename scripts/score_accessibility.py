import json
import argparse
import os
import math

def clamp01(x: float) -> float: # Clamp value to [0, 1] range
    return 0.0 if x < 0 else 1.0 if x > 1 else x

# ---------- On-site accessibility from OSM tags ----------

def onsite_score(tags: dict) -> float:
    # basic wheelchair
    wheelchair = str(tags.get("wheelchair") or "").lower()
    wc = 1.0 if wheelchair in ("yes", "designated") else 0.0 if wheelchair == "no" else 0.0

    ramp = 1.0 if str(tags.get("ramp") or "").lower() == "yes" else 0.0
    elev = 1.0 if str(tags.get("elevator") or "").lower() == "yes" else 0.0
    toilet = 1.0 if str(tags.get("toilets:wheelchair") or "").lower() == "yes" else 0.0
    tactile = 1.0 if str(tags.get("tactile_paving") or "").lower() == "yes" else 0.0

    surf = str(tags.get("surface") or "").lower()
    surface = 1.0 if surf in ("paved", "asphalt", "concrete") else 0.0

    return clamp01(
        0.30 * wc +
        0.10 * ramp +
        0.10 * elev +
        0.10 * toilet +
        0.05 * tactile +
        0.05 * surface
    )

# ---------- Transit reachability ----------

def reach_transit(nearest_stop: dict | None, max_walk_m: float = 600.0) -> float:
    if not nearest_stop:
        return 0.0
    d = nearest_stop.get("distance_m") or 1e9
    base = max(0.0, 1.0 - d / max_walk_m)  # linear decay

    wb = str(nearest_stop.get("wheelchair_boarding") or "")
    # GTFS convention: 0/empty=unknown, 1=some accessible, 2=no accessible
    if wb == "1":
        base = min(1.0, base + 0.2)
    elif wb == "2":
        base *= 0.5

    return clamp01(base)

# ---------- Driving / parking reachability ----------

def reach_driving(poi: dict) -> float:
    park = poi.get("nearest_parking")
    if not park:
        # assume street drop-off possible, but not ideal
        return 0.3

    d = park.get("distance_m", 9999.0)

    if d <= 50:
        base = 1.0
    elif d <= 150:
        base = 1.0 - (d - 50) / 100.0 * 0.5  # decrease to 0.5
    else:
        base = 0.3  # far away parking

    # boost if explicit disabled capacity
    cap_dis = park.get("capacity_disabled")
    try:
        if cap_dis is not None and int(cap_dis) > 0:
            base = min(1.0, base + 0.3)
    except Exception:
        pass

    # punish private/customers-only access
    access = str(park.get("access") or "").lower()
    if access in ("private", "residents"):
        base *= 0.6

    # slight penalty for paid parking
    fee = str(park.get("fee") or "").lower()
    if fee == "yes":
        base *= 0.9

    # low height garages may be bad for vans
    mh = park.get("maxheight")
    try:
        h_val = float(str(mh).split()[0]) if mh else None
        if h_val is not None and h_val < 2.0:
            base *= 0.8
    except Exception:
        pass

    return clamp01(base)

def grade(score: float) -> str:
    if score >= 0.80: return "A"
    if score >= 0.65: return "B"
    if score >= 0.50: return "C"
    return "D"

# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser(description="Score POIs for accessibility and write cards JSONL.")
    ap.add_argument("--in", required=True, dest="in_path",
                    help="Input joined POIs (e.g., canonical/poi_with_parking.jsonl)")
    ap.add_argument("--out", required=True, dest="out_path",
                    help="Output cards JSONL (e.g., canonical/poi_cards.jsonl)")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out_path), exist_ok=True)

    n = 0
    with open(args.in_path, encoding="utf-8") as fin, \
         open(args.out_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            poi = json.loads(line)

            tags = poi.get("tags") or {}

            onsite = onsite_score(tags)
            t_reach = reach_transit(poi.get("nearest_stop"))
            d_reach = reach_driving(poi)

            alpha = 0.7  # weight onsite more than reachability
            score_transit = clamp01(alpha * onsite + (1 - alpha) * t_reach)
            score_driving = clamp01(alpha * onsite + (1 - alpha) * d_reach)

            if score_transit >= score_driving:
                best_mode = "transit"
                best_score = score_transit
            else:
                best_mode = "driving"
                best_score = score_driving

            poi["a11y"] = {
                "onsite_score": onsite,
                "reach": {
                    "transit": {
                        "score": t_reach,
                        "distance_m": poi.get("nearest_stop", {}).get("distance_m")
                            if poi.get("nearest_stop") else None,
                    },
                    "driving": {
                        "score": d_reach,
                        "distance_m": poi.get("nearest_parking", {}).get("distance_m")
                            if poi.get("nearest_parking") else None,
                    }
                },
                "combined": {
                    "transit": score_transit,
                    "driving": score_driving,
                    "best_mode": best_mode,
                    "score": best_score,
                    "grade": grade(best_score),
                }
            }

            fout.write(json.dumps(poi, ensure_ascii=False) + "\n")
            n += 1

    print(f"[ok] wrote {args.out_path} ({n} POIs)")

if __name__ == "__main__":
    import json
    main()