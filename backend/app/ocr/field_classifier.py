"""
Field classification step. Takes OCR'd lines (with their pixel bounding
boxes — see extraction.Line) and maps them to the mandatory declaration
categories from rules/legal_metrology_rules.json (field names there must
stay in sync with the keys used here).

Every matched field also carries `pixel_height` (the average glyph
height of the line it was found on). That's the raw ingredient the
readability/font-size module (Step 5) needs to convert to millimetres
and compare against the rule config's slab thresholds — this module
does not do that conversion itself, since it needs either a reference
object in frame or a manually entered package dimension to know the
image's pixels-per-mm ratio, which is out of scope for OCR extraction.

Honest scope note: structured fields (net quantity, MRP, dates) have a
predictable shape, so regex works reasonably well. Free-text fields
(manufacturer name/address, consumer care) vary a lot by manufacturer
and are only approximated here with keyword-anchored heuristics — they
will need a trained NER model to get materially more accurate, and
until then every match here should be treated as "candidate, needs
inspector confirmation" rather than ground truth. `generic_name` isn't
attempted at all yet: reliably identifying "what this product actually
is" from label text alone needs a product-category classifier, which
is future work, not a regex.
"""
import re

from .extraction import Line

# --- regex patterns for structured fields ---

_QUANTITY_UNIT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(kg|g|gm|gram|grams|mg|ml|l|lt|litre|liter|ltrs?)\b",
    re.IGNORECASE,
)
_NET_KEYWORD_RE = re.compile(r"\bnet\s*(wt|weight|qty|quantity)\b", re.IGNORECASE)

_MRP_KEYWORD_RE = re.compile(r"\bm\.?\s?r\.?\s?p\b|\bmaximum\s+retail\s+price\b", re.IGNORECASE)
_MRP_AMOUNT_RE = re.compile(r"(?:rs\.?|inr|₹)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
_INCLUSIVE_TAXES_RE = re.compile(r"incl(?:usive|\.)?\s+of\s+all\s+taxes|incl\.?\s+of\s+taxes", re.IGNORECASE)

_DATE_KEYWORD_RE = re.compile(
    r"\b(mfg|mfd|manufactur\w*|pkd|packed|packing|best\s+before|use\s+by|expiry|exp)\b",
    re.IGNORECASE,
)
_MONTH_YEAR_NUMERIC_RE = re.compile(r"\b(0[1-9]|1[0-2])[\/\-.](\d{2}|\d{4})\b")
_MONTH_NAME_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4}|\d{2})\b",
    re.IGNORECASE,
)

_CONSUMER_CARE_KEYWORD_RE = re.compile(
    r"consumer\s+care|customer\s+care|helpline|toll\s*free|for\s+(?:any\s+)?complaints?", re.IGNORECASE
)
# Matches a plain 10-digit mobile number, an optional +91 prefix, or a
# hyphen/space-grouped toll-free style number (e.g. "1800-123-4567").
_PHONE_RE = re.compile(r"(?:\+?91[-\s]?)?(?:\d[\d\-\s]{7,13}\d)")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

_MANUFACTURER_KEYWORD_RE = re.compile(
    r"\b(mfd\.?\s+by|manufactured\s+by|marketed\s+by|packed\s+by|imported\s+by|importer)\b",
    re.IGNORECASE,
)

_COUNTRY_OF_ORIGIN_RE = re.compile(r"country\s+of\s+origin\s*:?\s*(.+)", re.IGNORECASE)


def _bbox(line: Line | None) -> list[int] | None:
    """[left, top, right, bottom] for a matched field's source line, so the
    Step 7 report generator can draw an evidence box on the original image.
    None (not omitted) when there's no source line, so callers don't need
    a .get() default to tell "no line" apart from "line at 0,0"."""
    if line is None:
        return None
    return [line.left, line.top, line.right, line.bottom]


def _find_first_match(lines: list[Line], keyword_re: re.Pattern) -> tuple[int, Line] | None:
    for i, line in enumerate(lines):
        if keyword_re.search(line.text):
            return i, line
    return None


def _nearby_lines(lines: list[Line], index: int, window: int = 2) -> list[Line]:
    """A keyword line often doesn't contain the full value — check a couple of lines around it too."""
    start = max(0, index - window)
    end = min(len(lines), index + window + 1)
    return lines[start:end]


