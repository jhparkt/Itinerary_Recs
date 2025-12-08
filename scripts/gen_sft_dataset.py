import json
import math
import argparse
import os
import random
import datetime as dt
from typing import List, Dict, Any, Optional

# -------------------------------
# Load + basic annotations
# -------------------------------

def load_cards(path: str) -> List[Dict[str, Any]]:
    cards = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cards.append(json.loads(line))
    return cards


def get_category(tags: dict) -> str:
    amenity = (tags.get("amenity") or "").lower()
    tourism = (tags.get("tourism") or "").lower()
    leisure = (tags.get("leisure") or "").lower()
    natural = (tags.get("natural") or "").lower()

    if tourism in ("museum", "gallery", "attraction", "theme_park", "zoo", "aquarium", "viewpoint"):
        return "attraction"
    if leisure in ("park", "garden"):
        return "park"
    if natural in ("beach",):
        return "beach"
    if amenity in ("restaurant", "cafe", "fast_food"):
        return "food"
    if tourism in ("hotel", "hostel"):
        return "lodging"
    return "other"


def get_display_name(card: dict) -> str:
    if card.get("name"):
        return card["name"]
    tags = card.get("tags") or {}
    return tags.get("name") or "(unnamed place)"


def annotate_cards(cards: List[Dict[str, Any]]) -> None:
    for c in cards:
        tags = c.get("tags") or {}
        c["_category"] = get_category(tags)

        a11y = c.get("a11y") or {}
        combined = a11y.get("combined") or {}
        c["_score"] = combined.get("score", 0.0)

        c["_display_name"] = get_display_name(c)


# -------------------------------
# Accessibility helpers
# -------------------------------

def passes_constraints(card: dict, wheelchair_only: bool) -> bool:
    tags = card.get("tags") or {}
    if wheelchair_only:
        w = str(tags.get("wheelchair") or "").lower()
        if w not in ("yes", "designated"):
            return False
    return True


def describe_accessibility(card: dict, constraints: List[str]) -> str:
    tags = card.get("tags") or {}
    a11y = card.get("a11y") or {}
    combined = a11y.get("combined") or {}

    parts = []

    w = (tags.get("wheelchair") or "").lower()
    if w == "yes":
        parts.append("wheelchair accessible")
    elif w == "limited":
        parts.append("partially wheelchair accessible")
    elif w == "no":
        parts.append("not wheelchair accessible")

    if (tags.get("tactile_paving") or "").lower() == "yes":
        parts.append("tactile paving available")
    if (tags.get("hearing_loop") or "").lower() == "yes":
        parts.append("hearing loop available")
    if (tags.get("toilets:wheelchair") or "").lower() == "yes":
        parts.append("accessible restroom")

    grade = combined.get("grade")
    if grade is not None:
        parts.append(f"overall accessibility grade {grade}")

    best_mode = combined.get("best_mode")
    if best_mode:
        parts.append(f"best reached by {best_mode}")

    if not parts:
        parts.append("basic accessibility (few explicit tags available)")

    if constraints:
        parts.append("relevant for constraints: " + ", ".join(constraints))

    return ", ".join(parts)


# -------------------------------
# Retrieval + distance
# -------------------------------

def retrieve_candidates(
    cards: List[Dict[str, Any]],
    min_score: float,
    categories: List[str],
    wheelchair_only: bool,
    top_k: int,
) -> List[Dict[str, Any]]:
    cats_filter = {c.lower() for c in categories} if categories else None
    cands: List[Dict[str, Any]] = []

    for c in cards:
        if c["_score"] < min_score:
            continue
        if cats_filter and c["_category"] not in cats_filter:
            continue
        if not passes_constraints(c, wheelchair_only):
            continue
        cands.append(c)

    cands.sort(key=lambda x: x["_score"], reverse=True)
    if len(cands) > top_k:
        cands = cands[:top_k]
    return cands


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def get_coords(poi: dict):
    coords = poi.get("coordinates") or poi.get("coords") or poi.get("center")
    if coords:
        return coords["lat"], coords["lon"]
    return None, None


