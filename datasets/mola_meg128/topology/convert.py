from pathlib import Path
import re
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.enums import Resampling
from rasterio.warp import reproject

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "database.raw"
OUTPUT_TIFF = BASE_DIR / "database.rect/mosaico_mars_megt_1024.tiff"

# Dimensões exatas de cada tile conforme o seu script de referência
HEIGHT_TILE = 5632
WIDTH_TILE = 11520

# O grid global completo do MEG128 possui 4 blocos de altura e 4 de largura
# Altura total: 5632 * 4 = 22528 (ou 23040 dependendo do espaçamento exato, aqui usaremos o proporcional)
# Largura total: 11520 * 4 = 46080
WIDTH_GLOBAL = 46080
HEIGHT_GLOBAL = 22528

# Dimensões finais desejadas para o GeoTIFF compacto
WIDTH_TARGET = 1024
HEIGHT_TARGET = 512

# Mapeamento das posições dos tiles baseado no sufixo (ex: '00n000', '44n090')
LAT_OFFSETS = {
    "88n": 0,
    "44n": 5632,
    "00n": 11264,
    "44s": 16896,
}

LON_OFFSETS = {
    "000": 0,
    "090": 11520,
    "180": 23040,
    "270": 34560,
}

PATTERN = re.compile(
    r"(megc|megr|megt)(\d{2}[ns]\d{3})hb",
    re.IGNORECASE,
)

def main():
    if not INPUT_DIR.is_dir():
        raise FileNotFoundError(f"Diretório não encontrado: {INPUT_DIR}")

    # Cria a matriz global vazia para a elevação (megt)
    global_grid = np.full((HEIGHT_GLOBAL, WIDTH_GLOBAL), np.nan, dtype=np.float32)

    print("Varrendo e processando os tiles brutos...")
    
    # Varre os arquivos .img na pasta
    for path in INPUT_DIR.glob("*.img"):
        match = PATTERN.fullmatch(path.stem.lower())
        if not match:
            continue

        product, tile = match.groups()
        
        # Focamos no produto de elevação 'megt' (você pode trocar para 'megr' se preferir o raio)
        if product != "megt":
            continue

        lat_key = tile[:3]  # ex: '00n'
        lon_key = tile[3:]  # ex: '000'

        if lat_key not in LAT_OFFSETS or lon_key not in LON_OFFSETS:
            continue

        row_start = LAT_OFFSETS[lat_key]
        col_start = LON_OFFSETS[lon_key]
        row_end = row_start + HEIGHT_TILE
        col_end = col_start + WIDTH_TILE

        expected_size = HEIGHT_TILE * WIDTH_TILE * 2  # 2 bytes por pixel para int16 (megt)

        if path.stat().st_size != expected_size:
            print(f"[AVISO] Tamanho inválido em {path.name}. Ignorando.")
            continue

        print(f"Lendo e posicionando o tile {tile} ({path.name})...")
        
        # Lê o binário exatamente como no seu script de referência
        data = np.fromfile(path, dtype=">i2")
        elevation = data.astype(np.float32).reshape(HEIGHT_TILE, WIDTH_TILE)
        
        # Substitui valores de NoData extremos por NaN
        elevation = np.where(elevation < -10000, np.nan, elevation)

        # Encaixa o tile na matriz global
        global_grid[row_start:row_end, col_start:col_end] = elevation

    print(f"\nRedimensionando mosaico global para o formato compacto ({WIDTH_TARGET}x{HEIGHT_TARGET} desativando ruídos)...")
    
    transform = from_bounds(-180, -90, 180, 90, WIDTH_TARGET, HEIGHT_TARGET)

    with rasterio.open(
        OUTPUT_TIFF,
        "w",
        driver="GTiff",
        height=HEIGHT_TARGET,
        width=WIDTH_TARGET,
        count=1,
        dtype=np.float32,
        nodata=np.nan,
        crs="+proj=latlong +datum=WGS84",
        transform=transform,
    ) as dst:
        
        destination_array = np.full((HEIGHT_TARGET, WIDTH_TARGET), np.nan, dtype=np.float32)

        reproject(
            source=global_grid,
            destination=destination_array,
            src_transform=from_bounds(-180, -90, 180, 90, WIDTH_GLOBAL, HEIGHT_GLOBAL),
            src_crs="+proj=latlong +datum=WGS84",
            dst_transform=transform,
            dst_crs="+proj=latlong +datum=WGS84",
            resampling=Resampling.bilinear
        )

        dst.write(destination_array, 1)

    print(f"\nSucesso! GeoTIFF equiretangular único gerado em: {OUTPUT_TIFF.resolve()}")

if __name__ == "__main__":
    main()