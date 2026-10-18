"""Deterministic marketplace ranking that keeps unavailable inventory visible."""


def rank_vehicle_matches(matches, sort_by="recommended"):
    """Sort search payloads by availability, distance, or transparent price order."""
    sort_by = str(sort_by or "recommended").strip().lower()
    if sort_by not in {"recommended", "nearest", "price_low", "price_high"}:
        raise ValueError("Choose recommended, nearest, lowest price, or highest price sorting.")

    def number(item, key, fallback):
        try:
            return float(item.get(key))
        except (TypeError, ValueError):
            return fallback

    def available(item):
        try:
            return int(item.get("available_quantity") or 0) > 0
        except (TypeError, ValueError):
            return item.get("availability_status") == "AVAILABLE"

    if sort_by == "nearest":
        key = lambda item: (number(item, "distance_km", float("inf")), not available(item), number(item, "daily_rate", float("inf")), str(item.get("name", "")).casefold())
    elif sort_by == "price_low":
        key = lambda item: (number(item, "daily_rate", float("inf")), not available(item), number(item, "distance_km", float("inf")), str(item.get("name", "")).casefold())
    elif sort_by == "price_high":
        key = lambda item: (-number(item, "daily_rate", float("-inf")), not available(item), number(item, "distance_km", float("inf")), str(item.get("name", "")).casefold())
    else:
        # Availability is always first. With coordinates, favor nearby options;
        # without coordinates, surface lower fares without inventing distances.
        key = lambda item: (not available(item), number(item, "distance_km", 0), number(item, "daily_rate", float("inf")), str(item.get("name", "")).casefold())
    return sorted(matches, key=key)
