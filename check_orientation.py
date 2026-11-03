import sys
sys.path.insert(0, "/app")

import cv2
import numpy as np
from app.ocr.preprocessing import preprocess_image

IMG_PATH = "/app/app/storage/be8d2e3f-99c2-4100-93cb-4a8e343e9717.png"
processed = preprocess_image(IMG_PATH)

print("shape (h, w):", processed.shape)

thresh = cv2.threshold(processed, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
row_ink = thresh.sum(axis=1)
col_ink = thresh.sum(axis=0)

print("row-ink std (variation across rows):", row_ink.std())
print("col-ink std (variation across columns):", col_ink.std())
print("-> if row-ink std >> col-ink std: text is horizontal (normal)")
print("-> if col-ink std >> row-ink std: text is vertical (rotated ~90deg)")
