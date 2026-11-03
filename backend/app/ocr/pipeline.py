"""
Orchestrates the full pipeline for a single scan: preprocess the image,
run OCR, classify fields, and package everything the compliance engine
(Step 5) and the inspector review UI (Step 6) will need.
"""
from .extraction import group_into_lines, run_ocr
from .field_classifier import classify_fields
from .preprocessing import preprocess_image


def process_label_image(image_path: str, lang: str = "eng+hin", binarize: bool = True) -> dict:
    processed = preprocess_image(image_path, binarize=binarize)
    blocks = run_ocr(processed, lang=lang)
    lines = group_into_lines(blocks)
    fields = classify_fields(lines)

    confidences = [b.confidence for b in blocks]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        # Plain text for the inspector review UI (Step 6) and for logging/
        # debugging — the pixel bounding boxes that back each matched
        # field are carried separately inside `fields.*.pixel_height`.
        "raw_lines": [line.text for line in lines],
        "word_count": len(blocks),
        "average_ocr_confidence": round(avg_confidence, 1),
        "fields": fields,
    }
