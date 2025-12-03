import math
from typing import List

# Test Variables

# Single Point of Interest (POI)
POI = {
    "id": int,
    "name": str,
    "lat": float,
    "lon": float,
    "poi_type": str, # amenity / tourism
    "features": {
        "wheelchair": bool,
        "toilets:wheelchair": bool,
        "air_conditioning": bool
        # More features can be added
    }
}

# User preferences/constraints (pref)
USER_PREFERNCES = {
    "start_location": {"lat": float, "lon": float},
    "avg_travel_speed_mph": float,
    "max_travel_time_minutes": float,
    "required_accessibility": List[str],  # ["wheelchair", "toilets:wheelchair"]
    "amenity_type": str, #'fast_food', 'restaurant', 'cafe', 'post_office', 'fountain', 'bench', 'theatre', 'clock', 'bicycle_parking', 'planetarium', 'conference_centre', 'fire_station', 'cinema', 'toilets', 'arts_centre', 'place_of_worship'
    "tourism_type": str, # 'attraction', 'gallery', 'museum', 'viewpoint', 'artwork', 'aquarium', 'zoo', 'theme_park'
    "cuisine": str,
}

TEST_ITINERARY = [
    {"id": 1, "name": "Tiger Coffee", "lat": 34.04, "lon": -118.26, "poi_type": "amenity", 
     "features": {"wheelchair": True, "toilets:wheelchair": True, "air_conditioning": True},
     "amenity": "cafe", "cuisine": "italian"}, 
     
    {"id": 2, "name": "History Museum", "lat": 34.07, "lon": -118.23, "poi_type": "tourism", 
     "features": {"wheelchair": True, "toilets:wheelchair": True, "air_conditioning": True},
     "tourism": "museum"},
     
    {"id": 3, "name": "Sculpture Garden", "lat": 34.03, "lon": -118.28, "poi_type": "tourism", 
     "features": {"wheelchair": True, "toilets:wheelchair": False, "air_conditioning": False},
     "tourism": "artwork"},
]

