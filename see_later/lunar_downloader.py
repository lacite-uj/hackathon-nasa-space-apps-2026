#!/usr/bin/env python3
"""
Lunar Environmental Data Downloader
Target grid: global lunar equirectangular, 16 pixels/degree (5760 x 2880).

Outputs:
  average_temperature_K.tif
  nighttime_temperature_range_K.tif
  topography_m.tif
  far_uv_lya_brightness.tif
  basalt_presence.tif
  basalt_units.geojson
  provenance.json

Scientific caveats:
- Diviner GDR_L3 soil-temperature products cover only 60N to 60S.
  The global-sized temperature rasters therefore contain NoData outside
  that latitude band.
- The Diviner "range" here is the range across the ten available nighttime
  local-time soil-temperature maps (19:30 through 05:30), NOT the full
  lunar diurnal maximum-minus-minimum.
- LAMP Lyman-alpha is far-UV brightness (photons/cm2/s/sr), not a terrestrial
  UV index and not incident solar irradiance. These maps cover polar caps
  from 80 degrees to the poles only.
- Mare/geologic polygons are basalt-associated mapping proxies. A mare
  polygon is not a pixel-by-pixel geochemical assay proving basalt.
- The Moon has no annual precipitation; no precipitation raster is created.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import urljoin

import numpy as np
import pandas as pd
import requests
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_bounds, from_origin
from rasterio.warp import reproject

import geopandas as gpd
from shapely.geometry import mapping

# ----------------------------- CONFIGURATION -----------------------------

PPD = 16
WIDTH = 360 * PPD
HEIGHT = 180 * PPD
MOON_RADIUS_M = 1_737_400.0
NODATA = -9999.0

ROOT = Path("lunar_environmental_data")
RAW = ROOT / "raw"
EXTRACTED = ROOT / "extracted"
OUT = ROOT / "geotiff"

# Verified public archive locations.
USGS_GEOLOGY_ZIP = (
    "https://asc-astropedia.s3.us-west-2.amazonaws.com/Moon/Geology/"
    "Unified_Geologic_Map_of_the_Moon_GIS_v2.zip"
)
LOLA_JP2_BASE = (
    "https://pds-geosciences.wustl.edu/lro/"
    "lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/"
    "cylindrical/jp2/"
)
LOLA_JP2 = LOLA_JP2_BASE + "ldem_16.jp2"

DIVINER_L3_JP2_BASE = (
    "https://pds-geosciences.wustl.edu/lro/"
    "urn-nasa-pds-lro_diviner_derived1/"
    "data_derived_gdr_l3/cylindrical/jp2/"
)
DIVINER_AVG = DIVINER_L3_JP2_BASE + "dgdr_st_avg_cyl_032_jp2.jp2"

# Ten nighttime local-time soil-temperature maps, 19:30 to 04:30.
# Their spread is explicitly a nighttime observed range, not a full
# day/night or seasonal temperature range.
NIGHTTIME_ST_FILES = [
    f"dgdr_st_clc_cyl_{t}_032_jp2.jp2"
    for t in ("1930", "2030", "2130", "2230", "2330",
              "0030", "0130", "0230", "0330", "0430")
]

# PDS3 LAMP polar GDR maps. Native map is 240 m/pixel, 80° to pole.
LAMP_BRIGHTNESS_BASE = (
    "https://planetarydata.jpl.nasa.gov/img/data/lro/lamp/gdr/"
    "LROLAM_2001/DATA/BRIGHTNESS/"
)
LAMP_FILES = {
    "north": "LAMP_80n_240mpp_lya_brite_01.img",
    "south": "LAMP_80s_240mpp_lya_brite_01.img",
}

# Moon equirectangular projection on a sphere. Coordinates are metres.
LUNAR_EQC = (
    f"+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 "
    f"+R={MOON_RADIUS_M} +units=m +no_defs +type=crs"
)
LUNAR_GEOG = (
    f"+proj=longlat +R={MOON_RADIUS_M} +no_defs +type=crs"
)

TARGET_TRANSFORM = from_bounds(
    -np.pi * MOON_RADIUS_M,
    -np.pi / 2 * MOON_RADIUS_M,
    np.pi * MOON_RADIUS_M,
    np.pi / 2 * MOON_RADIUS_M,
    WIDTH,
    HEIGHT,
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "LunarEnvironmentalDownloader/1.0"})
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
LOG = logging.getLogger("lunar-downloader")


# ----------------------------- DOWNLOAD HELPERS -----------------------------

def download(url: str, destination: Path) -> Path:
    """Download with streaming, retry-friendly partial-file handling."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        LOG.info("Already downloaded: %s", destination)
        return destination

    partial = destination.with_suffix(destination.suffix + ".part")
    LOG.info("Downloading %s", url)
    with SESSION.get(url, stream=True, timeout=(30, 180)) as response:
        response.raise_for_status()
        with partial.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    partial.replace(destination)
    LOG.info("Saved %s (%.1f MB)", destination, destination.stat().st_size / 1e6)
    return destination


