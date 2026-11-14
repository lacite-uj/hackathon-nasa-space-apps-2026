from pathlib import Path
import numpy as np
import rasterio
from PIL import Image

# Caminhos dos arquivos
BASE_DIR = Path(__file__).resolve().parent
INPUT_TIFF = BASE_DIR / "database.rect/mosaico_mars_megt_1024.tiff"
OUTPUT_PNG = BASE_DIR / "database.rect/mars_heightmap_1024.png"

if not INPUT_TIFF.exists():
    raise FileNotFoundError(f"Arquivo TIFF não encontrado: {INPUT_TIFF}")

print("Lendo o GeoTIFF...")
with rasterio.open(INPUT_TIFF) as src:
    # Lê a única banda do raster
    data = src.read(1)

# Trata os valores NaN (vazios/sem dado) substituindo pelo valor mínimo encontrado ou zero
min_val = np.nanmin(data)
max_val = np.nanmax(data)

print(f"Elevação mínima: {min_val:.2f} m | Elevação máxima: {max_val:.2f} m")

# Substitui NaNs por 0 (ou pelo valor mínimo) para evitar erros na imagem
data_clean = np.nan_to_num(data, nan=min_val)

# Normaliza os dados para a faixa de 0 a 1
normalized = (data_clean - min_val) / (max_val - min_val)

# Convertendo para 16 bits (0 a 65535) para reter muito mais detalhes de relevo do que um PNG de 8 bits
heightmap_16bit = (normalized * 65535).astype(np.uint16)

# Salvando como imagem PNG utilizando a biblioteca Pillow
print(f"Salvando o heightmap PNG em: {OUTPUT_PNG.resolve()}...")
img = Image.fromarray(heightmap_16bit)
img.save(OUTPUT_PNG)

print("Conversão concluída com sucesso!")
