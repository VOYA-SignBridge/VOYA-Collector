"""Offline GeoIP lookup and presentation helpers.

The MaxMind databases are optional. Missing databases, invalid addresses, and
Redis failures all degrade to an empty/local result so activity monitoring can
never interrupt a real request.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
from typing import Any, Dict

from app.infrastructure.redis.connection import get_activity_client

logger = logging.getLogger("activity")

GEOIP_DB_PATH = os.getenv("GEOIP_DB_PATH", "/workspace/geoip/GeoLite2-City.mmdb")
GEOIP_ASN_DB_PATH = os.getenv("GEOIP_ASN_DB_PATH", "/workspace/geoip/GeoLite2-ASN.mmdb")

_geo_reader = None
_geo_tried = False
_asn_reader = None
_asn_tried = False


def get_geo_reader():
    global _geo_reader, _geo_tried
    if _geo_tried:
        return _geo_reader
    _geo_tried = True
    try:
        import geoip2.database  # optional dependency

        if os.path.exists(GEOIP_DB_PATH):
            _geo_reader = geoip2.database.Reader(GEOIP_DB_PATH)
            logger.info("[ACTIVITY] GeoIP City DB loaded: %s", GEOIP_DB_PATH)
        else:
            logger.info("[ACTIVITY] GeoIP City DB not found at %s — location disabled", GEOIP_DB_PATH)
    except Exception as exc:
        logger.warning("[ACTIVITY] GeoIP City init failed (location disabled): %s", exc)
    return _geo_reader


def get_asn_reader():
    """Return the optional ASN reader used to resolve network operators."""
    global _asn_reader, _asn_tried
    if _asn_tried:
        return _asn_reader
    _asn_tried = True
    try:
        import geoip2.database  # optional dependency

        if os.path.exists(GEOIP_ASN_DB_PATH):
            _asn_reader = geoip2.database.Reader(GEOIP_ASN_DB_PATH)
            logger.info("[ACTIVITY] GeoIP ASN DB loaded: %s", GEOIP_ASN_DB_PATH)
        else:
            logger.info("[ACTIVITY] GeoIP ASN DB not found at %s — ISP disabled", GEOIP_ASN_DB_PATH)
    except Exception as exc:
        logger.warning("[ACTIVITY] GeoIP ASN init failed (ISP disabled): %s", exc)
    return _asn_reader


def is_private(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except Exception:
        return True


def geo_lookup(ip: str) -> Dict[str, Any]:
    """Resolve an IP locally and cache the result in Redis for 24 hours."""
    if not ip or is_private(ip):
        return {"local": True}

    client = get_activity_client()
    cache_key = f"act:geo:{ip}"
    if client is not None:
        try:
            cached = client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    geo: Dict[str, Any] = {}
    reader = get_geo_reader()
    if reader is not None:
        try:
            result = reader.city(ip)
            geo = {
                "country": result.country.name,
                "country_code": result.country.iso_code,
                "city": result.city.name,
                "lat": result.location.latitude,
                "lon": result.location.longitude,
            }
        except Exception:
            geo = {}

    asn_reader = get_asn_reader()
    if asn_reader is not None:
        try:
            result = asn_reader.asn(ip)
            geo["isp"] = result.autonomous_system_organization
            geo["asn"] = result.autonomous_system_number
        except Exception:
            pass

    if client is not None:
        try:
            client.set(cache_key, json.dumps(geo), ex=86400)
        except Exception:
            pass
    return geo


def location_label(geo: Dict[str, Any]) -> str:
    if not geo or geo.get("local"):
        return "Nội bộ / LAN"
    parts = [part for part in (geo.get("city"), geo.get("country")) if part]
    return ", ".join(parts) if parts else "Không rõ"
