from abc import ABC, abstractmethod
from typing import Any, Callable, Dict


class DetectionInterface(ABC):
    @abstractmethod
    def process_video(
        self,
        input_path: str,
        output_path: str,
        settings: Dict[str, Any],
        progress_callback: Callable[[Dict[str, Any]], None],
    ) -> Dict[str, Any]:
        """Xử lý video và gọi progress_callback mỗi khi cập nhật"""
        pass
