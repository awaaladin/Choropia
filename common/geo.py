from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points in kilometers.

    Kept as plain Python (rather than a DB-side GIS function) since the pilot
    is a single city and we don't want a PostGIS dependency for this scale.
    """
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))
