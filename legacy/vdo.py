"""Camera smoke test: open a device and save frames on demand.

Archived prototype - superseded by the surveillance/ package. Kept for the
development history; run `python run.py` from the project root for the
actual system. Defects found in review have been corrected so nothing in
the repository is broken, but these scripts are not maintained.
"""

import datetime
import os

import cv2

OUT_DIR = "../imgs"

os.makedirs(OUT_DIR, exist_ok=True)
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    cv2.imshow("Feed", frame)

    # The original raised a notification on every frame, which produced a
    # continuous stream of toasts and pinned the loop at roughly 1 fps.
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    elif key == ord("r"):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = os.path.join(OUT_DIR, "data_{}.jpg".format(stamp))
        cv2.imwrite(path, frame)
        print("saved", path)

cap.release()
cv2.destroyAllWindows()
