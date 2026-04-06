import cv2
import json

VIDEO_OR_IMAGE = r"D:/video/parking_video2.mp4"  # hoặc ảnh .jpg/.png
OUT_JSON = r"configs/zones/school_gate_01.json"

points = []

def on_mouse(event, x, y, flags, param):
    global points
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append([x, y])
        print([x, y])

cap = cv2.VideoCapture(VIDEO_OR_IMAGE)
ok, frame = cap.read()
cap.release()

if not ok:
    raise RuntimeError("Không đọc được frame. Hãy đổi VIDEO_OR_IMAGE sang ảnh hoặc video hợp lệ.")

cv2.namedWindow("Draw Zone")
cv2.setMouseCallback("Draw Zone", on_mouse)

while True:
    img = frame.copy()

    # vẽ các điểm đã chọn
    for p in points:
        cv2.circle(img, (p[0], p[1]), 5, (0, 255, 255), -1)

    # vẽ polygon nếu >= 2 điểm
    if len(points) >= 2:
        for i in range(len(points) - 1):
            cv2.line(img, tuple(points[i]), tuple(points[i + 1]), (0, 0, 255), 2)

    # đóng polygon nếu nhấn C
    cv2.putText(img, "Left click: add point | C: close | S: save | R: reset | ESC: quit",
                (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

    cv2.imshow("Draw Zone", img)
    key = cv2.waitKey(10) & 0xFF

    if key == 27:  # ESC
        break
    elif key in (ord('r'), ord('R')):
        points = []
        print("Reset points")
    elif key in (ord('s'), ord('S')):
        data = {"name": "no_park_zone", "points": points}
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Saved to", OUT_JSON)
    elif key in (ord('c'), ord('C')):
        # chỉ là thao tác “đóng” khi nhìn, file vẫn lưu danh sách điểm
        print("Close polygon (visual)")

cv2.destroyAllWindows()