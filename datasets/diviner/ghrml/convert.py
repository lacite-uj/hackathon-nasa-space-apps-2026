
from pathlib import Path
import argparse
import math

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds


MOON_RADIUS = 1737400

TARGET_CRS = CRS.from_proj4(
    f"+proj=eqc "
    f"+lat_ts=0 "
    f"+lat_0=0 "
    f"+lon_0=0 "
    f"+R={MOON_RADIUS} "
    f"+units=m "
    f"+no_defs"
)

BASE_DIR = Path(__file__).resolve().parent

SOURCE = BASE_DIR / "database.raw" / "dghrm_tbol_m_70s70n_tif.tif"
DESTINATION = BASE_DIR / "database.out" / "tbol_m_eq.tif"


def convert(source, destination, width, height):

    destination.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(source) as src:

        # Extensão global equiretangular lunar.
        half_width = math.pi * MOON_RADIUS
        half_height = math.pi * MOON_RADIUS / 2

        bounds = (
            -half_width,
            -half_height,
            half_width,
            half_height
        )

        transform = from_bounds(
            *bounds,
            width,
            height
        )

        nodata = np.float32(np.nan)

        profile = {
            "driver": "GTiff",
            "width": width,
            "height": height,
            "count": 1,
            "dtype": "float32",
            "crs": TARGET_CRS,
            "transform": transform,
            "nodata": nodata,
            "compress": "DEFLATE"
        }

        with rasterio.open(destination, "w", **profile) as dst:

            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),

                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=np.nan,

                dst_transform=transform,
                dst_crs=TARGET_CRS,
                dst_nodata=nodata,

                resampling=Resampling.bilinear,
                init_dest_nodata=True
            )

            dst.update_tags(**src.tags())

    print(f"[OK] {destination}")
    print(f"Dimensões: {width}x{height}")
    print(f"CRS: {TARGET_CRS}")


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=512)

    args = parser.parse_args()

    convert(
        SOURCE,
        DESTINATION,
        args.width,
        args.height
    )


if __name__ == "__main__":
    main()
