import cv2
from ultralytics import YOLO

# Load the YOLOv11 model
coco_model = YOLO("yolo11s.pt")  # or another version of YOLOv1 (e.g., yolov11s.pt for small)

target_classes = [0]
# Open the video capture
video_capture = cv2.VideoCapture(0)  # Replace 0 with video file path if needed

while True:
    ret, frame = video_capture.read()
    if not ret:
        break

    # Apply YOLOv8 object detection
    results = coco_model(frame, conf = 0.5)[0]


    # Draw bounding boxes and labels
    for result in results.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = result

        if int(class_id) in target_classes:

            label = f'{coco_model.names[int(class_id)]} {score}'
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)


            # Display the frame
            cv2.imshow('YOLOv11 Detection', frame)

            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
"""
        x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
        label = f'{coco_model.names[int(cls)]}'
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
"""




# Release the video capture and close windows
video_capture.release()
cv2.destroyAllWindows()