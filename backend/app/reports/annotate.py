"""
Step 7: produces the "annotated image" evidence attachment the reporting
module needs. Draws a box around the source line of every field tied to
an unresolved violation, using the per-field `bbox` the OCR field
classifier now carries (see ocr/field_classifier.py's `_bbox` helper).

Deliberately only boxes *violated* fields, not every matched one — the
report is evidence for what an inspector needs to act on, not a general
OCR debug overlay (that already exists in the Step 6 frontend's
extracted-declarations panel).
"""
import os
import re
import tempfile

from PIL import Image, ImageDraw, ImageFont

# Matches the field name the compliance engine (compliance/engine.py)
# quotes in its font-height violation descriptions, e.g.
# "'net_quantity' letter height is approximately 0.38mm...".
_QUOTED_FIELD_RE = re.compile(r"'([a-z_]+)'")

_BOX_COLOR = (200, 30, 30)
_BOX_WIDTH = 3
_LABEL_PAD = 4


def _violated_field_names(violations) -> set[str]:
    names: set[str] = set()
    for v in violations:
        if v.is_resolved:
            continue
        m = _QUOTED_FIELD_RE.search(v.description)
        if m:
            names.add(m.group(1))
        elif v.rule_id.endswith("-format"):
            # MRP wording-format violations don't quote a field name (see
            # compliance/engine.py's format_check branch) but always refer
            # to the MRP declaration itself.
            names.add("retail_sale_price")
    return names


def _load_font():
    # DejaVuSans ships with most Linux Pillow installs; fall back to the
    # bitmap default rather than failing the whole report if it's absent.
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
    except OSError:
        return ImageFont.load_default()


def annotate_label_image(image_path: str | None, fields: dict, violations: list) -> str | None:
    """Returns a path to the annotated image, the original path unchanged
    (nothing to flag), or None if there's no image to work with at all."""
    if not image_path or not os.path.exists(image_path):
        return None

    flagged = _violated_field_names(violations)
    if not flagged:
        return image_path

    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = _load_font()

    boxed_any = False
    for name in flagged:
        entry = fields.get(name)
        bbox = entry.get("bbox") if isinstance(entry, dict) else None
        if not bbox:
            continue  # e.g. a missing-declaration violation has no source line to box
        left, top, right, bottom = bbox
        box = (left - _LABEL_PAD, top - _LABEL_PAD, right + _LABEL_PAD, bottom + _LABEL_PAD)
        draw.rectangle(box, outline=_BOX_COLOR, width=_BOX_WIDTH)
        label_y = max(0, top - _LABEL_PAD - 20)
        draw.text((left - _LABEL_PAD, label_y), name.replace("_", " "), fill=_BOX_COLOR, font=font)
        boxed_any = True

    if not boxed_any:
        return image_path

    out_dir = tempfile.mkdtemp(prefix="lmc_annotated_")
    out_path = os.path.join(out_dir, f"annotated_{os.path.basename(image_path)}")
    img.save(out_path)
    return out_path
