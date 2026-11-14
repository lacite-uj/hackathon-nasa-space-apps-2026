
#!/usr/bin/env python3

import argparse
import re
import sys

from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from html.parser import HTMLParser


BASE_URL = (
    "https://pds-geosciences.wustl.edu/lro/"
    "urn-nasa-pds-lro_diviner_derived1/"
    "data_derived_gdr_l2/{year}/cylindrical/jp2/"
)

RESOLUTIONS = ["001", "004", "016", "064", "128"]

PRODUCTS = [
    "TB3", "TB4", "TB5", "TB6", "TB7", "TB8", "TB9",
    "VB1", "VB2", "JD", "LTIM",
]

CHUNK_SIZE = 64 * 1024
BAR_WIDTH = 30


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return

        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value)


def format_size(size):
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{value:.1f} TB"


def progress_bar(current, total, width=BAR_WIDTH):
    if total > 0:
        ratio = min(current / total, 1.0)
    else:
        ratio = 0.0

    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)

    return f"[{bar}] {ratio * 100:6.2f}%"


def fetch(url):
    request = Request(
        url,
        headers={
            "User-Agent": "Diviner-GDR-Downloader/1.0"
        },
    )

    with urlopen(request, timeout=60) as response:
        return response.read()


def list_remote_files(url):
    html = fetch(url).decode("utf-8", errors="replace")

    parser = LinkParser()
    parser.feed(html)

    return sorted({
        link.rsplit("/", 1)[-1]
        for link in parser.links
        if link.rsplit("/", 1)[-1]
    })


def download_file(url, destination, file_index, file_count):
    destination = Path(destination)

    if destination.exists() and destination.stat().st_size > 0:
        print(
            f"\n[{file_index}/{file_count}] "
            f"[SKIP] {destination.name}"
        )
        return True

    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary = destination.with_suffix(
        destination.suffix + ".part"
    )

    try:
        request = Request(
            url,
            headers={
                "User-Agent": "Diviner-GDR-Downloader/1.0"
            },
        )

        with urlopen(request, timeout=120) as response:
            total = int(
                response.headers.get("Content-Length", 0)
            )

            downloaded = 0

            print(
                f"\n[{file_index}/{file_count}] "
                f"{destination.name}"
            )

            with open(temporary, "wb") as output:
                while True:
                    chunk = response.read(CHUNK_SIZE)

                    if not chunk:
                        break

                    output.write(chunk)
                    downloaded += len(chunk)

                    bar = progress_bar(downloaded, total)

                    size_text = format_size(downloaded)

                    if total > 0:
                        size_text += f" / {format_size(total)}"

                    print(
                        f"\r  {bar}  {size_text}",
                        end="",
                        flush=True,
                    )

        temporary.replace(destination)

        print(
            f"\r  {progress_bar(1, 1)}  "
            f"{format_size(downloaded)}"
        )

        return True

    except Exception as error:
        temporary.unlink(missing_ok=True)

        print(
            f"\n  [ERROR] {destination.name}: {error}"
        )

        return False


def main():
    parser = argparse.ArgumentParser(
        description="Downloader NASA PDS - Diviner GDR Level 2"
    )

    parser.add_argument(
        "--year",
        type=int,
        default=2015,
        help="Ano do diretório PDS (padrão: 2015)",
    )

    parser.add_argument(
        "--product",
        type=str.upper,
        default="TB9",
        choices=PRODUCTS,
        help="Produto Diviner (padrão: TB9)",
    )

    parser.add_argument(
        "--resolution",
        type=str,
        default="001",
        choices=RESOLUTIONS,
        help="Resolução em pixels/grau (padrão: 001)",
    )

    parser.add_argument(
        "--period",
        choices=["both", "day", "night"],
        default="both",
        help="Período de observação (padrão: both)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "database.out",
        help="Diretório de destino",
    )

    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Não baixar arquivos LBL",
    )

    args = parser.parse_args()

    base_url = BASE_URL.format(year=args.year)

    print("=" * 65)
    print("NASA PDS - DIVINER GDR LEVEL 2 DOWNLOADER")
    print("=" * 65)

    print(f"Produto:   {args.product}")
    print(f"Resolução: {args.resolution} pixels/grau")
    print(f"Período:   {args.period}")
    print(f"Ano:       {args.year}")
    print(f"Destino:   {args.output.resolve()}")
    print("=" * 65)

    print("\nConsultando índice do PDS...")

    try:
        remote_files = list_remote_files(base_url)
    except Exception as error:
        sys.exit(f"Erro ao consultar o PDS: {error}")

    product = args.product.lower()
    resolution = args.resolution

    pattern = re.compile(
        rf"^dgdr_{product}_avg_cyl_"
        rf"\d{{8}}[dn]_{resolution}_jp2\.jp2$",
        re.IGNORECASE,
    )

    selected = [
        name for name in remote_files
        if pattern.match(name)
    ]

    if args.period == "day":
        selected = [
            name for name in selected
            if re.search(r"\d{8}d_", name, re.IGNORECASE)
        ]

    elif args.period == "night":
        selected = [
            name for name in selected
            if re.search(r"\d{8}n_", name, re.IGNORECASE)
        ]

    if not selected:
        sys.exit(
            "\nNenhum arquivo encontrado. "
            "Verifique o ano, produto e resolução."
        )

    # Localiza labels correspondentes.
    labels = {
        name.rsplit(".", 1)[0].casefold(): name
        for name in remote_files
        if name.lower().endswith(".lbl")
    }

    files_to_download = []

    for filename in selected:
        files_to_download.append(filename)

        if not args.no_labels:
            label = labels.get(
                filename.rsplit(".", 1)[0].casefold()
            )

            if label:
                files_to_download.append(label)
            else:
                print(
                    f"[WARN] Label não encontrado: {filename}"
                )

    destination = (
        args.output
        / product
        / resolution
        / str(args.year)
    )

    print(f"\nArquivos JP2 encontrados: {len(selected)}")
    print(f"Total de arquivos:         {len(files_to_download)}")
    print(f"Diretório:                 {destination.resolve()}")

    print("\nIniciando downloads...\n")

    successful = 0
    failed = 0

    total_files = len(files_to_download)

    for index, filename in enumerate(files_to_download, 1):
        url = urljoin(base_url, filename)
        path = destination / filename

        if download_file(
            url,
            path,
            index,
            total_files,
        ):
            successful += 1
        else:
            failed += 1

    print("\n" + "=" * 65)
    print("DOWNLOAD FINALIZADO")
    print("=" * 65)

    print(f"Concluídos: {successful}")
    print(f"Falharam:   {failed}")
    print(f"Total:      {total_files}")
    print(f"Destino:    {destination.resolve()}")
    print("=" * 65)


if __name__ == "__main__":
    main()
