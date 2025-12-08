import json
import random

# random seed
random.seed(42)

SAN_DIEGO_LOCATIONS = [
    {"lat": 32.7160, "lon": -117.1613, "name": "Downtown/Gaslamp"},
    {"lat": 32.7310, "lon": -117.1448, "name": "Balboa Park"},
    {"lat": 32.8593, "lon": -117.2543, "name": "La Jolla Shores"},
    {"lat": 32.7551, "lon": -117.1950, "name": "Old Town"},
    {"lat": 32.7303, "lon": -117.2155, "name": "Point Loma/Liberty Station"},
    {"lat": 32.6997, "lon": -117.1788, "name": "Coronado"},
    {"lat": 32.6401, "lon": -117.0863, "name": "Chula Vista (South Bay)"},
    {"lat": 32.7483, "lon": -117.1466, "name": "North Park/Hillcrest"},
]

# Options for different preferences
AMENITY_OPTIONS = ['fast_food', 'restaurant', 'cafe', 'post_office', 'fountain', 'bench', 'theatre', 'clock', 
                    'bicycle_parking', 'planetarium', 'conference_centre', 'fire_station', 'cinema', 'toilets',
                    'arts_centre', 'place_of_worship']
TOURISM_OPTIONS = ['attraction', 'gallery', 'museum', 'viewpoint', 'artwork', 'aquarium', 'zoo', 'theme_park']
CUISINE_OPTIONS = ['mexican', 'italian', 'thai', 'chinese', 'japanese', 'american',
    'cuban', 'spanish', 'indian', 'greek', 'korean', 'german',
    'french', 'vietnamese', 'afghan', 'pakistani', 'szechuan',
    'argentinian', 'caribbean', 'venezuelan', 'hawaiian', 'cajun',
    'new_zealand', 'peruvian', 'brazilian', 'ethiopian', 'russian',
    'jamaican', 'taiwanese', 'persian', 'nepalese', 'filipino',
    'guamanian', 'african', 'salvadoran', 'australian', 'colombian',
    'lebanese', 'tex-mex', 'mediterranean', 'middle_eastern']

# Add more if possible
# ACCESSIBILITY_OPTIONS = ['wheelchair', 'toilets', 'toilets:unisex', 'toilets:wheelchair',
#     'changing_table', 'sensory_friendly:accommodation', 'drive_through', 'air_conditioning']
ACCESSIBILITY_OPTIONS = ['wheelchair']

def randomize_coords(base_lat, base_lon):
    lat_offset = random.uniform(-0.025, 0.025)
    lon_offset = random.uniform(-0.025, 0.025)
    return {
        "lat": round(base_lat + lat_offset, 4),
        "lon": round(base_lon + lon_offset, 4)
    }

def select_multiple_options(options, min_count=1, max_count=3):
    k = random.randint(min_count, min(max_count, len(options)))
    selected = random.sample(options, k)
    return "|".join(selected)

def generate_user_preferences(count=100, max_poi=4):
    preferences = []
    
    for i in range(1, count + 1):
        location = random.choice(SAN_DIEGO_LOCATIONS)
        start_coords = randomize_coords(location['lat'], location['lon'])
        num_poi = random.randint(2, max_poi)
        time_per_poi = random.choice([0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]) # (hrs)
        
        # walking
        if num_poi > 4 and random.random() < 0.5:
            max_travel_dist = round(random.uniform(1, 3), 1) # 1-3 miles walking
            avg_travel_speed_mph = round(random.uniform(2.0, 4.0), 1)
            max_travel_time_minutes = random.choice([5, 7, 9, 11, 13, 15])
        # vehicle use
        else:
            max_travel_dist = round(random.uniform(10, 20), 1)
            avg_travel_speed_mph = random.choice([20, 30, 40, 50])
            max_travel_time_minutes = random.choice([15, 30, 45, 60])

        user_preference = {
            "id": i,
            "start_location": start_coords,
            "num_poi": num_poi,
            "time_per_poi": time_per_poi,
            "max_travel_dist": max_travel_dist,
            "avg_travel_speed_mph": avg_travel_speed_mph,
            "max_travel_time_minutes": max_travel_time_minutes,
            "amenity_type": select_multiple_options(AMENITY_OPTIONS),
            "tourism_type": select_multiple_options(TOURISM_OPTIONS),
            "cuisine": select_multiple_options(CUISINE_OPTIONS),
            "required_accessibility": select_multiple_options(ACCESSIBILITY_OPTIONS),
            "visited_ids": []
        }
        preferences.append(user_preference)
        
    return preferences

if __name__ == "__main__":
    count = 100
    max_poi = 5
    test_set = generate_user_preferences(count=count, max_poi=max_poi)
    
    filename = f"user_preferences_{count}.json"
    with open(filename, 'w') as f:
        json.dump(test_set, f, indent=2)
    print(f"Saved content to {filename}.\n")