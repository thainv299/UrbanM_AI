
from ultralytics import YOLO
model = YOLO("models/best.pt")
model.export(
    format="engine",
    half=True,        
    device=0,
    workspace=4       
)

