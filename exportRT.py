
from ultralytics import YOLO

model = YOLO("models/best.pt")

model.export(
    format="engine",
    half=True,        # FP16 engine
    device=0,
    workspace=4       # GB VRAM dành cho TensorRT
)
