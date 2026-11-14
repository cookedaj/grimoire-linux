# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit and currency conversion (no Qt).

Units: each category maps a unit to its factor in the category's base unit (temperature has offsets). Currency
rates come from the European Central Bank's daily reference rates (one public XML file, no key, no account), fetched
only when you press Update rates and cached in CACHE/calculatorl-rates.json with their date. Nothing else leaves
this PC.
"""
import json
import time
import urllib.request
import xml.etree.ElementTree as ET

from grimoire.i18n import tr_noop
from grimoire.paths import CACHE

RATES_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
RATES_FILE = CACHE / "calculatorl-rates.json"

# category → (name, {unit: (label, factor to the base unit)})
CATEGORIES = {
    "length": (tr_noop("grimoire.spells.calculatorl.units", "Length"), {
        "mm": ("mm", 0.001), "cm": ("cm", 0.01), "m": ("m", 1), "km": ("km", 1000), "in": ("in", 0.0254),
        "ft": ("ft", 0.3048), "yd": ("yd", 0.9144), "mi": ("mi", 1609.344), "nmi": ("nmi", 1852)}),
    "mass": (tr_noop("grimoire.spells.calculatorl.units", "Weight"), {
        "mg": ("mg", 1e-6), "g": ("g", 0.001), "kg": ("kg", 1), "t": ("t", 1000), "oz": ("oz", 0.028349523125),
        "lb": ("lb", 0.45359237), "st": ("st", 6.35029318)}),
    "temperature": (tr_noop("grimoire.spells.calculatorl.units", "Temperature"), {
        "c": ("°C", None), "f": ("°F", None), "k": ("K", None)}),
    "volume": (tr_noop("grimoire.spells.calculatorl.units", "Volume"), {
        "ml": ("ml", 0.001), "l": ("l", 1), "m3": ("m³", 1000), "tsp": ("tsp", 0.00492892), "tbsp": ("tbsp", 0.0147868),
        "cup": ("cup", 0.236588), "floz": ("fl oz", 0.0295735), "pt": ("pt", 0.473176), "gal": ("gal", 3.78541)}),
    "area": (tr_noop("grimoire.spells.calculatorl.units", "Area"), {
        "cm2": ("cm²", 1e-4), "m2": ("m²", 1), "km2": ("km²", 1e6), "ha": ("ha", 1e4), "in2": ("in²", 0.00064516),
        "ft2": ("ft²", 0.09290304), "ac": ("acre", 4046.8564224), "mi2": ("mi²", 2589988.110336)}),
    "speed": (tr_noop("grimoire.spells.calculatorl.units", "Speed"), {
        "ms": ("m/s", 1), "kmh": ("km/h", 1 / 3.6), "mph": ("mph", 0.44704), "kn": ("kn", 0.514444),
        "fts": ("ft/s", 0.3048)}),
    "data": (tr_noop("grimoire.spells.calculatorl.units", "Data"), {
        "b": ("bit", 1 / 8), "B": ("B", 1), "KB": ("KB", 1e3), "MB": ("MB", 1e6), "GB": ("GB", 1e9),
        "TB": ("TB", 1e12), "KiB": ("KiB", 1024), "MiB": ("MiB", 1024 ** 2), "GiB": ("GiB", 1024 ** 3),
        "TiB": ("TiB", 1024 ** 4)}),
    "time": (tr_noop("grimoire.spells.calculatorl.units", "Time"), {
        "ms": ("ms", 0.001), "s": ("s", 1), "min": ("min", 60), "h": ("h", 3600), "d": ("d", 86400),
        "wk": ("wk", 604800), "yr": ("yr", 31557600)}),
    "energy": (tr_noop("grimoire.spells.calculatorl.units", "Energy"), {
        "j": ("J", 1), "kj": ("kJ", 1000), "cal": ("cal", 4.184), "kcal": ("kcal", 4184), "wh": ("Wh", 3600),
        "kwh": ("kWh", 3.6e6)}),
}


def convert(category: str, value: float, src: str, dst: str) -> float:
    if category == "temperature":
        c = value if src == "c" else (value - 32) * 5 / 9 if src == "f" else value - 273.15
        return c if dst == "c" else c * 9 / 5 + 32 if dst == "f" else c + 273.15
    units = CATEGORIES[category][1]
    return value * units[src][1] / units[dst][1]


# ---------------------------------------------------------------- currency
def cached_rates() -> dict:
    """{"date": "YYYY-MM-DD", "fetched": ts, "rates": {code: per EUR}} or {} before the first update."""
    try:
        d = json.loads(RATES_FILE.read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(d, dict) or not isinstance(d.get("rates"), dict):
        return {}
    d["rates"] = {k: float(v) for k, v in d["rates"].items()
                  if isinstance(k, str) and len(k) == 3 and k.isalpha() and isinstance(v, (int, float)) and v > 0}
    return d


def parse_ecb(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)
    rates, date = {"EUR": 1.0}, ""
    for el in root.iter():
        if el.tag.endswith("Cube") and el.get("time"):
            date = el.get("time")
        if el.tag.endswith("Cube") and el.get("currency") and el.get("rate"):
            cur, rate = el.get("currency"), float(el.get("rate"))
            if len(cur) == 3 and cur.isalpha() and rate > 0:
                rates[cur] = rate
    if len(rates) < 10:
        raise ValueError("no rates in the answer")
    return {"date": date, "fetched": int(time.time()), "rates": rates}


def update_rates(fetch=None) -> dict:
    """Download today's ECB rates (on the user's click) and cache them. Raises OSError/ValueError."""
    if fetch is None:
        def fetch():
            req = urllib.request.Request(RATES_URL, headers={"User-Agent": "Grimoire-CalculatorL"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read(1_000_000)
    d = parse_ecb(fetch())
    RATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    RATES_FILE.write_text(json.dumps(d))
    return d


def convert_currency(rates: dict, value: float, src: str, dst: str) -> float:
    r = rates["rates"]
    return value / r[src] * r[dst]
