"""
KML/KMZ Service — parses uploaded contour files into NormalizedContourData.

Handles:
  - KML files (raw XML)
  - KMZ files (zip archives containing a .kml)
  - Elevation extraction from <name> element
  - LineString coordinate parsing
  - Bounding box calculation
  - Malformed input detection
"""

from __future__ import annotations

import io
import logging
import zipfile
from typing import List, Optional, Tuple

from lxml import etree

from app.models.contour import BoundingBox, ContourLine, NormalizedContourData

logger = logging.getLogger(__name__)

# KML namespace map — Google Earth KML
_KML_NS = {
    "kml": "http://www.opengis.net/kml/2.2",
    "gx":  "http://www.google.com/kml/ext/2.2",
}


class KMLParseError(ValueError):
    """Raised when the uploaded file cannot be parsed as valid KML/KMZ."""
    pass


# ── Public entry point ────────────────────────────────────────────────────────

def parse_contour_file(
    file_bytes: bytes,
    filename: str,
) -> NormalizedContourData:
    """
    Parse a KML or KMZ file and return a NormalizedContourData object.

    Args:
        file_bytes: Raw bytes of the uploaded file.
        filename:   Original filename (used for format detection and metadata).

    Returns:
        NormalizedContourData with all contour lines extracted.

    Raises:
        KMLParseError: If the file is invalid, unreadable, or yields no contours.
    """
    lower = filename.lower()

    if lower.endswith(".kmz"):
        kml_bytes = _extract_kml_from_kmz(file_bytes, filename)
        source_format = "KMZ"
    elif lower.endswith(".kml"):
        kml_bytes = file_bytes
        source_format = "KML"
    else:
        raise KMLParseError(
            f"Unsupported file extension for '{filename}'. Expected .kml or .kmz."
        )

    contours = _parse_kml_bytes(kml_bytes, filename)

    if not contours:
        raise KMLParseError(
            f"No contour lines could be extracted from '{filename}'. "
            "Ensure the file contains LineString Placemarks with elevation data."
        )

    bbox = _compute_bbox(contours)

    logger.info(
        "Parsed %d contour lines from '%s' (elevation %.1f – %.1f m, bbox %s)",
        len(contours),
        filename,
        min(c.elevation_m for c in contours),
        max(c.elevation_m for c in contours),
        bbox,
    )

    return NormalizedContourData(
        contours=contours,
        bbox=bbox,
        source_filename=filename,
        source_format=source_format,
        crs="EPSG:4326",
    )


# ── KMZ extraction ────────────────────────────────────────────────────────────

def _extract_kml_from_kmz(file_bytes: bytes, filename: str) -> bytes:
    """Unzip a KMZ archive and return the bytes of the primary .kml file."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            kml_names = [n for n in zf.namelist() if n.lower().endswith(".kml")]
            if not kml_names:
                raise KMLParseError(f"No .kml file found inside KMZ archive '{filename}'.")
            # Prefer "doc.kml" (Google Earth convention) otherwise take the first
            primary = next((n for n in kml_names if n.lower() == "doc.kml"), kml_names[0])
            logger.debug("Extracting '%s' from KMZ archive.", primary)
            return zf.read(primary)
    except zipfile.BadZipFile as exc:
        raise KMLParseError(f"'{filename}' is not a valid ZIP/KMZ archive: {exc}") from exc


# ── KML XML parsing ───────────────────────────────────────────────────────────

def _parse_kml_bytes(kml_bytes: bytes, filename: str) -> List[ContourLine]:
    """Parse KML XML bytes and extract all contour LineStrings."""
    try:
        root = etree.fromstring(kml_bytes)
    except etree.XMLSyntaxError as exc:
        raise KMLParseError(f"XML syntax error in '{filename}': {exc}") from exc

    # Detect namespace
    ns = _detect_namespace(root)

    placemarks = root.findall(f".//{ns}Placemark")
    if not placemarks:
        raise KMLParseError(
            f"No Placemark elements found in '{filename}'. "
            "Ensure the file is a valid contour KML."
        )

    contours: List[ContourLine] = []
    skipped = 0

    for pm in placemarks:
        result = _parse_placemark(pm, ns)
        if result is not None:
            contours.append(result)
        else:
            skipped += 1

    if skipped:
        logger.warning(
            "Skipped %d Placemarks that could not be parsed as contour lines.", skipped
        )

    return contours


def _detect_namespace(root: etree._Element) -> str:
    """
    Detect the KML namespace prefix to use in XPath queries.
    Returns either '{http://www.opengis.net/kml/2.2}' or '' for no-namespace KML.
    """
    tag = root.tag
    if tag.startswith("{"):
        ns_uri = tag.split("}")[0] + "}"
        return ns_uri
    return ""


def _parse_placemark(pm: etree._Element, ns: str) -> Optional[ContourLine]:
    """
    Parse a single Placemark element into a ContourLine.
    Returns None if the placemark cannot be interpreted as a contour.
    """
    # ── Elevation from <name> ─────────────────────────────────────────────
    name_el = pm.find(f"{ns}name")
    if name_el is None or not name_el.text:
        return None

    elevation = _parse_elevation(name_el.text.strip())
    if elevation is None:
        return None

    # ── Optional contour ID from ExtendedData ─────────────────────────────
    contour_id = _extract_extended_id(pm, ns)

    # ── LineString coordinates ────────────────────────────────────────────
    coords_el = pm.find(f".//{ns}LineString/{ns}coordinates")
    if coords_el is None or not coords_el.text:
        return None

    coordinates = _parse_coordinates(coords_el.text.strip())
    if len(coordinates) < 2:
        return None

    try:
        return ContourLine(
            elevation_m=elevation,
            coordinates=coordinates,
            contour_id=contour_id,
        )
    except ValueError:
        return None


def _parse_elevation(text: str) -> Optional[float]:
    """
    Parse elevation from the name text.
    Handles forms like "277.0", "277", "277m", "Elevation: 277".
    Returns None if no numeric value is found.
    """
    import re
    match = re.search(r"[-+]?\d+\.?\d*", text)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def _extract_extended_id(pm: etree._Element, ns: str) -> Optional[str]:
    """Extract the ID value from ExtendedData/SchemaData/SimpleData[@name='ID']."""
    for sd in pm.findall(f".//{ns}SimpleData"):
        if sd.get("name", "").upper() in ("ID", "CONTOUR_ID", "FID"):
            return sd.text
    return None


def _parse_coordinates(coord_text: str) -> List[Tuple[float, float]]:
    """
    Parse KML coordinate string into (lon, lat) tuples.
    KML format: 'lon,lat[,alt] lon,lat[,alt] ...'
    """
    coords: List[Tuple[float, float]] = []
    for token in coord_text.split():
        parts = token.strip().split(",")
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                # Sanity check
                if -180 <= lon <= 180 and -90 <= lat <= 90:
                    coords.append((lon, lat))
            except ValueError:
                continue
    return coords


# ── Bounding box ──────────────────────────────────────────────────────────────

def _compute_bbox(contours: List[ContourLine]) -> BoundingBox:
    """Compute the bounding box that covers all contour coordinates."""
    all_lons = [lon for c in contours for lon, _ in c.coordinates]
    all_lats = [lat for c in contours for _, lat in c.coordinates]
    return BoundingBox(
        min_lon=min(all_lons),
        min_lat=min(all_lats),
        max_lon=max(all_lons),
        max_lat=max(all_lats),
    )
