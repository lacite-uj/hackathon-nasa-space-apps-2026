from pathlib import Path
import argparse
import math
import re
import sys

import numpy as np
import rasterio

from rasterio.crs import CRS
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds


MOON_RADIUS = 1737400.0

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

SOURCE = BASE_DIR / "database.out"
DESTINATION = BASE_DIR / "database.geo"

NODATA = np.float32(-9999.0)


def parse_label(label_path):
    """
    Lê os fatores de escala, offset e valores nulos
    definidos no label PDS.
    """

    result = {
        "scale": 1.0,
        "offset": 0.0,
        "null_values": [],
    }

    if not label_path.exists():
        print(f"[WARN] Label ausente: {label_path.name}")
        return result

    content = label_path.read_text(
        encoding="latin-1",
        errors="replace"
    )

    def read_number(field):
        match = re.search(
            rf"^\s*{field}\s*=\s*"
            rf"([-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?)",
            content,
            re.IGNORECASE | re.MULTILINE
        )

        return float(match.group(1)) if match else None

    scale = read_number("SCALING_FACTOR")
    offset = read_number("OFFSET")

    if scale is not None:
        result["scale"] = scale

    if offset is not None:
        result["offset"] = offset

    for field in ("CORE_NULL", "MISSING_CONSTANT"):
        value = read_number(field)

        if value is not None:
            result["null_values"].append(value)

    return result


def read_source(src, label):
    """
    Lê a banda, remove pixels inválidos e aplica
    a escala física definida pelo PDS.
    """

    data = src.read(1).astype(np.float32)

    valid = src.read_masks(1) > 0
    valid &= np.isfinite(data)

    if src.nodata is not None:
        valid &= data != src.nodata

    for null_value in label["null_values"]:
        valid &= data != null_value

    data = data * label["scale"] + label["offset"]

    # TB3-TB9 representam temperaturas de brilho em Kelvin.
    # Valores fora da faixa documentada são considerados inválidos.
    if re.search(r"tb[3-9]", src.name, re.IGNORECASE):
        valid &= (data >= 10.0) & (data <= 450.0)

    data[~valid] = NODATA

    return data


def convert(source, destination, width, height, resampling):
    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    label_path = source.with_suffix(".lbl")
    label = parse_label(label_path)

    with rasterio.open(source) as src:

        if src.crs is None:
            raise ValueError(
                f"JP2 sem CRS reconhecido: {source.name}"
            )

        if src.count < 1:
            raise ValueError("Raster sem bandas.")

        print(f"  Origem: {src.width}x{src.height}")
        print(f"  CRS: {src.crs}")
        print(f"  Escala: {label['scale']}")
        print(f"  Offset: {label['offset']}")

        source_data = read_source(src, label)

        # Extensão global equiretangular lunar.
        half_width = math.pi * MOON_RADIUS
        half_height = math.pi * MOON_RADIUS / 2.0

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

        destination_data = np.full(
            (height, width),
            NODATA,
            dtype=np.float32
        )

        reproject(
            source=source_data,
            destination=destination_data,

            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=NODATA,

            dst_transform=transform,
            dst_crs=TARGET_CRS,
            dst_nodata=NODATA,

            resampling=resampling,
            init_dest_nodata=True
        )

        profile = {
            "driver": "GTiff",
            "width": width,
            "height": height,
            "count": 1,
            "dtype": "float32",
            "crs": TARGET_CRS,
            "transform": transform,
            "nodata": NODATA,
            "compress": "DEFLATE",
            "predictor": 3,
            "tiled": True
        }

        with rasterio.open(
            destination,
            "w",
            **profile
        ) as dst:

            dst.write(destination_data, 1)

            dst.update_tags(
                source_file=source.name,
                source_label=label_path.name,
                scaling_factor=str(label["scale"]),
                offset=str(label["offset"]),
                units="K",
                projection="Moon Equirectangular",
                resampling=resampling.name
            )

    valid_pixels = destination_data != NODATA

    if np.any(valid_pixels):
        values = destination_data[valid_pixels]

        print(
            f"  Valores: {values.min():.2f} "
            f"até {values.max():.2f} K"
        )
    else:
        print("  [WARN] Raster sem pixels válidos.")

    print(f"  [OK] {destination}")


def main():

    parser = argparse.ArgumentParser(
        description="Converte Diviner GDR L2 JP2 para GeoTIFF."
    )

    parser.add_argument(
        "--width",
        type=int,
        default=1024
    )

    parser.add_argument(
        "--height",
        type=int,
        default=512
    )

    parser.add_argument(
        "--resampling",
        choices=["nearest", "bilinear", "cubic"],
        default="bilinear"
    )

    parser.add_argument(
        "--overwrite",
        action="store_true"
    )

    parser.add_argument(
        "--source",
        type=Path,
        default=SOURCE
    )

    parser.add_argument(
        "--destination",
        type=Path,
        default=DESTINATION
    )

    args = parser.parse_args()

    if args.width <= 0 or args.height <= 0:
        parser.error("Width e height precisam ser positivos.")

    methods = {
        "nearest": Resampling.nearest,
        "bilinear": Resampling.bilinear,
        "cubic": Resampling.cubic
    }

    resampling = methods[args.resampling]

    files = sorted(args.source.rglob("*.jp2"))

    if not files:
        sys.exit(f"Nenhum JP2 encontrado em {args.source}")

    print("=" * 65)
    print("DIVINER GDR L2 - JP2 TO GEOTIFF")
    print("=" * 65)
    print(f"Entrada:    {args.source}")
    print(f"Saída:      {args.destination}")
    print(f"Dimensões:  {args.width}x{args.height}")
    print(f"Reamostra:  {args.resampling}")
    print(f"Arquivos:   {len(files)}")
    print("=" * 65)

    successful = 0
    failed = 0
    skipped = 0

    for index, source in enumerate(files, 1):

        relative = source.relative_to(args.source)
        destination = (
            args.destination
            / relative.parent
            / f"{source.stem}.tif"
        )

        print(f"\n[{index}/{len(files)}] {source.name}")

        if destination.exists() and not args.overwrite:
            print("  [SKIP] Já convertido.")
            skipped += 1
            continue

        try:
            convert(
                source,
                destination,
                args.width,
                args.height,
                resampling
            )

            successful += 1

        except Exception as error:
            print(f"  [ERROR] {error}")
            failed += 1

    print("\n" + "=" * 65)
    print("CONVERSÃO FINALIZADA")
    print("=" * 65)
    print(f"Convertidos: {successful}")
    print(f"Ignorados:   {skipped}")
    print(f"Falharam:    {failed}")
    print(f"Total:       {len(files)}")
    print(f"Saída:       {args.destination}")
    print("=" * 65)


if __name__ == "__main__":
    main()