def download_with_label(url: str, folder: Path) -> tuple[Path, Path]:
    """Download a detached PDS label when one exists next to the data file."""
    data_url = url
    data_path = download(data_url, folder / Path(url).name)
    label_url = url.rsplit(".", 1)[0] + ".lbl"
    label_path = folder / Path(label_url).name
    try:
        download(label_url, label_path)
    except requests.RequestException as exc:
        LOG.warning("Could not fetch detached label %s: %s", label_url, exc)
        label_path = None
    return data_path, label_path


def extract_zip(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    LOG.info("Extracting %s", zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        # Reject path traversal entries.
        base = destination.resolve()
        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            if base not in target.parents and target != base:
                raise RuntimeError(f"Unsafe ZIP member: {member.filename}")
        zf.extractall(destination)


# ----------------------------- RASTER HELPERS -----------------------------

def write_geotiff(
    path: Path,
    array: np.ndarray,
    units: str,
    description: str,
    source: str,
    extra_tags: dict | None = None,
) -> None:
    """Write a Float32 lunar EQC GeoTIFF with provenance tags."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(array, dtype=np.float32)
    data[~np.isfinite(data)] = NODATA

    profile = {
        "driver": "GTiff",
        "height": HEIGHT,
        "width": WIDTH,
        "count": 1,
        "dtype": "float32",
        "crs": LUNAR_EQC,
        "transform": TARGET_TRANSFORM,
        "nodata": NODATA,
        "compress": "deflate",
        "predictor": 3,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)
        dst.set_band_description(1, description)
        tags = {
            "TARGET": "Moon",
            "PROJECTION": "Lunar spherical equirectangular",
            "PIXELS_PER_DEGREE": str(PPD),
            "MOON_RADIUS_METRES": str(MOON_RADIUS_M),
            "UNITS": units,
            "DESCRIPTION": description,
            "SOURCE": source,
            "NODATA": str(NODATA),
        }
        if extra_tags:
            tags.update({str(k): str(v) for k, v in extra_tags.items()})
        dst.update_tags(**tags)
    LOG.info("Wrote %s", path)


def read_raster_scaled(path: Path) -> tuple[np.ndarray, rasterio.Affine, object, dict]:
    """
    Read a GeoTIFF/JP2 with its georeferencing and apply GDAL scale/offset
    if advertised. PDS labels remain alongside downloads for audit.
    """
    with rasterio.open(path) as ds:
        arr = ds.read(1, masked=True).astype("float32").filled(np.nan)
        scale = ds.scales[0] if ds.scales else 1.0
        offset = ds.offsets[0] if ds.offsets else 0.0

        # If GDAL did not expose scale/offset, consult the detached PDS label.
        # PDS labels commonly store physical_value = stored_value * scale + offset.
        label_path = path.with_suffix(".lbl")
        if scale == 1.0 and offset == 0.0 and label_path.exists():
            label_text = label_path.read_text(errors="replace")
            scale_match = re.search(
                r"SCALING_FACTOR\\s*=\\s*([-+0-9.eE]+)", label_text,
                flags=re.IGNORECASE
            )
            offset_match = re.search(
                r"\\bOFFSET\\s*=\\s*([-+0-9.eE]+)", label_text,
                flags=re.IGNORECASE
            )
            if scale_match:
                scale = float(scale_match.group(1))
            if offset_match:
                offset = float(offset_match.group(1))

        arr = arr * scale + offset
        crs = ds.crs
        transform = ds.transform
        tags = ds.tags()
        if crs is None:
            # Some PDS JP2 products have detached labels/auxiliary geotags.
            # Do not silently guess a projection from pixel dimensions.
            raise RuntimeError(
                f"{path.name} has no CRS in GDAL. Check its detached .LBL "
                "and *_aux.xml; add the documented source CRS before warping."
            )
    return arr, transform, crs, tags


def warp_to_global(
    source_array: np.ndarray,
    source_transform,
    source_crs,
    resampling=Resampling.bilinear,
) -> np.ndarray:
    dst = np.full((HEIGHT, WIDTH), np.nan, dtype=np.float32)
    # Reproject NaN as nodata; GDAL will leave uncovered cells as NaN.
    reproject(
        source=source_array,
        destination=dst,
        src_transform=source_transform,
        src_crs=source_crs,
        src_nodata=np.nan,
        dst_transform=TARGET_TRANSFORM,
        dst_crs=LUNAR_EQC,
        dst_nodata=np.nan,
        resampling=resampling,
        init_dest_nodata=True,
    )
    return dst


def read_and_warp_jp2(path: Path, resampling=Resampling.bilinear):
    arr, transform, crs, tags = read_raster_scaled(path)
    return warp_to_global(arr, transform, crs, resampling), tags


# ----------------------------- DIVINER -----------------------------

def build_diviner_products(provenance: dict) -> None:
    """
    Average soil temperature and nighttime observed range.
    GDR_L3 ST maps are Kelvin and cover 60N-60S at 32 ppd.
    """
    div_dir = RAW / "diviner"
    avg_path = download(DIVINER_AVG, div_dir / Path(DIVINER_AVG).name)
    avg_lbl = DIVINER_AVG.rsplit(".", 1)[0] + ".lbl"
    try:
        download(avg_lbl, div_dir / Path(avg_lbl).name)
    except requests.RequestException:
        LOG.warning("Diviner average label download failed; JP2 tags will be used.")

    avg, tags = read_and_warp_jp2(avg_path)
    write_geotiff(
        OUT / "average_temperature_K.tif",
        avg,
        "K",
        "Diviner GDR_L3 average soil temperature",
        DIVINER_AVG,
        {
            "COVERAGE": "approximately 60N to 60S; global grid outside coverage is NoData",
            "NATIVE_RESOLUTION": "32 pixels/degree; resampled to 16 pixels/degree",
            "SOURCE_SCALE_OFFSET_TAGS": json.dumps(tags),
        },
    )
    provenance["average_temperature_K"] = {
        "url": DIVINER_AVG,
        "units": "K",
        "coverage": "60N to 60S; NoData outside source coverage",
        "conversion": "native Diviner soil temperature retained in Kelvin",
    }

    night_maps = []
    for filename in NIGHTTIME_ST_FILES:
        url = DIVINER_L3_JP2_BASE + filename
        try:
            path = download(url, div_dir / filename)
            label_url = url.rsplit(".", 1)[0] + ".lbl"
            try:
                download(label_url, div_dir / Path(label_url).name)
            except requests.RequestException:
                pass
            grid, _ = read_and_warp_jp2(path)
            night_maps.append(grid)
        except Exception as exc:
            LOG.warning("Skipping nighttime map %s: %s", filename, exc)

    if len(night_maps) < 2:
        raise RuntimeError(
            "Fewer than two Diviner nighttime ST maps were read; "
            "cannot calculate a meaningful nighttime range."
        )

    stack = np.stack(night_maps, axis=0)
    with np.errstate(all="ignore"):
        tmin = np.nanmin(stack, axis=0)
        tmax = np.nanmax(stack, axis=0)
    span = tmax - tmin
    span[~np.isfinite(tmin) | ~np.isfinite(tmax)] = np.nan

    write_geotiff(
        OUT / "nighttime_temperature_range_K.tif",
        span,
        "K (temperature difference)",
        "Diviner nighttime soil-temperature span across available local-time maps",
        DIVINER_L3_JP2_BASE,
        {
            "COVERAGE": "approximately 60N to 60S; NoData outside source coverage",
            "NATIVE_RESOLUTION": "32 pixels/degree; resampled to 16 pixels/degree",
            "METHOD": "pixelwise max minus min across available 19:30-04:30 local-time ST maps",
            "WARNING": "not the full lunar diurnal or seasonal temperature range",
            "MAPS_USED": ",".join(NIGHTTIME_ST_FILES[:len(night_maps)]),
        },
    )
    provenance["nighttime_temperature_range_K"] = {
        "base_url": DIVINER_L3_JP2_BASE,
        "files_attempted": NIGHTTIME_ST_FILES,
        "files_read": len(night_maps),
        "units": "K difference (numerically equal to degrees C difference)",
        "method": "pixelwise maximum minus minimum across available nighttime local-time ST maps",
        "coverage": "60N to 60S; NoData outside source coverage",
        "limitation": "not full lunar day/night or seasonal temperature range",
    }


# ----------------------------- LOLA TOPOGRAPHY -----------------------------

def build_topography(provenance: dict) -> None:
    folder = RAW / "lola"
    jp2_url = LOLA_JP2
    path = download(jp2_url, folder / "ldem_16.jp2")
    for suffix in ("ldem_16_jp2.lbl", "ldem_16_aux.xml"):
        try:
            download(LOLA_JP2_BASE + suffix, folder / suffix)
        except requests.RequestException as exc:
            LOG.warning("LOLA metadata %s not downloaded: %s", suffix, exc)

    dem, tags = read_and_warp_jp2(path, Resampling.bilinear)
    write_geotiff(
        OUT / "topography_m.tif",
        dem,
        "m",
        "LOLA LDEM 16 pixels/degree lunar elevation",
        jp2_url,
        {
            "NATIVE_RESOLUTION": "16 pixels/degree",
            "SOURCE_SCALE_OFFSET_TAGS": json.dumps(tags),
            "UNIT_NOTE": "LOLA elevation is represented in metres; verify label scaling if using alternate product versions",
        },
    )
    provenance["topography_m"] = {
        "url": jp2_url,
        "units": "m",
        "native_resolution": "16 pixels/degree",
        "conversion": "native elevation values retained in metres; GDAL scale/offset applied if present",
    }


# ----------------------------- LAMP FAR-UV -----------------------------

def read_lamp_pds3_img(img_path: Path, hemisphere: str) -> tuple[np.ndarray, rasterio.Affine, str]:
    """
    LAMP PDS3 labels specify 2501x2501 PC_REAL, 240 m/pixel,
    polar stereographic, 80-90 degrees. Read little-endian Float32.
    """
    label_path = img_path.with_suffix(".lbl")
    if not label_path.exists():
        download_with_label(
            LAMP_BRIGHTNESS_BASE + img_path.name, img_path.parent
        )
    label_text = label_path.read_text(errors="replace")
    for required in ("SAMPLE_BITS", "LINE_SAMPLES", "LINES", "MAP_SCALE"):
        if required not in label_text:
            raise RuntimeError(f"Missing {required} in {label_path}")

    # Verified PDS label values for this product family.
    samples = int(re.search(r"LINE_SAMPLES\s*=\s*(\d+)", label_text).group(1))
    lines = int(re.search(r"LINES\s*=\s*(\d+)", label_text).group(1))
    bits = int(re.search(r"SAMPLE_BITS\s*=\s*(\d+)", label_text).group(1))
    if bits != 32:
        raise RuntimeError(f"Unexpected LAMP sample size: {bits} bits")

    arr = np.fromfile(img_path, dtype="<f4")
    if arr.size != samples * lines:
        raise RuntimeError(
            f"Unexpected LAMP IMG size: {arr.size} samples; "
            f"expected {samples * lines}"
        )
    arr = arr.reshape((lines, samples)).astype("float32")
    arr[~np.isfinite(arr)] = np.nan

    scale_match = re.search(
        r"SCALING_FACTOR\\s*=\\s*([-+0-9.eE]+)", label_text,
        flags=re.IGNORECASE
    )
    offset_match = re.search(
        r"\\bOFFSET\\s*=\\s*([-+0-9.eE]+)", label_text,
        flags=re.IGNORECASE
    )
    scale = float(scale_match.group(1)) if scale_match else 1.0
    offset = float(offset_match.group(1)) if offset_match else 0.0
    arr = arr * scale + offset

    # The LAMP label states 240 m/pixel and a 1250-pixel projection offset.
    # This creates a polar stereographic raster centered on the pole.
    pixel_size = 240.0
    offset = 1250.0
    left = (1.0 - offset) * pixel_size
    top = (offset - 1.0) * pixel_size
    transform = from_origin(left, top, pixel_size, pixel_size)

    lat0 = 90 if hemisphere == "north" else -90
    polar_crs = (
        f"+proj=stere +lat_0={lat0} +lat_ts={lat0} +lon_0=0 "
        f"+R={MOON_RADIUS_M} +units=m +no_defs +type=crs"
    )
    return arr, transform, polar_crs


def build_lamp_uv(provenance: dict) -> None:
    """Reproject LAMP north/south Lyman-alpha brightness into global EQC."""
    polar_grids = []
    lamp_dir = RAW / "lamp"
    for hemisphere, filename in LAMP_FILES.items():
        url = LAMP_BRIGHTNESS_BASE + filename
        img_path, lbl_path = download_with_label(url, lamp_dir)
        arr, transform, crs = read_lamp_pds3_img(img_path, hemisphere)
        grid = warp_to_global(arr, transform, crs, Resampling.bilinear)
        polar_grids.append(grid)

    combined = np.full((HEIGHT, WIDTH), np.nan, dtype=np.float32)
    for grid in polar_grids:
        mask = np.isfinite(grid)
        combined[mask] = grid[mask]

    write_geotiff(
        OUT / "far_uv_lya_brightness.tif",
        combined,
        "photons cm-2 s-1 sr-1",
        "LRO LAMP Lyman-alpha far-UV brightness (not UV index or incident irradiance)",
        LAMP_BRIGHTNESS_BASE,
        {
            "WAVELENGTH": "119.57-125.57 nm",
            "COVERAGE": "north and south polar caps, 80 degrees latitude to each pole; NoData elsewhere",
            "NATIVE_RESOLUTION": "240 m/pixel polar stereographic",
            "UNIT_CONVERSION": "PDS label units retained: photons/cm2/s/sr",
        },
    )
    provenance["far_uv_lya_brightness"] = {
        "base_url": LAMP_BRIGHTNESS_BASE,
        "files": list(LAMP_FILES.values()),
        "units": "photons/cm2/s/sr",
        "wavelength_nm": [119.57, 125.57],
        "coverage": "80N-90N and 80S-90S only",
        "limitation": "far-UV brightness, not solar UV irradiance or an Earth UV index",
    }


# ----------------------------- GEOLOGY / BASALT -----------------------------

MARE_BASALT_RE = re.compile(r"\bmare\b|basalt", re.IGNORECASE)


def choose_polygon_layers(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if path.suffix.lower() in (".shp", ".gpkg", ".geojson"):
            files.append(path)
    return files


def lunar_geology_to_eqc(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    USGS map is Moon 2000 / lunar geographic. If CRS metadata is missing,
    only assign lunar lon/lat when coordinates clearly look like degrees.
    """
    if gdf.crs is None:
        bounds = gdf.total_bounds
        if (
            -360 <= bounds[0] <= 360 and -360 <= bounds[2] <= 360
            and -90.1 <= bounds[1] <= 90.1
            and -90.1 <= bounds[3] <= 90.1
        ):
            gdf = gdf.set_crs(LUNAR_GEOG)
        else:
            raise RuntimeError(
                "Geology layer has no CRS and coordinates do not look like "
                "longitude/latitude degrees. Inspect its .prj/metadata."
            )
    try:
        return gdf.to_crs(LUNAR_EQC)
    except Exception as exc:
        bounds = gdf.total_bounds
        if (
            -360 <= bounds[0] <= 360 and -360 <= bounds[2] <= 360
            and -90.1 <= bounds[1] <= 90.1
            and -90.1 <= bounds[3] <= 90.1
        ):
            LOG.warning(
                "Could not transform source CRS (%s); treating coordinate "
                "values as lunar lon/lat degrees based on bounds.", exc
            )
            return gdf.set_crs(LUNAR_GEOG, allow_override=True).to_crs(LUNAR_EQC)
        raise


def build_basalt_products(provenance: dict) -> None:
    zip_path = download(
        USGS_GEOLOGY_ZIP,
        RAW / "usgs" / "Unified_Geologic_Map_of_the_Moon_GIS_v2.zip",
    )
    extract_zip(zip_path, EXTRACTED / "usgs_geology")

    candidate_paths = choose_polygon_layers(EXTRACTED / "usgs_geology")
    if not candidate_paths:
        raise RuntimeError("No polygon GIS files found in the USGS archive.")

    selected = []
    diagnostics = []
    for path in candidate_paths:
        try:
            layer = gpd.read_file(path)
        except Exception as exc:
            LOG.warning("Could not read %s: %s", path, exc)
            continue
        if layer.empty:
            continue

        # Match geological-unit descriptions, symbols, and attributes.
        text_cols = [
            c for c in layer.columns
            if c != layer.geometry.name
            and (
                str(layer[c].dtype) == "object"
                or str(layer[c].dtype).startswith("string")
            )
        ]
        if not text_cols:
            continue

        row_text = layer[text_cols].fillna("").astype(str).agg(" | ".join, axis=1)
        mask = row_text.str.contains(MARE_BASALT_RE, na=False)
        diagnostics.append({
            "file": str(path),
            "rows": int(len(layer)),
            "text_columns": text_cols,
            "matches": int(mask.sum()),
            "sample_values": {
                c: layer[c].dropna().astype(str).unique()[:12].tolist()
                for c in text_cols[:8]
            },
        })
        if mask.any():
            subset = layer.loc[mask].copy()
            subset["source_layer"] = path.name
            selected.append(subset)

    if not selected:
        (ROOT / "geology_attribute_inspection.json").write_text(
            json.dumps(diagnostics, indent=2)
        )
        raise RuntimeError(
            "No attributes explicitly containing 'mare' or 'basalt' were "
            "found. Inspect geology_attribute_inspection.json, then update "
            "MARE_BASALT_RE to match the map's actual unit-description field. "
            "The script deliberately does not guess unit codes."
        )

    merged = gpd.GeoDataFrame(
        pd.concat(selected, ignore_index=True),
        geometry=selected[0].geometry.name,
        crs=selected[0].crs,
    )
    merged_eqc = lunar_geology_to_eqc(merged)
    merged_eqc = merged_eqc[merged_eqc.geometry.notna() & ~merged_eqc.geometry.is_empty]

    # Binary raster: 1 = selected mare/basalt-associated geological unit.
    shapes = [(geom, 1) for geom in merged_eqc.geometry]
    mask = rasterize(
        shapes,
        out_shape=(HEIGHT, WIDTH),
        transform=TARGET_TRANSFORM,
        fill=0,
        dtype="uint8",
        all_touched=False,
    ).astype("float32")

    # GeoJSON is stored in lunar longitude/latitude degrees (Moon sphere).
    merged_ll = merged_eqc.to_crs(LUNAR_GEOG)
    geojson_path = OUT / "basalt_units.geojson"
    geojson_path.parent.mkdir(parents=True, exist_ok=True)
    merged_ll.to_file(geojson_path, driver="GeoJSON")

    write_geotiff(
        OUT / "basalt_presence.tif",
        mask,
        "binary class (1=mare/basalt-associated mapped unit; 0=other)",
        "USGS Unified Geologic Map mare/basalt-associated polygon mask",
        USGS_GEOLOGY_ZIP,
        {
            "CLASS_1": "geological attribute text matched 'mare' or 'basalt'",
            "CLASS_0": "not selected; not proof of basalt absence",
            "POLYGON_FEATURE_COUNT": len(merged_eqc),
            "GEOJSON": str(geojson_path),
            "CAUTION": "geological map proxy; not pixel-level spectral/geochemical confirmation",
        },
    )
    provenance["basalt_presence"] = {
        "url": USGS_GEOLOGY_ZIP,
        "geojson": str(geojson_path),
        "polygon_count": int(len(merged_eqc)),
        "filter": "case-insensitive text match for 'mare' or 'basalt' across string attributes",
        "limitation": "mapped geological proxy, not a geochemical basalt abundance map",
        "layer_diagnostics": diagnostics,
    }


# ----------------------------- MAIN -----------------------------

def main() -> int:
    for folder in (RAW, EXTRACTED, OUT):
        folder.mkdir(parents=True, exist_ok=True)

    provenance = {
        "project": "Lunar Environmental Data Downloader",
        "target": "Moon",
        "grid": {
            "projection": "spherical equirectangular",
            "pixels_per_degree": PPD,
            "width": WIDTH,
            "height": HEIGHT,
            "radius_m": MOON_RADIUS_M,
            "extent": "360 degrees longitude x 180 degrees latitude",
        },
        "scientific_notes": [
            "Global raster dimensions do not imply global source coverage.",
            "Diviner L3 ST source coverage is limited to 60N-60S.",
            "Nighttime temperature range is not the full diurnal range.",
            "LAMP Lyman-alpha brightness is not solar UV irradiance or UV index.",
            "Mare/basalt geological polygons are mapped proxies.",
            "Lunar annual precipitation is not applicable; no precipitation raster.",
        ],
        "products": {},
    }

    tasks = [
        ("Diviner temperature", lambda: build_diviner_products(provenance)),
        ("LOLA topography", lambda: build_topography(provenance)),
        ("LAMP far-UV", lambda: build_lamp_uv(provenance)),
        ("USGS basalt geology", lambda: build_basalt_products(provenance)),
    ]

    failures = []
    for name, task in tasks:
        try:
            LOG.info("=== %s ===", name)
            task()
        except Exception as exc:
            failures.append({"task": name, "error": str(exc)})
            LOG.exception("%s failed", name)

    provenance["failures"] = failures
    provenance_path = ROOT / "provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2))

    LOG.info("Finished. Output directory: %s", OUT.resolve())
    LOG.info("Provenance: %s", provenance_path.resolve())
    if failures:
        LOG.error("Completed with %d task(s) failing: %s", len(failures), failures)
        return 1
    LOG.info("All products completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
