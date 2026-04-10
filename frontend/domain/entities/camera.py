from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Camera:
    id: Optional[int]
    name: str
    stream_source: str = ""
    description: str = ""
    roi_points: Optional[List[List[int]]] = None
    no_parking_points: Optional[List[List[int]]] = None
    enable_congestion: bool = True
    enable_illegal_parking: bool = True
    enable_license_plate: bool = True
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "stream_source": self.stream_source,
            "description": self.description,
            "roi_points": self.roi_points,
            "no_parking_points": self.no_parking_points,
            "enable_congestion": self.enable_congestion,
            "enable_illegal_parking": self.enable_illegal_parking,
            "enable_license_plate": self.enable_license_plate,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
