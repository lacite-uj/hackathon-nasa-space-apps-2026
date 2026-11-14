import numpy as np
import rasterio
import matplotlib.pyplot as plt

path = "datasets/diviner/database.out/tbol_m_eq.tif"

with rasterio.open(path) as src:
    data = src.read(1)
    print("CRS:", src.crs)
    print("Dimensões:", src.width, src.height)
    print("NoData:", src.nodata)
    print("Pixels válidos:", np.isfinite(data).sum())
    print("Pixels inválidos:", (~np.isfinite(data)).sum())

    valid = data[np.isfinite(data)]

    if valid.size:
        print("Mínimo:", valid.min())
        print("Máximo:", valid.max())
        print("Percentis:", np.percentile(valid, [1, 5, 25, 50, 75, 95, 99]))

        low, high = np.percentile(valid, [2, 98])

        plt.figure(figsize=(16, 8))
        plt.imshow(data, cmap="inferno", vmin=low, vmax=high)
        plt.colorbar(label="Temperatura (K)")
        plt.title("Diviner - Bolometric Temperature")
        plt.savefig("diviner_preview.png", dpi=150, bbox_inches="tight")
        plt.show()