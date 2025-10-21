from time import ctime
import ctypes
from ultralytics import YOLO
import cv2, noti
import numpy as np
import datetime

#model = YOLO("./weights/best.pt")
user32 = ctypes.windll.user32

width, height = (user32.GetSystemMetrics(0) * 99) // 100, (user32.GetSystemMetrics(1) * 90) // 100

cap = cv2.VideoCapture(0)
while True:
    ret, frame = cap.read()

    #canvas = np.zeros((height, width, 3))
    #print(frame.shape)
    cv2.imshow("Feed", frame)
    noti.notif()

    key = cv2.waitKey(1)
    if key == ord('q'):
        break
    elif key == ord('r'):
        cv2.imwrite('./imgs/data_{}.jpg'.format(datetime.datetime.now()), frame)
        print('saving an image')

cap.release()
cv2.destroyAllWindows()