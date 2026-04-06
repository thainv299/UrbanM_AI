from typing import Any, Dict

from domain.repositories.camera_repository import CameraRepository
from domain.repositories.user_repository import UserRepository


class DashboardUseCases:
    def __init__(self, user_repo: UserRepository, camera_repo: CameraRepository):
        self.user_repo = user_repo
        self.camera_repo = camera_repo

    def get_dashboard_stats(self) -> Dict[str, Any]:
        users = self.user_repo.list_all()
        cameras = self.camera_repo.list_all()
        
        feature_counts = self.camera_repo.get_feature_counts()
        recent_cameras = self.camera_repo.get_recent(limit=6)

        return {
            "user_count": len(users),
            "camera_count": len(cameras),
            "active_cameras": self.camera_repo.get_active_count(),
            "congestion_enabled": feature_counts.get("congestion", 0),
            "illegal_parking_enabled": feature_counts.get("illegal_parking", 0),
            "license_plate_enabled": feature_counts.get("license_plate", 0),
            "recent_cameras": [cam.to_dict() for cam in recent_cameras],
        }
