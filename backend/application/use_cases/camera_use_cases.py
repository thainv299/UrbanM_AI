from typing import Any, Dict, List

from core.errors import AlreadyExistsError, NotFoundError, ValidationError
from domain.entities.camera import Camera
from domain.repositories.camera_repository import CameraRepository


class CameraUseCases:
    def __init__(self, camera_repo: CameraRepository):
        self.camera_repo = camera_repo

    def list_cameras(self) -> List[Camera]:
        return self.camera_repo.list_all()

    def get_camera(self, camera_id: int) -> Camera:
        camera = self.camera_repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Không tìm thấy camera.")
        return camera

    def _validate_payload(self, payload: Dict[str, Any]) -> Camera:
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValidationError("Tên camera không được để trống.")

        is_active = payload.get("is_active")
        is_active = True if is_active is None else str(is_active).strip().lower() in {"1", "true", "yes", "on"}

        return Camera(
            id=None,
            name=name,
            stream_source=str(payload.get("stream_source", "")).strip(),
            description=str(payload.get("description", "")).strip(),
            roi_points=payload.get("roi_points"), # raw unparsed if dict, wait, it should be the raw list
            no_parking_points=payload.get("no_parking_points"),
            enable_congestion=payload.get("enable_congestion", True),
            enable_illegal_parking=payload.get("enable_illegal_parking", True),
            enable_license_plate=payload.get("enable_license_plate", True),
            is_active=is_active
        )
        
    def create_camera(self, payload: Dict[str, Any]) -> Camera:
        camera = self._validate_payload(payload)
        for existing in self.camera_repo.list_all():
            if existing.name == camera.name:
                raise AlreadyExistsError("Tên camera đã tồn tại.")
        return self.camera_repo.create(camera)

    def update_camera(self, camera_id: int, payload: Dict[str, Any]) -> Camera:
        updates = self._validate_payload(payload)
        updates.id = camera_id

        existing = self.get_camera(camera_id)
        for other in self.camera_repo.list_all():
            if other.name == updates.name and other.id != camera_id:
                raise AlreadyExistsError("Tên camera đã tồn tại.")

        updated = self.camera_repo.update(updates)
        if not updated:
            raise NotFoundError("Không tìm thấy camera.")
        return updated

    def delete_camera(self, camera_id: int) -> bool:
        if not self.camera_repo.delete(camera_id):
            raise NotFoundError("Không tìm thấy camera.")
        return True
