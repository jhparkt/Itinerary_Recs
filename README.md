# Dataset Overview & Collection Metadata

This project collects **OpenStreetMap (OSM)** and **GTFS (General Transit Feed Specification)** data to support a generative AI system for personalized, accessible trip planning in San Diego.  
The collected datasets serve as foundational inputs for downstream normalization, enrichment, and model training.

---

## OpenStreetMap (OSM) — Places of Interest (POIs)

**Description:**  
OpenStreetMap (OSM) is a global open dataset containing crowdsourced map features, including landmarks, transportation networks, public amenities, and accessibility metadata.

**Purpose:**  
To provide a high-quality catalog of _places of interest_ (POIs) — such as museums, parks, beaches, restaurants, and attractions — for itinerary generation.

**Data Source:**

- **Provider:** [OpenStreetMap](https://www.openstreetmap.org)
- **API:** [Overpass API](https://overpass-api.de)
- **Collection Method:** Overpass query using a city boundary (San Diego) and curated category presets

**Core Categories Fetched:**
| Category | OSM Tags |
|-----------|-----------|
| Museums | `tourism=museum` |
| Parks | `leisure=park` |
| Beaches | `natural=beach` |
| Food & Cafés | `amenity=restaurant`, `amenity=cafe`, `amenity=fast_food` |
| Attractions | `tourism=attraction`, `zoo`, `gallery`, `aquarium`, `theme_park` |
| Historic sites | `historic=*` |

**Accessibility-Related Tags (if present):**

- `wheelchair` (`yes`, `limited`, `no`)
- `entrance:wheelchair`, `toilets:wheelchair`
- `surface`, `tactile_paving`, `kerb`, `ramp`

**File Metadata:**
| Field | Value |
|--------|--------|
| Output Path | `raw_data/osm/raw_osm.json` |
| Format | JSON (Overpass API native) |
| Size | ~10–30 MB (city-level, varies by preset) |
| Refresh Frequency | Manual (recommend weekly) |
| Script | `fetch_osm_raw.py` |
| Inputs | `--city`, `--preset`, `--out` |
| Outputs | Raw JSON with all nodes/ways/relations within city boundary |

**Sample Record:**

```json
{
  "id": 123456789,
  "type": "node",
  "lat": 32.731,
  "lon": -117.149,
  "tags": {
    "name": "Balboa Park",
    "tourism": "attraction",
    "wheelchair": "yes",
    "opening_hours": "Mo-Su 09:00-17:00"
  }
}
```

# GTFS Dataset Documentation

This document describes the **General Transit Feed Specification (GTFS)** dataset used in the Trip Planning Generative AI project.  
The GTFS feed provides structured information on public transit stops, routes, and schedules for **San Diego Metropolitan Transit System (MTS)** and is one of the two core datasets, alongside **OpenStreetMap (OSM)**.

---

## Overview

**Name:** General Transit Feed Specification (GTFS)  
**Provider:** [San Diego Metropolitan Transit System (MTS)](https://www.sdmts.com/business-center/app-developers)  
**Feed URL:** [https://www.sdmts.com/google_transit_files/google_transit.zip](https://www.sdmts.com/google_transit_files/google_transit.zip)  
**Format:** Static GTFS ZIP (CSV tables)  
**License:** Publicly available for non-commercial use  
**Collection Script:** `collector_GTFS.py`

---

## 🧭 Purpose

The GTFS dataset allows the system to understand **mobility, accessibility, and connectivity** between locations in the city.  
It provides all the information necessary to:

- Map **transit stops** near OSM points of interest (POIs)
- Compute **route coverage**, **transit type**, and **frequency**
- Integrate **accessibility signals** (e.g., wheelchair boarding) for inclusive trip planning

---

## 🧩 Data Structure

Each GTFS feed is a ZIP file containing multiple CSV tables, each describing a part of the transit system.

| File             | Description                              | Key Fields                                                      | Accessibility Attributes |
| ---------------- | ---------------------------------------- | --------------------------------------------------------------- | ------------------------ |
| `stops.txt`      | Transit stop coordinates and names       | `stop_id`, `stop_name`, `stop_lat`, `stop_lon`                  | `wheelchair_boarding`    |
| `routes.txt`     | Bus, trolley, or other route details     | `route_id`, `route_short_name`, `route_long_name`, `route_type` | —                        |
| `trips.txt`      | Trips (route + vehicle info)             | `trip_id`, `route_id`, `wheelchair_accessible`                  | `wheelchair_accessible`  |
| `stop_times.txt` | Stop sequences for trips                 | `trip_id`, `stop_id`, `stop_sequence`, `arrival_time`           | —                        |
| `calendar.txt`   | Service days (weekday/weekend schedules) | `service_id`, `monday`–`sunday`, `start_date`, `end_date`       | —                        |
| `agency.txt`     | Agency-level metadata                    | `agency_name`, `agency_url`, `agency_timezone`                  | —                        |

---

## Accessibility Fields

GTFS defines explicit accessibility indicators at both stop and trip levels:

| Field                   | Source File | Type    | Meaning                                         |
| ----------------------- | ----------- | ------- | ----------------------------------------------- |
| `wheelchair_boarding`   | `stops.txt` | integer | 0 = unknown, 1 = accessible, 2 = not accessible |
| `wheelchair_accessible` | `trips.txt` | integer | 0 = unknown, 1 = accessible, 2 = not accessible |

These allow the model to identify **accessible routes and stops** when generating itineraries.

---

## File Metadata

| Field                 | Value                                                          |
| --------------------- | -------------------------------------------------------------- |
| **Output Directory**  | `raw_data/gtfs/`                                               |
| **Downloaded File**   | `google_transit.zip`                                           |
| **Extracted Files**   | `stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`, etc. |
| **Format**            | CSV (UTF-8)                                                    |
| **Average Size**      | ~5–15 MB                                                       |
| **Refresh Frequency** | Monthly (based on MTS updates)                                 |
| **Collector Script**  | `fetch_gtfs_raw.py`                                            |
| **Input Argument**    | `--outdir ./raw_data/gtfs`                                     |
| **Outputs**           | Extracted CSVs verified by structure check                     |

---
