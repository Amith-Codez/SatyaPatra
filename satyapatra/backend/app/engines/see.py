"""SEE engine: check physical claims against open data.

Building footprints (Google Open Buildings / OpenStreetMap format, GeoJSON with an optional height)
are summed inside the declared campus boundary and turned into an estimated floor area.
Lab photos are checked for GPS inside the campus and a recent capture date.
Only large gaps are flagged, and only ever to "Manual review required" (it triggers an inspection).
"""
import json
import math
from datetime import datetime

import httpx
import piexif
from shapely.geometry import Point, shape

from .. import config

FLOOR_HEIGHT_M = 3.6


def _m2(geom):
    """Area in m² of a lon/lat polygon (equirectangular projection; fine at campus scale)."""
    lat0 = geom.centroid.y
    kx, ky = 111_320 * math.cos(math.radians(lat0)), 110_540
    from shapely.affinity import scale
    return scale(geom, xfact=kx, yfact=ky, origin=(0, 0)).area


def footprint_check(institution, footprints_geojson):
    campus = shape(json.loads(institution["campus_geojson"]))
    total_fp, est_floor, n = 0.0, 0.0, 0
    for f in footprints_geojson.get("features", []):
        g = shape(f["geometry"])
        if not campus.intersects(g):
            continue
        a = _m2(g.intersection(campus))
        h = (f.get("properties") or {}).get("height_m") or FLOOR_HEIGHT_M
        floors = max(1, round(h / FLOOR_HEIGHT_M))
        total_fp += a
        est_floor += a * floors
        n += 1
    claimed = institution.get("claimed_builtup_m2") or 0
    ratio = claimed / est_floor if est_floor else None
    outcome = config.REVIEW if (ratio is None or ratio > 1.6) else config.VERIFIED
    detail = (f"Claimed {claimed:,.0f} m²; {n} buildings detected, footprint {total_fp:,.0f} m², "
              f"estimated floor area {est_floor:,.0f} m² ({ratio:.1f}x claimed vs estimate)." if ratio
              else "No buildings found inside the declared boundary.")
    return {"engine": "SEE", "code": "builtup_vs_satellite", "outcome": outcome, "severity": "soft",
            "weight": 30 if outcome != config.VERIFIED else 0,
            "title": "Built-up area matches satellite building data" if outcome == config.VERIFIED
            else "Claimed built-up area far exceeds what satellite data shows",
            "detail": detail, "evidence": {"buildings": n, "footprint_m2": round(total_fp), "estimated_m2": round(est_floor),
                                           "claimed_m2": claimed, "ratio": round(ratio, 2) if ratio else None}}


OVERPASS_SERVERS = ["https://overpass-api.de/api/interpreter",
                    "https://overpass.kumi.systems/api/interpreter",
                    "https://overpass.private.coffee/api/interpreter"]


def live_osm_buildings(campus_geojson):
    """Fetch real OpenStreetMap building footprints inside a boundary (Overpass API)."""
    g = shape(json.loads(campus_geojson))
    minx, miny, maxx, maxy = g.bounds
    qry = f'[out:json][timeout:25];way["building"]({miny},{minx},{maxy},{maxx});out geom;'
    r = None
    for url in OVERPASS_SERVERS:  # the public servers are often at capacity; try the next one
        try:
            r = httpx.post(url, data={"data": qry}, timeout=20,
                           headers={"User-Agent": "SatyaPatra/1.0 (SIH 2026 prototype)", "Accept": "application/json"})
            r.raise_for_status()
            break
        except httpx.HTTPError:
            r = None
    if r is None:
        raise RuntimeError("all public OpenStreetMap servers are busy")
    feats = []
    for el in r.json().get("elements", []):
        coords = [[p["lon"], p["lat"]] for p in el.get("geometry", [])]
        if len(coords) >= 4:
            lv = el.get("tags", {}).get("building:levels")
            feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords]},
                          "properties": {"height_m": float(lv) * FLOOR_HEIGHT_M if lv and lv.replace('.', '').isdigit() else None,
                                         "source": "OpenStreetMap"}})
    return {"type": "FeatureCollection", "features": feats}


def _dms(v):
    d, m, s = v
    return d[0] / d[1] + m[0] / m[1] / 60 + s[0] / s[1] / 3600


def photo_check(path, institution, cycle_start="2026-01-01"):
    try:
        ex = piexif.load(path)
    except Exception:
        ex = {}
    gps = ex.get("GPS", {})
    when = ex.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
    out = {"engine": "SEE", "code": "photo_location", "severity": "soft", "weight": 0, "evidence": {}}
    if not gps:
        out.update(outcome=config.VERIFIED, title="Photo has no location data",
                   detail="Messaging apps remove location; missing GPS is not treated as a problem.")
        return out
    lat = _dms(gps[piexif.GPSIFD.GPSLatitude]) * (-1 if gps.get(piexif.GPSIFD.GPSLatitudeRef) == b"S" else 1)
    lon = _dms(gps[piexif.GPSIFD.GPSLongitude]) * (-1 if gps.get(piexif.GPSIFD.GPSLongitudeRef) == b"W" else 1)
    campus = shape(json.loads(institution["campus_geojson"]))
    inside = campus.buffer(0.0005).contains(Point(lon, lat))
    taken = datetime.strptime(when.decode(), "%Y:%m:%d %H:%M:%S").date().isoformat() if when else None
    old = taken and taken < cycle_start
    if inside and not old:
        out.update(outcome=config.VERIFIED, title="Photo taken on campus this cycle",
                   detail=f"GPS {lat:.5f}, {lon:.5f} is inside the declared campus; taken {taken}.")
    else:
        why = []
        if not inside:
            dist = campus.distance(Point(lon, lat)) * 111_000
            why.append(f"GPS {lat:.5f}, {lon:.5f} is about {dist:,.0f} m outside the campus")
        if old:
            why.append(f"taken {taken}, before this approval cycle")
        out.update(outcome=config.REVIEW, weight=35, title="Lab photo was not taken on this campus this cycle",
                   detail="; ".join(why) + ".")
    out["evidence"] = {"lat": lat, "lon": lon, "taken": taken, "inside": bool(inside)}
    return out
