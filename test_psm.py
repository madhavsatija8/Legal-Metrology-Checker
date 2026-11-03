import sys
sys.path.insert(0, "/app")

import pytesseract
from app.ocr.preprocessing import preprocess_image

IMG_PATH = "/app/app/storage/be8d2e3f-99c2-4100-93cb-4a8e343e9717.png"
processed = preprocess_image(IMG_PATH)

for psm in [None, 3, 4, 6, 11, 12]:
    config = "" if psm is None else f"--psm {psm}"
    data = pytesseract.image_to_data(processed, config=config, output_type=pytesseract.Output.DICT)
    found = None
    for i, t in enumerate(data["text"]):
        if "efined" in t or "Refined" in t:
            found = (t, data["left"][i], data["top"][i], data["width"][i], data["height"][i])
            break
    label = f"psm={psm if psm is not None else chr(39)}default{chr(39)}"
    print(f"{label:15} -> Refined box: {found}")
