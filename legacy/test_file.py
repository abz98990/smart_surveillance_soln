"""Single-image inference against the handgun detector.

Archived prototype - superseded by the surveillance/ package. Kept for the
development history; run `python run.py` from the project root for the
actual system. Defects found in review have been corrected so nothing in
the repository is broken, but these scripts are not maintained.
"""

from ultralytics import YOLO

model = YOLO("../weights_gun/best.pt")

results = model("samples/img_6.png", conf=0.4)

# results[0].probs is always None for a detection model - it only carries a
# value for classification models. Boxes are what this model produces.
print("classes:", results[0].names)
for x1, y1, x2, y2, score, class_id in results[0].boxes.data.tolist():
    print("  {} {:.0%} at ({:.0f}, {:.0f}, {:.0f}, {:.0f})".format(
        results[0].names[int(class_id)], score, x1, y1, x2, y2))

results[0].show()
