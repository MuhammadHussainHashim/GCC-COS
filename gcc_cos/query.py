"""The same product/search filters drive CLI, dashboard and exports."""
from .model import is_product


def select(rows, products_only=False, search='', category=None, manufacturer=None,
           geography=None, status=None, verification_status=None, warnings_only=False, warning=None, hs6=None):
    results = []
    needle = search.casefold().strip()
    for row in rows:
        if warnings_only and not row.get("issues"):
            continue
        if warning and warning not in (row.get("issues") or []):
            continue
        if hs6 and row.get("hs6") != hs6:
            continue
        if products_only and not is_product(row):
            continue
        if any(value and row.get(field) != value for field, value in [
            ('category', category), ('manufacturer', manufacturer), ('geography', geography),
            ('review_status', status), ('verification_status', verification_status)]):
            continue
        haystack = ' '.join(str(row.get(k) or '') for k in
                            ('product_name', 'manufacturer', 'category', 'subcategory', 'material', 'epd_id', 'hs6'))
        if needle and needle not in haystack.casefold():
            continue
        results.append(row)
    return results
