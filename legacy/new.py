"""Single-image inference against the face demonstrator.

Archived prototype - superseded by the surveillance/ package. Kept for the
development history; run `python run.py` from the project root for the
actual system. Defects found in review have been corrected so nothing in
the repository is broken, but these scripts are not maintained.
"""

from ultralytics import YOLO

# The original pointed at ./weights/last.pt, a directory that does not exist.
model = YOLO("../new/best.pt")

results = model("samples/Henry Cavill_14.jpg", conf=0.5)

print("classes:", results[0].names)
for x1, y1, x2, y2, score, class_id in results[0].boxes.data.tolist():
    print("  {} {:.0%} at ({:.0f}, {:.0f}, {:.0f}, {:.0f})".format(
        results[0].names[int(class_id)], score, x1, y1, x2, y2))

results[0].show()
