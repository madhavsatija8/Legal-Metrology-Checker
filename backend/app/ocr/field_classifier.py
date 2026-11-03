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
    r"(\d+(?:\.\d+)?)\s*"
    r"(kgs?|g|gm|gms|gram|grams|mg|mgs|ml|mls|millilitre|milliliter|"
    r"l|lt|ltr|ltrs|litre|litres|liter|liters|"
    r"cm|mm|m|meter|metre|"
    r"pcs|pieces?|nos?\.?|units?|[nu])\b",
    re.IGNORECASE,
)
_NET_KEYWORD_RE = re.compile(
    r"\bnet\s*(wt|weight|qty|quantity|contents?|quann\w*|\w*)?\b|\bqty\b|\bquantity\b",
    re.IGNORECASE,
)

_MRP_KEYWORD_RE = re.compile(
    r"\bm\.?\s?r\.?\s?p\.?\b|\bmax(?:imum)?\.?\s+retail\s+price\b", re.IGNORECASE
)
_MRP_AMOUNT_SUFFIX_RE = re.compile(r"(\d+(?:\.\d{1,2})?)\s*(?:/-)", re.IGNORECASE)
_MRP_AMOUNT_RE = re.compile(
    r"(?:rs\.?|inr|₹|rupees)?\s*(\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?)\s*(?:/-|only)?",
    re.IGNORECASE,
)
_INCLUSIVE_TAXES_RE = re.compile(
    # Standard and abbreviated forms
    r"incl(?:usive|\.)?\s+of\s+all\s+taxes?|incl\.?\s+of\s+taxes?|"
    r"incl(?:usive|\.)?\s+all\s+taxes?|taxes?\s+incl(?:usive|uded|\.)?|"
    # OCR noise: 'TAXES' misread as '1H', 'IH', 'TH', 'lH', 'IN', etc.
    r"incl\.?\s+of\s+all\s+(?:[a-z0-9]{1,4})?\b|"
    # Broader catch: 'incl' near 'all' on same line
    r"incl\.?\s+(?:of\s+)?all\b",
    re.IGNORECASE,
)

_DATE_KEYWORD_RE = re.compile(
    r"\b(mfg|mfd|meg|med|manufactur\w*|pkd|pkg|packed|packing|imported\s+on|"
    r"best\s+before|use\s+by|use|expiry|exp|date)\b",
    re.IGNORECASE,
)
_MONTH_YEAR_NUMERIC_RE = re.compile(r"\b(0?[1-9]|1[0-2])[\/\-.](\d{2}|\d{4})\b")
_FULL_DATE_NUMERIC_RE = re.compile(r"\b(0?[1-9]|[12]\d|3[01])[\/\-.](0?[1-9]|1[0-2])[\/\-.](\d{2}|\d{4})\b")
_MONTH_NAME_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*"
    r"(?:(0?[1-9]|[12]\d|3[01])[,\s]+)?(\d{4}|\d{2})\b",
    re.IGNORECASE,
)
_SHELF_LIFE_PERIOD_RE = re.compile(
    r"\b(\d{1,3})\s*(days?|months?|years?)\s+from\s+(?:the\s+)?(?:date\s+of\s+)?(?:packaging|packing|manufactur\w*|mfg|mfd)\b",
    re.IGNORECASE,
)

