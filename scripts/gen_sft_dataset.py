#!/usr/bin/env python3
import json
import math
import argparse
import os
import random
import datetime as dt
from typing import List, Dict, Any

# -------------- Load cards -------------- #

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
    if "name" in card and card["name"]:
        return card["name"]
    tags = card.get("tags") or {}
    return tags.get("name") or "(unnamed place)"

def annotate_cards(cards: List[Dict[str, Any]]) -> None:
    """Add helper fields: _category, _score, _display_name."""
    for c in cards:
        tags = c.get("tags") or {}
        c["_category"] = get_category(tags)
        a11y = c.get("a11y") or {}
        combined = a11y.get("combined") or {}
        c["_score"] = combined.get("score", 0.0)
        c["_display_name"] = get_display_name(c)

# -------------- Retrieval helpers -------------- #

def passes_constraints(card: dict, wheelchair_only: bool) -> bool:
    tags = card.get("tags") or {}
    if wheelchair_only:
        w = str(tags.get("wheelchair") or "").lower()
        if w not in ("yes", "designated"):
            return False
    return True

def retrieve_candidates(
    cards: List[Dict[str, Any]],
    min_score: float,
    categories: List[str],
    wheelchair_only: bool,
    top_k: int,
) -> List[Dict[str, Any]]:
    cats_filter = {c.lower() for c in categories} if categories else None
    cands = []
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

# -------------- Rule-based itinerary builder -------------- #

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlmb/2)**2
    return 2 * R * math.asin(math.sqrt(h))

def get_coords(poi: dict):
    coords = poi.get("coordinates") or poi.get("coords") or poi.get("center")
    if coords:
        return coords["lat"], coords["lon"]
    return None, None

def build_itinerary(
    candidates: List[Dict[str, Any]],
    start_time_str: str = "10:00",
    stop_count: int = 6,
    slot_minutes: int = 90,
) -> List[Dict[str, Any]]:
    if not candidates:
        return []

    pool = sorted(candidates, key=lambda p: p["_score"], reverse=True)
    chosen = []

    # pick first by score
    current = pool.pop(0)
    chosen.append(current)

    # greedy nearest neighbor
    while pool and len(chosen) < stop_count:
        clat, clon = get_coords(current)
        if clat is None:
            current = pool.pop(0)
            chosen.append(current)
            continue

        best, best_d, best_idx = None, 1e18, None
        for idx, cand in enumerate(pool):
            lat, lon = get_coords(cand)
            if lat is None:
                continue
            d = haversine_m(clat, clon, lat, lon)
            if d < best_d:
                best_d, best, best_idx = d, cand, idx

        if best is None:
            best = pool.pop(0)
        else:
            pool.pop(best_idx)

        chosen.append(best)
        current = best

    # assign times
    h, m = map(int, start_time_str.split(":"))
    t = dt.datetime(2000, 1, 1, h, m)
    itinerary = []
    for poi in chosen:
        start = t
        end = start + dt.timedelta(minutes=slot_minutes)
        a11y = poi.get("a11y") or {}
        combined = a11y.get("combined") or {}
        itinerary.append({
            "name": poi["_display_name"],
            "start_time": start.strftime("%H:%M"),
            "end_time": end.strftime("%H:%M"),
            "explanation": (
                f"Good fit because it is a {poi['_category']} with accessibility grade "
                f"{combined.get('grade')} and fits the overall theme of the day."
            ),
            # keep internal IDs only if you want them for evaluation later
            # "poi_id": poi["id"],
        })
        t = end

    return itinerary

# -------------- Scenario definitions -------------- #

SCENARIOS = [
    {
        "name": "wheelchair_museums_coffee",
        "user_text": (
            "I use a wheelchair and I love art museums and coffee. "
            "I want a relaxed one-day itinerary in San Diego from 10:00 to 18:00 with a mix of culture and food."
        ),
        "constraints": ["wheelchair"],
        "prefs": ["museum", "art", "coffee"],
        "categories": ["attraction", "food"],
        "wheelchair_only": True,
        "min_score": 0.6,
        "top_k": 50,
        "stops": 6,
        "slot_minutes": 90,
    },
    {
        "name": "sensory_friendly_parks",
        "user_text": (
            "I prefer quieter, sensory-friendly outdoor spaces like parks and gardens. "
            "Please avoid very crowded or overwhelming places. A calm, nature-focused day would be ideal."
        ),
        "constraints": ["sensory"],
        "prefs": ["park", "garden"],
        "categories": ["park", "attraction"],
        "wheelchair_only": False,
        "min_score": 0.5,
        "top_k": 50,
        "stops": 5,
        "slot_minutes": 90,
    },
    {
        "name": "dietary_focused_food",
        "user_text": (
            "I care a lot about dietary options like vegan or gluten-free food. "
            "I want an itinerary that focuses on accessible restaurants and cafes, with one or two nearby sights."
        ),
        "constraints": ["dietary"],
        "prefs": ["vegan", "gluten-free", "restaurant"],
        "categories": ["food", "attraction"],
        "wheelchair_only": False,
        "min_score": 0.5,
        "top_k": 50,
        "stops": 6,
        "slot_minutes": 75,
    },
    {
        "name": "mixed_access_family_day",
        "user_text": (
            "I'm traveling with family, and one person uses a wheelchair. "
            "We like a mix of parks, museums, and kid-friendly activities, with reasonable travel times between stops."
        ),
        "constraints": ["wheelchair"],
        "prefs": ["museum", "park", "family"],
        "categories": ["park", "attraction", "food"],
        "wheelchair_only": True,
        "min_score": 0.55,
        "top_k": 60,
        "stops": 7,
        "slot_minutes": 75,
    },
]

