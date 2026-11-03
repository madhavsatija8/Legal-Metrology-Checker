import sys
sys.path.insert(0, "/app")

import cv2
import numpy as np
from app.ocr.preprocessing import _enhance_contrast, _denoise

IMG_PATH = "/app/app/storage/be8d2e3f-99c2-4100-93cb-4a8e343e9717.png"
img = cv2.imread(IMG_PATH)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
gray = _enhance_contrast(gray)
gray = _denoise(gray)

thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
ys, xs = np.where(thresh > 0)
coords = np.column_stack((xs, ys))
print("num foreground pixels:", coords.shape[0])

rect = cv2.minAreaRect(coords)
print("minAreaRect (center, size, angle):", rect)
angle = rect[-1]
print("raw angle:", angle)

corrected = -(90 + angle) if angle < -45 else -angle
print("corrected angle used for rotation:", corrected)
print("would skip rotation (abs<0.5)?", abs(corrected) < 0.5)
print("cv2 version in this container:", cv2.__version__)