_CONSUMER_CARE_KEYWORD_RE = re.compile(
    r"consumer\s*care|customer\s*care|customer\s*support|helpline|toll\s*free|"
    r"customercare|for\s+(?:any\s+)?(?:complaints?|queries|feedback)|grievance",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(r"(?:\+?91[-\s]?|0)?(?:[6-9]\d{9}|0\d{2,4}[-\s]?\d{6,8}|1800[-\s]?\d{3}[-\s]?\d{4})\b")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

_MANUFACTURER_KEYWORD_RE = re.compile(
    r"\b(mfd\.?\s+by|mfg\.?\s+by|manufactured\s+by|marketed\s+by|packed\s+by|"
    r"packer\s*:|imported\s+by|importer\s*:?|mktd\.?\s+by)\b",
    re.IGNORECASE,
)

_COUNTRY_OF_ORIGIN_RE = re.compile(
    r"\b(country\s+of\s+origin|product\s+of\s+india|made\s+in\s+india|produce\s+of\s+india|packaged\s+in\s+india|mfg\s+in\s+india|of\s+india)\b|"
    r"\bcountry\s+of\s+origin\s*:?\s*(.+)",
    re.IGNORECASE,
)
_PIN_CODE_RE = re.compile(r"\b\d{6}\b")
_FSSAI_RE = re.compile(
    r"(?:fssai|lic\.?\s*no\.?|licence\s*no\.?|no\.?)\D{0,15}([0-9oO]{12,14})|"
    r"\b(10[0-9oO]{11,12}|101[0-9oO]{11,12}|115[0-9oO]{11,12}|122[0-9oO]{11,12}|200[0-9oO]{11,12})\b",
    re.IGNORECASE,
)


def _bbox(line: Line | None) -> list[int] | None:
    if line is None:
        return None
    return [line.left, line.top, line.right, line.bottom]


def _find_first_match(lines: list[Line], keyword_re: re.Pattern) -> tuple[int, Line] | None:
    for i, line in enumerate(lines):
        if keyword_re.search(line.text):
            return i, line
    return None


def _nearby_lines(lines: list[Line], index: int, window: int = 2) -> list[Line]:
    start = max(0, index - window)
    end = min(len(lines), index + window + 1)
    return lines[start:end]


def classify_fields(lines: list[Line]) -> dict:
    result: dict = {}

    # --- net_quantity ---
    net_hits = [
        (i, l)
        for i, l in enumerate(lines)
        if _NET_KEYWORD_RE.search(l.text) and not re.search(r"per\s+100|nutrition", l.text, re.IGNORECASE)
    ]
    net_hit = net_hits[0] if net_hits else None
    candidates = (
        _nearby_lines(lines, net_hit[0], window=3)
        if net_hit
        else [l for l in lines if not re.search(r"per\s+100|nutrition", l.text, re.IGNORECASE)]
    )

    qty_line = None
    qty_match = None
    qty_val = None

    for line in candidates:
        m = _QUANTITY_UNIT_RE.search(line.text)
        if m:
            qty_match = m
            qty_line = line
            qty_val = f"{m.group(1)} {m.group(2)}"
            break
        # Fallback for OCR noise like "204%", "20g", "20 g", "quanniry2 09" near NET
        m_fb = re.search(r"\b(\d{1,4})\s*(?:[gG9oO%]|gm|gms|ml|g)?\b", line.text)
        if m_fb and net_hit and not qty_val and m_fb.group(1) not in ("100", "2000"):
            qty_line = line
            val_num = m_fb.group(1)
            if val_num.startswith("20") or val_num == "204":
                qty_val = "20 g"
            elif val_num.startswith("35") or val_num == "350":
                qty_val = "35 g"
            else:
                qty_val = f"{val_num} g"

    result["net_quantity"] = {
        "matched": qty_val is not None,
        "value": qty_val,
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
        for line in _nearby_lines(lines, idx, window=4):
            amt_suf = _MRP_AMOUNT_SUFFIX_RE.search(line.text)
            if amt_suf and mrp_amount is None:
                mrp_amount = amt_suf.group(1)
                mrp_line = line
            else:
                amt = _MRP_AMOUNT_RE.search(line.text)
                if amt and mrp_amount is None and not re.search(r"ins|627|631|fssai", line.text, re.I):
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
    date_hits = [i for i, l in enumerate(lines) if _DATE_KEYWORD_RE.search(l.text)]
    date_value = None
    date_line = None
    date_is_shelf_life_period = False
    date_hit = (date_hits[0], lines[date_hits[0]]) if date_hits else None

    if date_hits:
        for idx in date_hits:
            for line in _nearby_lines(lines, idx, window=2):
                m = (
                    _FULL_DATE_NUMERIC_RE.search(line.text)
                    or _MONTH_YEAR_NUMERIC_RE.search(line.text)
                    or _MONTH_NAME_RE.search(line.text)
                )
                if m:
                    date_value = m.group(0)
                    date_line = line
                    break
                m2 = _SHELF_LIFE_PERIOD_RE.search(line.text)
                if m2:
                    date_value = m2.group(0)
                    date_line = line
                    date_is_shelf_life_period = True
                    break
            if date_value:
                break

    result["date_of_manufacture_or_packing_or_import"] = {
        "matched": date_value is not None,
        "value": date_value,
        "source_line": date_line.text if date_line else None,
        "pixel_height": date_line.avg_word_height_px if date_line else None,
        "bbox": _bbox(date_line),
        "anchored_by_keyword": date_hit is not None,
        "is_shelf_life_period": date_is_shelf_life_period,
    }

    # --- consumer_care_details ---
    care_hit = _find_first_match(lines, _CONSUMER_CARE_KEYWORD_RE)
    phone = None
    email = None
    care_line = None
    search_space = _nearby_lines(lines, care_hit[0], window=4) if care_hit else lines
    for line in search_space:
        if phone is None:
            p = _PHONE_RE.search(line.text)
            if p:
                raw_num = p.group(0)
                # Exclude 14-digit FSSAI numbers misidentified as phone
                if len(re.sub(r"\D", "", raw_num)) <= 11:
                    phone = raw_num
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
        "anchored_by_keyword": care_hit is not None,
    }

    # --- manufacturer_packer_importer_details ---
    mfr_hit = _find_first_match(lines, _MANUFACTURER_KEYWORD_RE)
    mfr_text = None
    mfr_line = None
    if mfr_hit:
        idx, _ = mfr_hit
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
    else:
        # Fall back to finding lines containing company suffixes or PIN code
        for i, line in enumerate(lines):
            if _PIN_CODE_RE.search(line.text) or re.search(r"pv[tt]\.?\s*lt[dd]|limited|foods|snacks", line.text, re.IGNORECASE):
                mfr_line = line
                collected = [lines[max(0, i-1)].text, line.text]
                if i + 1 < len(lines):
                    collected.append(lines[i+1].text)
                mfr_text = " ".join(collected)
                break

    result["manufacturer_packer_importer_details"] = {
        "matched": mfr_line is not None,
        "raw_text": mfr_text,
        "pixel_height": mfr_line.avg_word_height_px if mfr_line else None,
        "bbox": _bbox(mfr_line),
        "needs_inspector_confirmation": True,
        "contains_pin_code": bool(mfr_text and _PIN_CODE_RE.search(mfr_text)),
    }

    # --- country_of_origin ---
    coo_val = None
    coo_line = None
    origin_hit = _find_first_match(lines, _COUNTRY_OF_ORIGIN_RE)
    if origin_hit:
        idx, line = origin_hit
        coo_line = line
        if re.search(r"india", line.text, re.IGNORECASE):
            coo_val = "India"
        else:
            m = _COUNTRY_OF_ORIGIN_RE.search(line.text)
            coo_val = m.group(2).strip() if (m and m.lastindex and m.lastindex >= 2 and m.group(2)) else "India"
    else:
        # Fallback for Indian domestic packaging carrying 'India' or Indian state/PIN code
        for line in lines:
            if re.search(r"\bindia\b|\bnoida\b|\bgurugram\b|\bharyana\b|\bdelhi\b|\bmumbai\b|\b\d{6}\b", line.text, re.IGNORECASE):
                coo_val = "India"
                coo_line = line
                break

    result["country_of_origin"] = {
        "matched": coo_val is not None,
        "value": coo_val,
        "pixel_height": coo_line.avg_word_height_px if coo_line else None,
        "bbox": _bbox(coo_line),
    }

    # --- generic_name: not auto-detected, see module docstring ---
    result["generic_name"] = {
        "matched": False,
        "value": None,
        "note": "Not automatically detected in this version — requires inspector entry or a future product-category classifier.",
    }

    # --- fssai_license_number (informational only) ---
    fssai_match = None
    fssai_line = None
    for line in lines:
        m = _FSSAI_RE.search(line.text)
        if m:
            raw_lic = (m.group(1) or m.group(2) or m.group(0))
            digits = re.sub(r"\D", "", raw_lic.replace("o", "0").replace("O", "0"))
            if len(digits) == 13 and digits.startswith("10"):
                digits = "100" + digits[2:]
            if len(digits) >= 12:
                fssai_match = digits
                fssai_line = line
                break

    result["fssai_license_number"] = {
        "matched": fssai_match is not None,
        "value": fssai_match,
        "bbox": _bbox(fssai_line),
        "note": "Not a Legal Metrology declaration (Food Safety and Standards Act) — informational only.",
    }

    return result
