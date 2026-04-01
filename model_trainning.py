from ultralytics import YOLO

def main():
    model = YOLO("models/yolo26m.pt")

    results = model.train(
        data="E:/DATN_code/Dataset/COCO_Balanced/dataset.yaml",
        epochs=100,
        imgsz=640,
        batch=8,         
        device=0,
        patience=20,
        project="Traffic_AI",
        name="Medium_Run1",

        workers=4,        
        cache=True,       

        lr0=0.001,
        lrf=0.01,
        warmup_epochs=3,
        weight_decay=0.0005,

        mosaic=1.0,
        close_mosaic=10,
        mixup=0.1,
        degrees=10.0,
        hsv_s=0.5,
        hsv_v=0.3,
        fliplr=0.5,
        flipud=0.0,
    )

if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    main()