# -------------- SFT example builder -------------- #

def format_candidates_for_prompt(cands: List[Dict[str, Any]]) -> str:
    """
    Natural-language bullet list: no OSM IDs, just names + short descriptors.
    """
    lines = []
    for c in cands:
        a11y = c.get("a11y") or {}
        combined = a11y.get("combined") or {}
        grade = combined.get("grade")
        best_mode = combined.get("best_mode")
        name = c["_display_name"]
        cat = c["_category"]
        line = (
            f"- {name}: a {cat} that is rated {grade} for accessibility "
            f"and is easiest to reach by {best_mode}."
        )
        lines.append(line)
    return "\n".join(lines)

def build_user_message(scenario: dict, cands: List[Dict[str, Any]]) -> str:
    cand_text = format_candidates_for_prompt(cands)
    constraints = scenario["constraints"]
    if constraints:
        constraints_text = "\n".join(f"- {c}" for c in constraints)
    else:
        constraints_text = "- none"

    return (
        "You are a helpful assistant that plans one-day itineraries in San Diego.\n\n"
        "Here is the traveler description:\n"
        f"{scenario['user_text']}\n\n"
        "Accessibility needs:\n"
        f"{constraints_text}\n\n"
        "Below are some possible places you can use in the itinerary:\n"
        f"{cand_text}\n\n"
        "Using only these places, create a coherent one-day itinerary in natural language. "
        "Make sure the itinerary is realistic in terms of timing and respects the accessibility needs.\n\n"
        "Return your answer as a JSON object with a single field \"itinerary\", where the value is a list of stops. "
        "Each stop must have:\n"
        "- \"name\": the place name\n"
        "- \"start_time\": e.g., \"10:00\"\n"
        "- \"end_time\": e.g., \"11:30\"\n"
        "- \"explanation\": a short explanation of why this stop is a good fit.\n"
    )

def build_assistant_message(itinerary: List[Dict[str, Any]]) -> str:
    obj = {"itinerary": itinerary}
    return json.dumps(obj, ensure_ascii=False, indent=2)

# -------------- Main -------------- #

def main():
    ap = argparse.ArgumentParser(description="Generate natural-language SFT chat dataset from poi_cards.jsonl.")
    ap.add_argument("--cards", required=True, help="canonical/poi_cards.jsonl")
    ap.add_argument("--out", required=True, help="training/chat_sft_natural.jsonl")
    ap.add_argument("--examples-per-scenario", type=int, default=10,
                    help="How many random examples to generate per scenario")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    cards = load_cards(args.cards)
    annotate_cards(cards)
    print(f"[load] cards: {len(cards)}")

    random.seed(42)

    n_written = 0
    with open(args.out, "w", encoding="utf-8") as fout:
        for scenario in SCENARIOS:
            for _ in range(args.examples_per-scenario if False else args.examples_per_scenario):
                cands = retrieve_candidates(
                    cards,
                    min_score=scenario["min_score"],
                    categories=scenario["categories"],
                    wheelchair_only=scenario["wheelchair_only"],
                    top_k=scenario["top_k"],
                )
                if len(cands) < scenario["stops"]:
                    continue

                # slight shuffle so candidate order varies
                random.shuffle(cands)
                itinerary = build_itinerary(
                    cands,
                    start_time_str="10:00",
                    stop_count=scenario["stops"],
                    slot_minutes=scenario["slot_minutes"],
                )
                if not itinerary:
                    continue

                user_msg = build_user_message(scenario, cands)
                assistant_msg = build_assistant_message(itinerary)

                example = {
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an accessibility-aware itinerary planner for San Diego."
                        },
                        {
                            "role": "user",
                            "content": user_msg
                        },
                        {
                            "role": "assistant",
                            "content": assistant_msg
                        }
                    ]
                }
                fout.write(json.dumps(example, ensure_ascii=False) + "\n")
                n_written += 1

    print(f"[ok] wrote {n_written} SFT examples to {args.out}")

if __name__ == "__main__":
    main()