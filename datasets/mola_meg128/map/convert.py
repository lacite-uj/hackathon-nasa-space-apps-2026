from pathlib import Path
import re
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.enums import Resampling
from rasterio.warp import reproject
import matplotlib.pyplot as plt
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "database.raw"
OUTPUT_TIFF = BASE_DIR / "database.rect/mosaico_mars_megr_1024.tiff"
OUTPUT_PNG = BASE_DIR / "database.rect/mars_texture_1024.png"

# Dimensões exatas de cada tile do MEG128
HEIGHT_TILE = 5632
WIDTH_TILE = 11520

WIDTH_GLOBAL = 46080
HEIGHT_GLOBAL = 22528

WIDTH_TARGET = 1024
HEIGHT_TARGET = 512

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

    # Cria a matriz global vazia para o raio planetário ('megr')
    global_grid = np.full((HEIGHT_GLOBAL, WIDTH_GLOBAL), np.nan, dtype=np.float32)

    print("Varrendo e processando os tiles brutos para texturização (megr)...")
    
    for path in INPUT_DIR.glob("*.img"):
        match = PATTERN.fullmatch(path.stem.lower())
        if not match:
            continue

        product, tile = match.groups()
        
        # Focamos no produto 'megr' (raio médio do planeta), ideal para texturas topográficas coloridas
        if product != "megr":
            continue

        lat_key = tile[:3]
        lon_key = tile[3:]

        if lat_key not in LAT_OFFSETS or lon_key not in LON_OFFSETS:
            continue

        row_start = LAT_OFFSETS[lat_key]
        col_start = LON_OFFSETS[lon_key]
        row_end = row_start + HEIGHT_TILE
        col_end = col_start + WIDTH_TILE

        # Megr utiliza int16 (2 bytes por pixel) com tamanho de 129.761.280 bytes por tile
        expected_size = HEIGHT_TILE * WIDTH_TILE * 2

        if path.stat().st_size != expected_size:
            print(f"[AVISO] Tamanho inválido em {path.name}. Ignorando.")
            continue

        print(f"Lendo e posicionando o tile {tile} ({path.name})...")
        
        data = np.fromfile(path, dtype=">i2")
        radius = data.astype(np.float32).reshape(HEIGHT_TILE, WIDTH_TILE)
        
        # Substitui valores inválidos por NaN
        radius = np.where(radius < -10000, np.nan, radius)

        global_grid[row_start:row_end, col_start:col_end] = radius

    print(f"\nRedimensionando mosaico global para o formato compacto ({WIDTH_TARGET}x{HEIGHT_TARGET})...")
    
    transform = from_bounds(-180, -90, 180, 90, WIDTH_TARGET, HEIGHT_TARGET)

    # 1. Gera o TIFF intermediário compactado do raio
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

    print(f"GeoTIFF de raio gerado em: {OUTPUT_TIFF.resolve()}")

    # 2. Converte a matriz de raio em uma textura PNG colorida usando um colormap científico ('terrain')
    print("Aplicando paleta de cores para gerar a textura PNG...")
    
    min_val = np.nanmin(destination_array)
    max_val = np.nanmax(destination_array)
    
    # Normaliza entre 0 e 1
    norm_data = (destination_array - min_val) / (max_val - min_val)
    norm_data = np.nan_to_num(norm_data, nan=0.0)

    # Aplica o colormap do Matplotlib (ex: 'terrain', 'gist_earth' ou 'copper')
    cmap = plt.get_cmap('terrain')
    colored_image = cmap(norm_data) # Retorna RGBA float entre 0 e 1
    
    # Converte para imagem uint8 (0-255) do Pillow
    img_uint8 = (colored_image[:, :, :3] * 255).astype(np.uint8)
    img_pil = Image.fromarray(img_uint8)
    
    OUTPUT_TIFF.parent.mkdir(parents=True, exist_ok=True)
    img_pil.save(OUTPUT_PNG)

    print(f"\nSucesso! Textura colorida do planeta gerada em: {OUTPUT_PNG.resolve()}")

if __name__ == "__main__":
    main()