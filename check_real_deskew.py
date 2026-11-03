import sys
sys.path.insert(0, "/app")

import cv2
import numpy as np
from app.ocr.preprocessing import preprocess_image, _deskew, _enhance_contrast, _denoise

IMG_PATH = "/app/app/storage/be8d2e3f-99c2-4100-93cb-4a8e343e9717.png"
img = cv2.imread(IMG_PATH)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
gray = _enhance_contrast(gray)
gray = _denoise(gray)

before = gray.copy()
after = _deskew(gray)

# If _deskew returned the exact same array unchanged, no rotation happened.
identical = np.array_equal(before, after)
print("deskew changed the image:", not identical)

# Also run full pipeline + OCR word check, same as the earlier diagnostic.
import pytesseract
processed = preprocess_image(IMG_PATH)
data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)
for i, t in enumerate(data["text"]):
    if "efined" in t:
        print(f"'Refined' box: left={data['left'][i]} top={data['top'][i]} w={data['width'][i]} h={data['height'][i]}")
        break
