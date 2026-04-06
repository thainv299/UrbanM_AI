import fiftyone as fo
import fiftyone.zoo as foz
import os

all_classes = ["person", "bicycle", "car", "motorcycle", "bus", "truck"]
counts = {"train": 3000, "validation": 500}
EXPORT_DIR = "Dataset/COCO_Balanced"

for split, limit in counts.items():
    print(f"\n=== BẮT ĐẦU TẢI TẬP {split.upper()} ===")

    dataset_name = f"Merged_Traffic_{split}"
    if fo.dataset_exists(dataset_name):
        fo.delete_dataset(dataset_name)
    merged_dataset = fo.Dataset(dataset_name)

    for cls in all_classes:
        temp_name = f"temp_coco_{cls}_{split}"
        if fo.dataset_exists(temp_name):
            fo.delete_dataset(temp_name)
            
        ds = foz.load_zoo_dataset(
            "coco-2017", split=split, label_types=["detections"],
            classes=[cls], max_samples=limit,
            dataset_name=temp_name 
        )
        print(f"-> {cls} ({split}): Đã tải {len(ds)} ảnh.")

        # Lọc duplicate
        existing_filepaths = set(merged_dataset.values("filepath")) if len(merged_dataset) > 0 else set()
        new_samples = [s for s in ds if s.filepath not in existing_filepaths]
        print(f"   -> Thêm {len(new_samples)} ảnh mới (bỏ qua {len(ds) - len(new_samples)} duplicate).")
        merged_dataset.add_samples(new_samples)
        ds.delete()

    print(f"\nTổng ảnh {split}: {len(merged_dataset)}")

    view = merged_dataset.filter_labels("ground_truth", fo.ViewField("label").is_in(all_classes))
    view.export(
        export_dir=EXPORT_DIR,
        dataset_type=fo.types.YOLOv5Dataset,
        split="train" if split == "train" else "val",
        classes=all_classes,
    )

    # Nắn ID sau khi export
    lbl_path = os.path.join(EXPORT_DIR, "labels", "train" if split == "train" else "val")
    if os.path.exists(lbl_path):
        files = [f for f in os.listdir(lbl_path) if f.endswith('.txt')]
        print(f"Đang nắn ID cho {len(files)} file nhãn...")
        for f in files:
            p = os.path.join(lbl_path, f)
            with open(p, 'r') as file:
                lines = file.readlines()
            with open(p, 'w') as file:
                for line in lines:
                    parts = line.split()
                    if not parts:
                        continue
                    c = int(parts[0])
                    if c == 4: c = 5
                    elif c == 5: c = 7
                    file.write(f"{c} " + " ".join(parts[1:]) + "\n")

    merged_dataset.delete()

print("\nHoàn tất tải và nắn ID!")