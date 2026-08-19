"""Stock COCO person detection, used to sanity-check the pipeline.

Archived prototype - superseded by the surveillance/ package. Kept for the
development history; run `python run.py` from the project root for the
actual system. Defects found in review have been corrected so nothing in
the repository is broken, but these scripts are not maintained.
"""

import cv2
from ultralytics import YOLO

# Stock COCO weights; class 0 is "person".
coco_model = YOLO("../yolo11s.pt")
TARGET_CLASSES = {0}

video_capture = cv2.VideoCapture(0)

while True:
    ret, frame = video_capture.read()
    if not ret:
        break

    results = coco_model(frame, conf=0.5, verbose=False)[0]

    for x1, y1, x2, y2, score, class_id in results.boxes.data.tolist():
        if int(class_id) not in TARGET_CLASSES:
            continue
        # cv2.rectangle needs integer points; passing the raw floats straight
        # from tolist() raises TypeError on the very first detection.
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        label = "{} {}%".format(coco_model.names[int(class_id)], int(score * 100))
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, label, (x1, max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Display and key handling belong in the frame loop, not the detection
    # loop. Inside it the window froze whenever nobody was in shot, and the
    # 'q' handler only ever broke out of the inner loop.
    cv2.imshow("YOLO11 person detection", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

video_capture.release()
cv2.destroyAllWindows()
