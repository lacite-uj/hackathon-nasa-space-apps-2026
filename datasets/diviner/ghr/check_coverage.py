
import numpy as np
import rasterio

path = "datasets/diviner/database.out/tbol_m_eq.tif"

with rasterio.open(path) as src:
    data = src.read(1)

    print("CRS:", src.crs)
    print("Dimensões:", src.width, src.height)
    print("Transform:", src.transform)
    print("Bounds:", src.bounds)
    print("NoData:", src.nodata)

    valid = np.isfinite(data)

    if src.nodata is not None:
        if np.isnan(src.nodata):
            valid &= ~np.isnan(data)
        else:
            valid &= data != src.nodata

    total = data.size
    count = int(valid.sum())

    print("\n--- COBERTURA ---")
    print(f"Pixels totais: {total:,}")
    print(f"Pixels válidos: {count:,}")
    print(f"Pixels inválidos: {total-count:,}")
    print(f"Cobertura: {100*count/total:.2f}%")

    if count:
        values = data[valid]

        print("\n--- VALORES ---")
        print("Mínimo:", values.min())
        print("Máximo:", values.max())
        print("Média:", values.mean())
        print("Percentis:", np.percentile(
            values, [1, 5, 25, 50, 75, 95, 99]
        ))

    print("\n--- COBERTURA POR LATITUDE ---")

    for south in range(-90, 90, 10):
        north = south + 10

        row_start = int((90 - north) / 180 * src.height)
        row_end = int((90 - south) / 180 * src.height)

        row_start = max(0, min(src.height, row_start))
        row_end = max(0, min(src.height, row_end))

        region = valid[row_start:row_end, :]

        percentage = (
            100 * region.sum() / region.size
            if region.size else 0
        )

        print(
            f"{south:>4}° a {north:>4}°: "
            f"{percentage:6.2f}%"
        )
