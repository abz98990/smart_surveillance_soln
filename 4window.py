import cv2
import time
import ctypes
import noti
import numpy as np
from ultralytics import YOLO

# Load the YOLOv11 model
people_model = YOLO("yolo11n.pt")    # or another version of YOLOv1 (e.g., yolov11s.pt for small)
gun_model = YOLO("./weights_gun/last.pt")
fire_model = YOLO("./weights_fire/last.pt")

# Open the video capture
video_capture = cv2.VideoCapture(0)  # Replace 0 with video file path if needed

# Get display resolution to
user32 = ctypes.windll.user32
width, height = (user32.GetSystemMetrics(0) * 99) // 100, (user32.GetSystemMetrics(1) * 90) // 100

# Set an Alert variable
alert = False

while True:
    ret, frame = video_capture.read()
    if not ret:
        break

    pd_frame = gd_frame = fd_frame = frame

    #create a blank canvas for pasting video frames
    canvas = np.zeros((height, width, 3), np.uint8)

    # Show raw camera feed
    raw_frame = cv2.resize(frame, (width // 2, height // 2))
    canvas[:height//2, :width//2] = raw_frame
    #cv2.imshow("Original Feed", canvas)

    # Apply YOLOv11 object detection for detecting people
    people_results = people_model(pd_frame, conf = 0.4)[0]

    # Draw bounding boxes and labels
    for *xyxy, conf1, class_id1 in people_results.boxes.data.tolist():
        if int(class_id1) == 0:
            x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
            label = '{} {}%'.format(people_model.names[int(class_id1)], int(conf1 * 100))
            cv2.rectangle(pd_frame, (x1, y1), (x2, y2), (0, 225, 0), 3)
            cv2.putText(pd_frame, "People", (0, 0), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 215, 0), 2)
            cv2.putText(pd_frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 215, 0), 2)
    pd_frame = cv2.resize(pd_frame, (width // 2, height // 2))
    canvas[:height // 2, width//2:] = pd_frame


    # Apply YOLOv11 object detection for detecting gun
    gun_results = gun_model(gd_frame, conf = 0.4)[0]

    # Draw bounding boxes and labels
    for *abab, conf2, class_id2 in gun_results.boxes.data.tolist():
        a1, b1, a2, b2 = int(abab[0]), int(abab[1]), int(abab[2]), int(abab[3])
        label2 = '{} {}%'.format(gun_model.names[int(class_id2)], int(conf2 * 100))
        cv2.rectangle(gd_frame, (a1, b1), (a2, b2), (0, 0, 225), 3)
        cv2.putText(gd_frame, label2, (a1, b1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 215), 2)
        alert = True

    gd_frame = cv2.resize(gd_frame, (width // 2, height // 2))
    canvas[height // 2:, :width // 2] = gd_frame

    # Apply YOLOv11 object detection for detecting fire
    fire_results = fire_model(fd_frame)[0]

    # Draw bounding boxes and labels
    for *jkjk, conf3, class_id3 in fire_results.boxes.data.tolist():
        j1, k1, j2, k2 = int(jkjk[0]), int(jkjk[1]), int(jkjk[2]), int(jkjk[3])
        label3 = '{} {}%'.format(("smoke", "fire")[int(class_id3) == 0], int(conf3 * 100))
        cv2.rectangle(fd_frame, (j1, k1), (j2, k2), (225, 0, 0), 3)
        cv2.putText(fd_frame, label3, (j1, k1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (215, 0, 0), 2)

    fd_frame = cv2.resize(fd_frame, (width // 2, height // 2))
    canvas[height // 2:, width // 2:] = fd_frame

    # Display the frame
    cv2.imshow('YOLOv11 Detection', canvas)

    # Press 'q' to quit
    key = cv2.waitKey(1)
    if key == ord('q'):
        break
    elif key == ord('r'):
        cv2.imwrite('./imgs/data_{}.jpg'.format(time.time()), frame)
        print('saving an image')

    # Generate alerts
    if alert:
        noti.notif()
    alert = False

# Release the video capture and close windows
video_capture.release()
cv2.destroyAllWindows()