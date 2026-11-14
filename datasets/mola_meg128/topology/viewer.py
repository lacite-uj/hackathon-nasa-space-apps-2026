from pathlib import Path
import matplotlib.pyplot as plt
import rasterio

SCRIPT_DIR = Path(__file__).resolve().parent
tiff_path = SCRIPT_DIR / "database.rect/mosaico_mars_megt_1024.tiff"

with rasterio.open(tiff_path) as src:
  image_data = src.read(1)  # Lê a primeira banda

  plt.figure(figsize=(10, 5))
  plt.imshow(image_data, cmap="terrain", extent=[-180, 180, -90, 90])
  plt.colorbar(label="Elevação / Métrica")
  plt.title("Visualização do Mosaico Equiretangular")
  plt.xlabel("Longitude")
  plt.ylabel("Latitude")
  plt.show()