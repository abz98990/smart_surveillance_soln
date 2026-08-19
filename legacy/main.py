"""Three detectors drawn onto one window.

Archived prototype - superseded by the surveillance/ package. Kept for the
development history; run `python run.py` from the project root for the
actual system. Defects found in review have been corrected so nothing in
the repository is broken, but these scripts are not maintained.
"""

import cv2
from ultralytics import YOLO

# Load the YOLOv11 model
people_model = YOLO("./weights_people/best.pt")    # or another version of YOLOv1 (e.g., yolov11s.pt for small)
gun_model = YOLO("./weights_gun/best.pt")
fire_model = YOLO("./weights_fire/best.pt")


# Open the video capture
video_capture = cv2.VideoCapture(0)  # Replace 0 with video file path if needed

while True:
    ret, frame = video_capture.read()
    if not ret:
        break
    # Show raw camera feed
    cv2.imshow("Capture Window", frame)

    # Apply YOLOv11 object detection for detecting people
    people_results = people_model(frame, conf = 0.4)[0]

    # Draw bounding boxes and labels
    for *xyxy, conf1, class_id1 in people_results.boxes.data.tolist():
        if int(class_id1) == 0:
            x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
            label = f'{people_model.names[int(class_id1)]} {int(conf1 * 100)}%'
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 225, 0), 3)
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 225, 0), 2)


    # Apply YOLOv11 object detection for detecting gun
    gun_results = gun_model(frame, conf = 0.4)[0]

    # Draw bounding boxes and labels
    for *abab, conf2, class_id2 in gun_results.boxes.data.tolist():
        a1, b1, a2, b2 = int(abab[0]), int(abab[1]), int(abab[2]), int(abab[3])
        label2 = f'{gun_model.names[int(class_id2)]} {int(conf2 * 100)}%'
        cv2.rectangle(frame, (a1, b1), (a2, b2), (0, 0, 225), 3)
        cv2.putText(frame, label2, (a1, b1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 225), 2)


    # Apply YOLOv11 object detection for detecting fire
    fire_results = fire_model(frame, conf=0.5)[0]

    # Draw bounding boxes and labels
    for *jkjk, conf3, class_id3 in fire_results.boxes.data.tolist():
        j1, k1, j2, k2 = int(jkjk[0]), int(jkjk[1]), int(jkjk[2]), int(jkjk[3])
        label3 = f'{fire_model.names[int(class_id3)]} {int(conf3 * 100)}%'
        cv2.rectangle(frame, (j1, k1), (j2, k2), (225, 0, 0), 3)
        cv2.putText(frame, label3, (j1, k1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (225, 0, 0), 2)

    # Display the frame
    cv2.imshow('YOLOv11 Detection', frame)

    # Press 'q' to quit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the video capture and close windows
video_capture.release()
cv2.destroyAllWindows()