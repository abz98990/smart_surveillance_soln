
from ultralytics import YOLO
import cv2, datetime

model = YOLO("./weights_gun/last.pt")

results = model("img_6.png")

names = results[0].names

probs = results[0].probs
results[0].show()

print(names)
print(probs)
"""
import ctypes
user32 = ctypes.windll.user32
print(user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
"""