def classify_fields(lines: list[Line]) -> dict:
    result: dict = {}

    # --- net_quantity ---
    net_hit = _find_first_match(lines, _NET_KEYWORD_RE)
    candidates = _nearby_lines(lines, net_hit[0]) if net_hit else lines  # fall back to scanning the whole label

    qty_line = None
    qty_match = None
    for line in candidates:
        m = _QUANTITY_UNIT_RE.search(line.text)
        if m:
            qty_match = m
            qty_line = line
            break

    result["net_quantity"] = {
        "matched": qty_match is not None,
        "value": f"{qty_match.group(1)} {qty_match.group(2)}" if qty_match else None,
        "source_line": qty_line.text if qty_line else None,
        "pixel_height": qty_line.avg_word_height_px if qty_line else None,
        "bbox": _bbox(qty_line),
        "anchored_by_keyword": net_hit is not None,
    }

    # --- retail_sale_price (MRP) ---
    mrp_hit = _find_first_match(lines, _MRP_KEYWORD_RE)
    mrp_amount = None
    mrp_inclusive_wording = False
    mrp_line = None
    if mrp_hit:
        idx, _ = mrp_hit
        for line in _nearby_lines(lines, idx):
            amt = _MRP_AMOUNT_RE.search(line.text)
            if amt and mrp_amount is None:
                mrp_amount = amt.group(1)
                mrp_line = line
            if _INCLUSIVE_TAXES_RE.search(line.text):
                mrp_inclusive_wording = True

    result["retail_sale_price"] = {
        "matched": mrp_hit is not None,
        "amount": mrp_amount,
        "inclusive_of_taxes_wording_present": mrp_inclusive_wording,
        "source_line": mrp_line.text if mrp_line else None,
        "pixel_height": mrp_line.avg_word_height_px if mrp_line else None,
        "bbox": _bbox(mrp_line),
    }

    # --- date_of_manufacture_or_packing_or_import ---
    date_hit = _find_first_match(lines, _DATE_KEYWORD_RE)
    date_value = None
    date_line = None
    if date_hit:
        idx, _ = date_hit
        for line in _nearby_lines(lines, idx):
            m = _MONTH_YEAR_NUMERIC_RE.search(line.text) or _MONTH_NAME_RE.search(line.text)
            if m:
                date_value = m.group(0)
                date_line = line
                break

    result["date_of_manufacture_or_packing_or_import"] = {
        "matched": date_value is not None,
        "value": date_value,
        "source_line": date_line.text if date_line else None,
        "pixel_height": date_line.avg_word_height_px if date_line else None,
        "bbox": _bbox(date_line),
        "anchored_by_keyword": date_hit is not None,
    }

    # --- consumer_care_details ---
    care_hit = _find_first_match(lines, _CONSUMER_CARE_KEYWORD_RE)
    phone = None
    email = None
    care_line = None
    search_space = _nearby_lines(lines, care_hit[0], window=3) if care_hit else lines
    for line in search_space:
        if phone is None:
            p = _PHONE_RE.search(line.text)
            if p:
                phone = p.group(0)
                care_line = care_line or line
        if email is None:
            e = _EMAIL_RE.search(line.text)
            if e:
                email = e.group(0)
                care_line = care_line or line

    result["consumer_care_details"] = {
        "matched": phone is not None or email is not None,
        "phone": phone,
        "email": email,
        "pixel_height": care_line.avg_word_height_px if care_line else None,
        "bbox": _bbox(care_line),
        # Unanchored matches (no "consumer care" keyword found nearby) are
        # lower confidence: the phone/email could belong to something else
        # entirely, e.g. a corporate website contact.
        "anchored_by_keyword": care_hit is not None,
    }

    # --- manufacturer_packer_importer_details ---
    mfr_hit = _find_first_match(lines, _MANUFACTURER_KEYWORD_RE)
    mfr_text = None
    mfr_line = None
    if mfr_hit:
        idx, _ = mfr_hit
        # The address usually continues for a line or two after the
        # keyword line — but stop as soon as we hit another declaration's
        # keyword (consumer care, MRP, net qty, date), so the address
        # doesn't swallow the next field. Capped at 4 lines either way
        # as a backstop for labels with no other keyword lines nearby.
        mfr_line = lines[idx]
        collected = [lines[idx].text]
        for line in lines[idx + 1 : idx + 5]:
            if (
                _CONSUMER_CARE_KEYWORD_RE.search(line.text)
                or _MRP_KEYWORD_RE.search(line.text)
                or _NET_KEYWORD_RE.search(line.text)
                or _DATE_KEYWORD_RE.search(line.text)
            ):
                break
            collected.append(line.text)
        mfr_text = " ".join(collected)

    result["manufacturer_packer_importer_details"] = {
        "matched": mfr_hit is not None,
        "raw_text": mfr_text,
        "pixel_height": mfr_line.avg_word_height_px if mfr_line else None,
        "bbox": _bbox(mfr_line),
        "needs_inspector_confirmation": True,  # free-text field — always flag for human review
    }

    # --- country_of_origin (only relevant for imports) ---
    origin_hit = _find_first_match(lines, _COUNTRY_OF_ORIGIN_RE)
    result["country_of_origin"] = {
        "matched": origin_hit is not None,
        "value": _COUNTRY_OF_ORIGIN_RE.search(origin_hit[1].text).group(1).strip() if origin_hit else None,
        "pixel_height": origin_hit[1].avg_word_height_px if origin_hit else None,
        "bbox": _bbox(origin_hit[1]) if origin_hit else None,
    }

    # --- generic_name: not auto-detected, see module docstring ---
    result["generic_name"] = {
        "matched": False,
        "value": None,
        "note": "Not automatically detected in this version — requires inspector entry or a future product-category classifier.",
    }

    return result
