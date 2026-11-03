import re
import urllib.request
import json
import logging

logger = logging.getLogger(__name__)

def lookup_product_by_barcode(barcode: str) -> dict | None:
    """
    Looks up an Indian product by barcode (GTIN / EAN-13) using Open Food Facts India & World APIs.
    Returns a dict with product attributes suitable for populating a Product record, or None if not found.
    """
    clean_barcode = re.sub(r"\D", "", barcode)
    if not clean_barcode:
        return None

    urls = [
        f"https://in.openfoodfacts.org/api/v2/product/{clean_barcode}.json",
        f"https://world.openfoodfacts.org/api/v2/product/{clean_barcode}.json",
    ]

    for url in urls:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "LegalMetrologyChecker - IndianCompliance/1.0"}
            )
            with urllib.request.urlopen(req, timeout=4.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    if data.get("status") == 1 and "product" in data:
                        p = data["product"]
                        name = p.get("product_name") or p.get("product_name_en") or p.get("product_name_hi")
                        if not name:
                            continue
                        
                        brand = p.get("brands") or p.get("brand_owner") or ""
                        if "," in brand:
                            brand = brand.split(",")[0].strip()

                        categories = p.get("categories_tags") or []
                        category = "General Commodity"
                        if categories:
                            raw_cat = categories[0].replace("en:", "").replace("-", " ").title()
                            category = raw_cat

                        mfg = p.get("manufacturing_places") or p.get("brands") or brand
                        origins = p.get("origins") or p.get("countries_tags") or []
                        if clean_barcode.startswith("890"):
                            is_imported = False
                        else:
                            is_imported = any("india" not in str(o).lower() for o in origins) if origins else False

                        return {
                            "barcode": clean_barcode,
                            "name": name.strip(),
                            "brand": brand.strip() if brand else None,
                            "category": category.strip() if category else None,
                            "manufacturer_name": mfg.strip() if mfg else None,
                            "is_imported": is_imported,
                        }
        except Exception as exc:
            logger.debug(f"Lookup failed for {url}: {exc}")
            continue

    return None
