from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict

class Coords(BaseModel):
    lat: float
    lon: float

class AccessiblePOI(BaseModel):
    id: str
    name: Optional[str] = None
    category: Optional[str] = None
    coords: Coords
    source: str = "OSM"

    # Accessibility attributes
    wheelchair: Optional[str] = None
    entrance_wheelchair: Optional[str] = None
    toilets_wheelchair: Optional[str] = None
    surface: Optional[str] = None
    tactile_paving: Optional[str] = None
    ramp: Optional[str] = None
    smoothness: Optional[str] = None
    incline: Optional[str] = None
    steps: Optional[str] = None
    elevator: Optional[str] = None

    #transit attributes
    nearest_stop_id: Optional[str] = None
    nearest_stop_name: Optional[str] = None
    distance_to_nearest_stop_m: Optional[float] = None
    routes: List[str] = Field(default_factory=list)

    # Misc. attributes
    tags: Dict[str, str] = Field(default_factory=dict)

    @field_validator("wheelchair", "entrance_wheelchair", "toilets_wheelchair", mode="before")
    @classmethod
    def norm_wheelchair_flags(cls, v):
        if v is None: return None
        v = str(v).lower().strip()
        return {"true":"yes","false":"no","unknown":"unknown"}.get(v, v)