from ultralytics import YOLO
import cv2

model = YOLO("./weights/last.pt")

results = model("img_1.png", conf=0.5)

names = results[0].names

probs = results[0].probs
results[0].show()

print(names)
print(probs)