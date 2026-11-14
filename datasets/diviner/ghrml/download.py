
from pathlib import Path
import argparse
import requests
from tqdm import tqdm

BASE_URL = (
    "https://pds-geosciences.wustl.edu/"
    "lro/urn-nasa-pds-lro_diviner_derived1/"
    "data_derived_ghrm/geotiff/"
)

# Diretório onde este script está localizado.
SCRIPT_DIR = Path(__file__).resolve().parent

# Diretório de saída.
OUTPUT_DIR = SCRIPT_DIR / "database.raw"

PRODUCTS = {
    # Temperatura bolométrica
    "tbol_m": "dghrm_tbol_m_70s70n_tif.tif",
    "tbol_sam": "dghrm_tbol_sam_70s70n_tif.tif",
    "tbol_anom": "dghrm_tbol_anom_70s70n_tif.tif",

    # Temperatura do regolito
    "treg_m": "dghrm_treg_m_70s70n_tif.tif",
    "treg_sam": "dghrm_treg_sam_70s70n_tif.tif",
    "treg_anom": "dghrm_treg_anom_70s70n_tif.tif",

    # Temperatura de brilho por canal
    **{
        f"tb{channel}_{variant}":
            f"dghrm_tb{channel}_{variant}_70s70n_tif.tif"
        for channel in range(6, 10)
        for variant in ("m", "sam")
        if not (channel == 6 and variant == "sam")
        and not (channel == 7 and variant == "sam")
        and not (channel == 8 and variant == "sam")
        and not (channel == 9 and variant == "sam")
    },

    # Abundância de rochas
    "rock_abundance": "dghrm_ra_sam_70s70n_tif.tif",
}

def remote_size(session, url):
    response = session.head(
        url,
        timeout=30,
        allow_redirects=True
    )

    response.raise_for_status()

    size = response.headers.get("Content-Length")
    return int(size) if size else None


def download(session, filename):
    url = BASE_URL + filename

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    destination = OUTPUT_DIR / filename
    temporary = destination.with_suffix(
        destination.suffix + ".part"
    )

    expected_size = remote_size(session, url)

    if (
        destination.exists()
        and expected_size is not None
        and destination.stat().st_size == expected_size
    ):
        print(f"[SKIP] Já existe: {filename}")
        return

    downloaded = (
        temporary.stat().st_size
        if temporary.exists()
        else 0
    )

    if expected_size is not None and downloaded > expected_size:
        temporary.unlink()
        downloaded = 0

    headers = {}

    if downloaded:
        headers["Range"] = f"bytes={downloaded}-"

    print(f"\nBaixando: {filename}")

    with session.get(
        url,
        headers=headers,
        stream=True,
        timeout=(30, 180)
    ) as response:

        if response.status_code == 416:
            temporary.unlink(missing_ok=True)
            return download(session, filename)

        response.raise_for_status()

        if downloaded and response.status_code == 206:
            mode = "ab"
        else:
            downloaded = 0
            mode = "wb"

        content_type = response.headers.get(
            "Content-Type", ""
        ).lower()

        if "text/html" in content_type:
            raise RuntimeError(
                f"Servidor retornou HTML em vez do arquivo: {url}"
            )

        total = expected_size

        if total is None:
            content_range = response.headers.get(
                "Content-Range", ""
            )

            if "/" in content_range:
                remote_total = content_range.rsplit("/", 1)[1]

                if remote_total.isdigit():
                    total = int(remote_total)

            if total is None:
                length = response.headers.get("Content-Length")

                if length:
                    total = downloaded + int(length)

        with open(temporary, mode) as file:
            with tqdm(
                total=total,
                initial=downloaded,
                unit="B",
                unit_scale=True,
                desc=filename
            ) as progress:

                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        file.write(chunk)
                        progress.update(len(chunk))

    actual_size = temporary.stat().st_size

    if (
        expected_size is not None
        and actual_size != expected_size
    ):
        raise RuntimeError(
            f"Download incompleto: "
            f"{actual_size} / {expected_size} bytes"
        )

    temporary.replace(destination)

    print(f"[OK] Salvo: {destination}")


def main():
    parser = argparse.ArgumentParser(
        description="Downloader NASA PDS Diviner GHRM"
    )

    parser.add_argument(
        "product",
        nargs="?",
        choices=PRODUCTS.keys(),
        default="tbol_m",
        help="Produto para baixar (padrão: tbol_m)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Baixar todos os produtos"
    )

    args = parser.parse_args()

    selected = (
        list(PRODUCTS.keys())
        if args.all
        else [args.product]
    )

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "LunarResearchDataset/1.0"
        })

        for product in selected:
            filename = PRODUCTS[product]

            try:
                # Baixa o GeoTIFF.
                download(session, filename)

                # Baixa o XML correspondente.
                label = filename.rsplit(".", 1)[0] + ".xml"
                download(session, label)

            except requests.RequestException as error:
                print(f"[ERRO] {product}: {error}")

            except Exception as error:
                print(f"[ERRO] {product}: {error}")

    print("\nProcessamento finalizado.")


if __name__ == "__main__":
    main()