TEST_PREFERENCES = {
    "start_location": {"lat": 34.05, "lon": -118.25}, 
    "avg_travel_speed_mph": 20.0, 
    "max_travel_time_minutes": 45.0,
    "required_accessibility": "wheelchair|toilets:wheelchair",
    "amenity_type": "restaurant|cafe", 
    "tourism_type": "museum|gallery", 
    "cuisine": "italian|american",
}

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 3958.8  #miles
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    
    d_lat = lat2_rad - lat1_rad
    d_lon = lon2_rad - lon1_rad
    
    a = math.sin(d_lat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(d_lon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return radius * c


# Evaluation Metrics

def get_tdts_score(itinerary, pref):
    """
    Get Travel Distance/Time Score
    Score = (Max Time - Actual Time) / Max Time. 
    - 1.0 = perfect use of time
    - 0.0 = time is maxed out
    - <0.0 = infeasible

    Returns: (score, total_distance_miles, total_time_minutes)
    """
    if not itinerary:
        return 0.0, 0.0, 0.0

    curr_loc = pref["start_location"]
    total_dist = 0.0

    for poi in itinerary:
        distance_to_next = haversine(curr_loc["lat"], curr_loc["lon"], poi["lat"], poi["lon"])
        total_dist += distance_to_next
        curr_loc = {"lat": poi["lat"], "lon": poi["lon"]}
    
    # Calculate total travel time
    avg_speed = pref.get("avg_travel_speed_mph", 15.0)
    max_time = pref.get("max_travel_time_minutes", 60.0)
    
    total_time_minutes = (total_dist / avg_speed) * 60.0
    
    # Calculate score
    tdts_score = (max_time - total_time_minutes) / max_time
    
    return tdts_score, total_dist, total_time_minutes

def get_diversity_score(itinerary):
    """
    POI Diversity Score
    Score = (Number of unique POI types) / (Total number of pois).
    - 1.0 = Very diverse
    - 0.0 = All POI same type
    """
    if not itinerary:
        return 0.0

    poi_types = [poi.get("poi_type") for poi in itinerary if poi.get("poi_type")]
    
    if not poi_types:
        return 0.0
        
    unique_types = set(poi_types)
    
    diversity_score = len(unique_types) / len(poi_types)
    return diversity_score

def get_pref_coverage(itinerary, pref):
    """
    Preference Coverage
    Score = (Number of pois matching any user preference) / (Total number of pois).
    """
    if not itinerary:
        return 0.0

    match_count = 0
    
    # current preferences type
    pref_amenity = pref.get("amenity_type")
    pref_tourism = pref.get("tourism_type")
    pref_cuisine = pref.get("cuisine")

    for poi in itinerary:
        is_match = False

        if poi.get("poi_type") == "amenity" and str(poi.get("amenity")) in pref_amenity:
            is_match = True
        
        elif poi.get("poi_type") == "tourism" and str(poi.get("tourism")) in pref_tourism:
            is_match = True

        elif poi.get("poi_type") == "amenity" and str(poi.get("cuisine")) in pref_cuisine:
            is_match = True

        if is_match:
            match_count += 1

    preference_coverage = match_count / len(itinerary)
    return preference_coverage

def get_accessibility_acc(itinerary, pref):
    """
    Measures how many POIs adhere to ALL required accessibility constraints
    Score = (Number of fully compliant pois) / (Total number of pois).
    """
    if not itinerary:
        return 0.0

    required_accessibility = pref.get("required_accessibility", "")

    compliant_pois = 0
    for poi in itinerary:
        is_fully_compliant = True
        poi_features = poi.get("features", {})
        
        for feature in required_accessibility.split("|"):
            if not poi_features.get(feature, False):
                is_fully_compliant = False
                break
        
        if is_fully_compliant:
            compliant_pois += 1
    
    accuracy = compliant_pois / len(itinerary)
    return accuracy

def get_compliance_rate(itinerary, pref):
    """
    Measures how much of the accessibility requirements are satisfied
    Score = (Total number of required features MET) / (Total number of features REQUIRED across all pois).
    """
    if not itinerary:
        return 0.0

    required_accessibility = pref.get("required_accessibility", "")
        
    total_required_count = len(required_accessibility.split("|")) * len(itinerary)
    total_met_count = 0

    if total_required_count == 0:
        return 1.0

    for poi in itinerary:
        poi_features = poi.get("features", {})
        for feature in required_accessibility.split("|"):
            if poi_features.get(feature, False):
                total_met_count += 1

    compliance_rate = total_met_count / total_required_count
    return compliance_rate

def get_evaluation_metrics(itinerary, pref):
    tdts_score, total_distance, total_time = get_tdts_score(itinerary, pref)
    diversity_score = get_diversity_score(itinerary)
    pref_coverage = get_pref_coverage(itinerary, pref)
    accessibility_acc = get_accessibility_acc(itinerary, pref)
    compliance_rate = get_compliance_rate(itinerary, pref)
    return [tdts_score, total_distance, total_time, diversity_score, pref_coverage, accessibility_acc, compliance_rate]

def print_with_lines(str):
    print("\n" + "-" * 80)
    print(str)
    print("-" * 80)

def get_evaluation_metrics_verbose(itinerary, pref):
    eval_metrics = get_evaluation_metrics(itinerary, pref)
    tdts_score, total_distance, total_time = eval_metrics[0], eval_metrics[1], eval_metrics[2]
    diversity_score = eval_metrics[3]
    pref_coverage = eval_metrics[4]
    accessibility_acc = eval_metrics[5]
    compliance_rate = eval_metrics[6]

    print_with_lines("Itinerary")
    print(f"Total POIs: {len(itinerary)}")
    print(f"User Preferences: {pref}" )
    print(f"Required Features: {pref['required_accessibility']}")
    
    print_with_lines("Quality of POI Metric")
    print(f"Total Travel Distance: {total_distance:.2f} miles")
    print(f"Total Travel Time: {total_time:.1f} minutes (Max: {pref['max_travel_time_minutes']:.1f} min)")
    print(f"Travel Distance/Time Score: {tdts_score:.2f}")
    print(f"POI Diversity Score: {diversity_score:.2f}")
    print(f"Preference Coverage: {pref_coverage:.2f}")

    print_with_lines("Adherence to Accessibility Constraints Metrics")
    print(f"Accuracy (Fully Compliant POIs): {accessibility_acc:.2f}")
    print(f"Compliance Rate (Granular Features Met): {compliance_rate:.2f}")
    
    is_feasible = (tdts_score >= 0.0) and (accessibility_acc == 1.0)
    print(f"\nOverall Feasibility: {'TRUE' if is_feasible else 'FALSE'}")
    return eval_metrics
    
if __name__ == "__main__":
    get_evaluation_metrics_verbose(TEST_ITINERARY, TEST_PREFERENCES)