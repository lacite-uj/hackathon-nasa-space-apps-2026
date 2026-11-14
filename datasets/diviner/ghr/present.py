from pathlib import Path

import numpy as np
import rasterio
import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent

SOURCE = BASE_DIR / "database.geo"
OUTPUT = BASE_DIR / "database.preview"

OUTPUT.mkdir(parents=True, exist_ok=True)


def visualize(path):

    print("\n" + "=" * 65)
    print(path.name)
    print("=" * 65)

    with rasterio.open(path) as src:

        data = src.read(1).astype(np.float32)

        print("CRS:", src.crs)
        print("Dimensões:", src.width, src.height)
        print("NoData:", src.nodata)

        # Máscara de pixels válidos.
        valid_mask = np.isfinite(data)

        if src.nodata is not None:
            valid_mask &= data != src.nodata

        print("Pixels válidos:", valid_mask.sum())
        print("Pixels inválidos:", (~valid_mask).sum())

        valid = data[valid_mask]

        if not valid.size:
            print("[SKIP] Nenhum pixel válido.")
            return

        print("Mínimo:", valid.min())
        print("Máximo:", valid.max())

        percentiles = np.percentile(
            valid,
            [1, 5, 25, 50, 75, 95, 99]
        )

        print("Percentis:", percentiles)

        low, high = np.percentile(valid, [2, 98])

        # Converte pixels inválidos em NaN para visualização.
        display_data = data.copy()
        display_data[~valid_mask] = np.nan

        fig, ax = plt.subplots(figsize=(16, 8))

        image = ax.imshow(
            display_data,
            cmap="inferno",
            vmin=low,
            vmax=high,
            extent=(-180, 180, -90, 90),
            origin="upper"
        )

        fig.colorbar(
            image,
            ax=ax,
            label="Temperatura de brilho (K)"
        )

        ax.set_title(path.stem)
        ax.set_xlabel("Longitude (graus)")
        ax.set_ylabel("Latitude (graus)")

        ax.set_xticks(np.arange(-180, 181, 30))
        ax.set_yticks(np.arange(-90, 91, 15))

        ax.grid(alpha=0.2)

        fig.tight_layout()

        output_path = OUTPUT / f"{path.stem}.png"

        fig.savefig(
            output_path,
            dpi=150,
            bbox_inches="tight"
        )

        print("[OK] Imagem salva:", output_path)

        plt.close(fig)


def main():

    files = sorted(SOURCE.rglob("*.tif"))

    print(f"Arquivos encontrados: {len(files)}")

    if not files:
        print("Nenhum GeoTIFF encontrado.")
        return

    successful = 0
    failed = 0

    for index, path in enumerate(files, 1):

        print(f"\n[{index}/{len(files)}]")

        try:
            visualize(path)
            successful += 1

        except Exception as error:
            print("[ERROR]", error)
            failed += 1

    print("\n" + "=" * 65)
    print("VISUALIZAÇÃO FINALIZADA")
    print("=" * 65)
    print("Sucesso:", successful)
    print("Falhas:", failed)
    print("Saída:", OUTPUT)


if __name__ == "__main__":
    main()
