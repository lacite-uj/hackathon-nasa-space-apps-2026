
from pathlib import Path
import re

import numpy as np
import xarray as xr
import zarr

INPUT_DIR = Path("mola_meg128")
OUTPUT_DIR = Path("mars_mola.zarr")

HEIGHT = 5632
WIDTH = 11520

PRODUCTS = {
    "megc": {
        "dtype": np.uint8,
        "name": "observation_count",
    },
    "megr": {
        "dtype": np.dtype(">i2"),
        "name": "radius_m",
    },
    "megt": {
        "dtype": np.dtype(">i2"),
        "name": "elevation_m",
    },
}

PATTERN = re.compile(
    r"(megc|megr|megt)(\d{2}[ns]\d{3})hb",
    re.IGNORECASE,
)


def discover_tiles():
    tiles = {}

    for path in INPUT_DIR.glob("*.img"):
        match = PATTERN.fullmatch(path.stem.lower())

        if not match:
            continue

        product, tile = match.groups()

        tiles.setdefault(tile, {})[product] = path

    return tiles


def read_raster(path: Path, dtype):
    expected_size = HEIGHT * WIDTH * np.dtype(dtype).itemsize

    if path.stat().st_size != expected_size:
        raise ValueError(
            f"Tamanho inválido em {path.name}: "
            f"{path.stat().st_size} bytes; "
            f"esperado: {expected_size}"
        )

    data = np.fromfile(path, dtype=dtype)

    # Converte para tipos nativos para facilitar o processamento.
    if dtype == np.uint8:
        return data.reshape(HEIGHT, WIDTH)

    return data.astype(np.int16).reshape(HEIGHT, WIDTH)


def convert_tile(tile, files):
    print(f"\nProcessando tile {tile}...")

    variables = {}

    # MEGT: elevação mediana em metros.
    if "megt" in files:
        elevation = read_raster(
            files["megt"],
            PRODUCTS["megt"]["dtype"],
        )

        variables["elevation_m"] = (
            ("line", "sample"),
            elevation,
            {
                "long_name": "Median topography",
                "units": "m",
            },
        )

    # MEGR: raio médio com offset de 3.396.000 metros.
    if "megr" in files:
        radius_encoded = read_raster(
            files["megr"],
            PRODUCTS["megr"]["dtype"],
        )

        radius = radius_encoded.astype(np.int32) + 3_396_000

        variables["radius_m"] = (
            ("line", "sample"),
            radius,
            {
                "long_name": "Mean planetary radius",
                "units": "m",
                "encoding_offset_m": 3_396_000,
            },
        )

    # MEGC: quantidade de observações por bin.
    if "megc" in files:
        count = read_raster(
            files["megc"],
            PRODUCTS["megc"]["dtype"],
        )

        variables["observation_count"] = (
            ("line", "sample"),
            count,
            {
                "long_name": "MOLA observations per bin",
                "units": "count",
            },
        )

        variables["observed"] = (
            ("line", "sample"),
            count > 0,
            {
                "long_name": "Bins with direct MOLA observations",
            },
        )

    if not variables:
        return

    dataset = xr.Dataset(
        data_vars=variables,
        coords={
            "line": np.arange(HEIGHT),
            "sample": np.arange(WIDTH),
        },
        attrs={
            "planet": "Mars",
            "mission": "Mars Global Surveyor",
            "instrument": "MOLA",
            "collection": "MEG128",
            "tile": tile,
            "source": "NASA PDS Geosciences Node",
            "coordinate_note": (
                "line and sample are raster indices. "
                "Geographic coordinates must be derived from PDS labels."
            ),
        },
    )

    encoding = {
        name: {
            "chunks": (512, 512),
        }
        for name in dataset.data_vars
    }

    dataset.to_zarr(
        OUTPUT_DIR,
        group=tile,
        mode="a",
        encoding=encoding,
        consolidated=False,
    )

    print(f"  Variáveis: {list(dataset.data_vars)}")
    print(f"  Concluído: {tile}")

    del dataset
    del variables


def main():
    if not INPUT_DIR.is_dir():
        raise FileNotFoundError(
            f"Diretório não encontrado: {INPUT_DIR}"
        )

    if OUTPUT_DIR.exists():
        raise FileExistsError(
            f"{OUTPUT_DIR} já existe. "
            "Use outro nome ou remova o dataset anterior."
        )

    tiles = discover_tiles()

    if not tiles:
        raise RuntimeError("Nenhum tile MOLA encontrado.")

    print(f"Tiles encontrados: {len(tiles)}")

    # Cria o grupo raiz do Zarr.
    zarr.group(
        store=str(OUTPUT_DIR),
        overwrite=True,
    )

    for tile, files in sorted(tiles.items()):
        convert_tile(tile, files)

    # Consolida os metadados para facilitar a leitura.
    zarr.consolidate_metadata(str(OUTPUT_DIR))

    print("\nConversão finalizada!")
    print(f"Dataset: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
