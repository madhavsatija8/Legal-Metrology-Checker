"""
Run this INSIDE the backend container to see exactly where the OCR
pipeline diverges from the expected clean output.
"""
import sys
sys.path.insert(0, "/app")

from app.ocr.preprocessing import preprocess_image
from app.ocr.extraction import run_ocr, group_into_lines
from app.ocr.field_classifier import classify_fields
import cv2

IMG_PATH = "/app/app/storage/be8d2e3f-99c2-4100-93cb-4a8e343e9717.png"

raw = cv2.imread(IMG_PATH)
print(f"RAW image shape (h, w, c): {raw.shape}")

processed = preprocess_image(IMG_PATH)
print(f"PREPROCESSED image shape: {processed.shape}")
cv2.imwrite("/app/app/storage/_debug_preprocessed.png", processed)
print("Saved preprocessed image -- pull it out and look at it.")

blocks = run_ocr(processed)
print(f"\n{len(blocks)} word-level blocks detected. First 15:")
for b in blocks[:15]:
    print(f"  text={b.text!r:20} left={b.left:4} top={b.top:4} w={b.width:4} h={b.height:4} conf={b.confidence:.1f}")

lines = group_into_lines(blocks)
print(f"\n{len(lines)} grouped lines:")
for l in lines:
    print(f"  {l.text!r:55} bbox=({l.left},{l.top},{l.right},{l.bottom}) avg_h={l.avg_word_height_px:.1f}")

fields = classify_fields(lines)
print("\nretail_sale_price matched:", fields["retail_sale_price"]["matched"])
print("manufacturer matched:", fields["manufacturer_packer_importer_details"]["matched"])
