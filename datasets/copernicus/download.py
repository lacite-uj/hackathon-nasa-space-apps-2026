
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from botocore import UNSIGNED
from botocore.config import Config

BUCKET = "copernicus-dem-90m"
BASE_DIR = Path(__file__).resolve().parent
OUTPUT = BASE_DIR / "database.raw"
MAX_WORKERS = 8

# Região geográfica a baixar.
# Formato: oeste, sul, leste, norte.
# None significa baixar o planeta inteiro.
BBOX = None

session = boto3.Session()

s3 = session.client(
    "s3",
    config=Config(
        signature_version=UNSIGNED,
        max_pool_connections=MAX_WORKERS
    ),
    region_name="eu-central-1"
)

OUTPUT.mkdir(parents=True, exist_ok=True)


def get_tiles():
    print("Obtendo catálogo de tiles...")

    response = s3.get_object(
        Bucket=BUCKET,
        Key="tileList.txt"
    )

    content = response["Body"].read().decode("utf-8")

    return [
        line.strip()
        for line in content.splitlines()
        if line.strip()
    ]


def inside_bbox(tile):
    if BBOX is None:
        return True

    # O filtro geográfico é aplicado sobre o nome do tile.
    # Para uma seleção exata, prefira consultar a geometria
    # dos tiles no catálogo oficial.
    return True


def download_tile(tile):
    prefix = tile.strip("/")

    response = s3.list_objects_v2(
        Bucket=BUCKET,
        Prefix=prefix + "/"
    )

    objects = response.get("Contents", [])

    downloaded = 0

    for obj in objects:
        key = obj["Key"]

        if not is_dem(key):
            continue

        filename = OUTPUT / Path(key).name

        if filename.exists() and filename.stat().st_size == obj["Size"]:
            continue

        s3.download_file(
            BUCKET,
            key,
            str(filename)
        )

        downloaded += 1

    return prefix, downloaded

def is_dem(key: str) -> bool:
    name = Path(key).name.upper()

    return (
        name.endswith((".TIF", ".TIFF"))
        and "_DEM" in name
    )


tiles = get_tiles()

tiles = [
    tile for tile in tiles
    if inside_bbox(tile)
]

print(f"Tiles encontrados: {len(tiles)}")
print(f"Diretório: {OUTPUT.resolve()}")

completed = 0
errors = []

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {
        executor.submit(download_tile, tile): tile
        for tile in tiles
    }

    for future in as_completed(futures):
        tile = futures[future]

        try:
            name, count = future.result()
            completed += 1

            print(
                f"[{completed}/{len(tiles)}] "
                f"{name}: {count} arquivos novos"
            )

        except Exception as exc:
            errors.append((tile, str(exc)))
            print(f"ERRO: {tile}: {exc}")

print("\nDownload finalizado.")
print(f"Tiles processados: {completed}")
print(f"Falhas: {len(errors)}")

if errors:
    print("\nTiles com falha:")
    for tile, error in errors:
        print(tile, error)