def build_itinerary(
    candidates: List[Dict[str, Any]],
    constraints: List[str],
    start_time_str: str = "10:00",
    stop_count: int = 6,
    slot_minutes: int = 90,
    day_end: Optional[str] = None,
    max_hop_m: Optional[float] = None,
    prefer_first_categories: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    if not candidates:
        return []

    pool = sorted(candidates, key=lambda p: p["_score"], reverse=True)
    chosen: List[Dict[str, Any]] = []
    used_names = set()

    def pop_first():
        if not pool:
            return None
        if not prefer_first_categories:
            return pool.pop(0)
        pref = set(prefer_first_categories)
        for idx, cand in enumerate(pool):
            if cand["_category"] in pref:
                return pool.pop(idx)
        return pool.pop(0)

    first = pop_first()
    if not first:
        return []

    chosen.append(first)
    used_names.add(first["_display_name"])
    prev_lat, prev_lon = get_coords(first)

    while pool and len(chosen) < stop_count:
        best, best_d, best_idx = None, 1e18, None
        for idx, cand in enumerate(pool):
            name = cand["_display_name"]
            if name in used_names:
                continue

            lat, lon = get_coords(cand)
            if lat is None or prev_lat is None:
                d = 1e9
            else:
                d = haversine_m(prev_lat, prev_lon, lat, lon)

            if d < best_d:
                best_d, best, best_idx = d, cand, idx

        if best is None:
            break

        if max_hop_m is not None and best_d > max_hop_m:
            break

        pool.pop(best_idx)
        chosen.append(best)
        used_names.add(best["_display_name"])
        prev_lat, prev_lon = get_coords(best)

    start_h, start_m = map(int, start_time_str.split(":"))
    start_dt = dt.datetime(2000, 1, 1, start_h, start_m)

    if day_end is not None:
        end_h, end_m = map(int, day_end.split(":"))
        end_dt = dt.datetime(2000, 1, 1, end_h, end_m)
        total_minutes = max(60, int((end_dt - start_dt).total_seconds() // 60))
        slot_minutes = max(45, total_minutes // max(1, len(chosen)))

    itinerary: List[Dict[str, Any]] = []
    prev = None
    t = start_dt

    for poi in chosen:
        start = t
        end = start + dt.timedelta(minutes=slot_minutes)
        a11y_desc = describe_accessibility(poi, constraints)
        cat = poi["_category"]

        if prev is not None:
            lat1, lon1 = get_coords(prev)
            lat2, lon2 = get_coords(poi)
            if None not in (lat1, lon1, lat2, lon2):
                d_m = haversine_m(lat1, lon1, lat2, lon2)
                d_str = f"approximately {d_m:.0f} meters from the previous stop"
            else:
                d_str = "at a reasonable distance from the previous stop"
        else:
            d_str = "a good starting point for the day"

        explanation = (
            f"This stop is a {cat} and {d_str}. "
            f"It matches the user's accessibility needs because it is {a11y_desc}."
        )

        itinerary.append(
            {
                "name": poi["_display_name"],
                "start_time": start.strftime("%H:%M"),
                "end_time": end.strftime("%H:%M"),
                "explanation": explanation,
            }
        )

        t = end
        prev = poi

    return itinerary


# -------------------------------
# Scenarios (all wheelchair-focused)
# -------------------------------

SCENARIOS = [
    {
        "name": "wheelchair_museums_coffee",
        "user_text": (
            "I use a wheelchair and I love art museums and coffee. "
            "I want a relaxed, accessible one-day itinerary in San Diego from 10:00 to 18:00 "
            "with a mix of culture and food."
        ),
        "constraints": ["wheelchair"],
        "prefs": ["museum", "art", "coffee"],
        "categories": ["attraction", "food", "park"],
        "wheelchair_only": True,
        "min_score": 0.3,
        "top_k": 120,
        "stops": 5,
        "slot_minutes": 90,
        "min_stops": 4,
        "day_start": "10:00",
        "day_end": "18:00",
        "max_hop_m": 5000,
        "prefer_first_categories": ["attraction", "food"],
        "required_categories": ["food"],
    },
    {
        "name": "wheelchair_outdoors_easy_day",
        "user_text": (
            "I use a wheelchair and prefer open outdoor areas like parks, gardens, and waterfront views. "
            "Please avoid steep paths or uneven terrain. I want a peaceful accessible day."
        ),
        "constraints": ["wheelchair"],
        "prefs": ["park", "waterfront", "nature"],
        "categories": ["park", "attraction", "food"],
        "wheelchair_only": True,
        "min_score": 0.3,
        "top_k": 100,
        "stops": 5,
        "slot_minutes": 80,
        "min_stops": 4,
        "day_start": "10:00",
        "day_end": "18:00",
        "max_hop_m": 4000,
        "prefer_first_categories": ["park"],
    },
    {
        "name": "wheelchair_food_and_sights",
        "user_text": (
            "I use a wheelchair and want an itinerary focused on accessible restaurants and a few popular sights. "
            "Make sure all stops are wheelchair-friendly with smooth access."
        ),
        "constraints": ["wheelchair"],
        "prefs": ["food", "coffee", "easy_sights"],
        "categories": ["food", "attraction", "park"],
        "wheelchair_only": True,
        "min_score": 0.3,
        "top_k": 100,
        "stops": 6,
        "slot_minutes": 75,
        "min_stops": 4,
        "day_start": "10:00",
        "day_end": "18:30",
        "max_hop_m": 6000,
        "prefer_first_categories": ["food"],
        "required_categories": ["food"],
    },
    {
        "name": "wheelchair_family_day",
        "user_text": (
            "I use a wheelchair and am traveling with family. We want a mix of parks, museums, "
            "and kid-friendly activities with minimal hills and step-free access."
        ),
        "constraints": ["wheelchair"],
        "prefs": ["museum", "park", "family"],
        "categories": ["park", "attraction", "food"],
        "wheelchair_only": True,
        "min_score": 0.4,
        "top_k": 120,
        "stops": 6,
        "slot_minutes": 75,
        "min_stops": 4,
        "day_start": "09:30",
        "day_end": "18:30",
        "max_hop_m": 6000,
        "prefer_first_categories": ["park", "attraction"],
    },
    {
        "name": "wheelchair_evening_food_views",
        "user_text": (
            "I use a wheelchair and want an accessible afternoon and evening in San Diego with easy paths, "
            "good food, and nice coastal views. I prefer step-free access everywhere. Starting at 14:00 "
            "and ending around 22:00."
        ),
        "constraints": ["wheelchair"],
        "prefs": ["food", "views", "waterfront"],
        "categories": ["food", "attraction", "park"],
        "wheelchair_only": True,
        "min_score": 0.3,
        "top_k": 120,
        "stops": 5,
        "slot_minutes": 100,
        "min_stops": 4,
        "day_start": "14:00",
        "day_end": "22:00",
        "max_hop_m": 7000,
        "prefer_first_categories": ["food", "attraction"],
    },
    {
        "name": "wheelchair_short_low_effort",
        "user_text": (
            "I use a wheelchair and want a very low-effort half-day plan with locations close together "
            "and easy rolling surfaces. No steep hills."
        ),
        "constraints": ["wheelchair"],
        "prefs": ["short_walks", "easy_access", "rest"],
        "categories": ["attraction", "park", "food"],
        "wheelchair_only": True,
        "min_score": 0.3,
        "top_k": 80,
        "stops": 4,
        "slot_minutes": 90,
        "min_stops": 3,
        "day_start": "10:00",
        "day_end": "15:00",
        "max_hop_m": 3000,
        "prefer_first_categories": ["park", "food"],
    },
]


# -------------------------------
# Prompt formatting
# -------------------------------

def format_candidates_for_prompt(cands: List[Dict[str, Any]], constraints: List[str]) -> str:
    lines = []
    for c in cands:
        name = c["_display_name"]
        cat = c["_category"]
        a11y_desc = describe_accessibility(c, constraints)
        lines.append(f"- {name}: category={cat}, accessibility={a11y_desc}")
    return "\n".join(lines)


def build_user_message(scenario: dict, cands: List[Dict[str, Any]]) -> str:
    cand_text = format_candidates_for_prompt(cands, scenario["constraints"])
    constraints = scenario["constraints"]
    if constraints:
        constraints_text = "\n".join(f"- {c}" for c in constraints)
    else:
        constraints_text = "- none"

    return (
        "You are a helpful assistant that plans one-day itineraries in San Diego.\n\n"
        "You MUST:\n"
        "- Use ONLY the places listed below (do NOT invent new locations).\n"
        "- Respect all accessibility needs.\n"
        "- Prefer short travel distances between consecutive stops.\n"
        "- Produce a realistic schedule with non-overlapping times.\n\n"
        "Here is the traveler description:\n"
        f"{scenario['user_text']}\n\n"
        "Accessibility needs:\n"
        f"{constraints_text}\n\n"
        "Below are candidate places you may use in the itinerary:\n"
        f"{cand_text}\n\n"
        "Using only these places, create a coherent one-day itinerary. "
        "Make sure the itinerary is realistic in terms of timing and explicitly respects the accessibility needs.\n\n"
        "Return your answer as a JSON object with a single field \"itinerary\", where the value is a list of stops. "
        "Each stop must have:\n"
        "- \"name\": the place name\n"
        "- \"start_time\": e.g., \"10:00\"\n"
        "- \"end_time\": e.g., \"11:30\"\n"
        "- \"explanation\": a short explanation of why this stop is a good fit, "
        "including accessibility reasoning and, when relevant, short travel distance from the previous stop.\n"
    )


def build_assistant_message(itinerary: List[Dict[str, Any]]) -> str:
    return json.dumps({"itinerary": itinerary}, ensure_ascii=False, indent=2)


# -------------------------------
# generate SFT jsonl
# -------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Generate natural-language SFT chat dataset from poi_cards.jsonl."
    )
    ap.add_argument("--cards", required=True, help="canonical/poi_cards.jsonl")
    ap.add_argument("--out", required=True, help="training/chat_sft_natural.jsonl")
    ap.add_argument(
        "--examples-per-scenario",
        type=int,
        default=10,
        help="How many random examples to generate per scenario",
    )
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    cards = load_cards(args.cards)
    annotate_cards(cards)
    print(f"[load] cards: {len(cards)}")

    random.seed(42)
    n_written = 0

    with open(args.out, "w", encoding="utf-8") as fout:
        for scenario in SCENARIOS:
            for _ in range(args.examples_per_scenario):
                all_cands = retrieve_candidates(
                    cards,
                    min_score=scenario["min_score"],
                    categories=scenario["categories"],
                    wheelchair_only=scenario["wheelchair_only"],
                    top_k=scenario["top_k"],
                )

                if len(all_cands) < scenario["stops"]:
                    print(
                        f"[skip] {scenario['name']} — only {len(all_cands)} candidates "
                        f"(need >= {scenario['stops']})"
                    )
                    continue

                req_cats = scenario.get("required_categories") or []
                if req_cats:
                    cats_present = {c["_category"] for c in all_cands}
                    if any(rc not in cats_present for rc in req_cats):
                        print(f"[skip] {scenario['name']} — missing required categories {req_cats}")
                        continue

                # subset shown to the model
                prompt_k = min(len(all_cands), 12)
                cands_for_prompt = random.sample(all_cands, k=prompt_k)
                random.shuffle(cands_for_prompt)

                itinerary = build_itinerary(
                    cands_for_prompt,
                    constraints=scenario["constraints"],
                    start_time_str=scenario.get("day_start", "10:00"),
                    stop_count=scenario["stops"],
                    slot_minutes=scenario["slot_minutes"],
                    day_end=scenario.get("day_end"),
                    max_hop_m=scenario.get("max_hop_m"),
                    prefer_first_categories=scenario.get("prefer_first_categories"),
                )
                if not itinerary:
                    continue

                min_stops = scenario.get("min_stops", 3)
                if len(itinerary) < min_stops:
                    continue

                valid_names = {c["_display_name"] for c in cands_for_prompt}
                if not all(stop["name"] in valid_names for stop in itinerary):
                    continue

                user_msg = build_user_message(scenario, cands_for_prompt)
                assistant_msg = build_assistant_message(itinerary)

                example = {
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an accessibility-aware itinerary planner for San Diego. "
                                "You must obey all accessibility constraints, be honest about the data, "
                                "and prefer itineraries with short travel distances between stops."
                            ),
                        },
                        {"role": "user", "content": user_msg},
                        {"role": "assistant", "content": assistant_msg},
                    ]
                }
                fout.write(json.dumps(example, ensure_ascii=False) + "\n")
                n_written += 1

    print(f"[ok] wrote {n_written} SFT examples to {args.out}")


if __name__ == "__main__":
    main()