
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from pathlib import Path
import time

BASE_URL = (
    "https://pds-geosciences.wustl.edu/mgs/"
    "urn-nasa-pds-mgs_mola_topography_derived/meg128/"
)

OUTPUT = Path("database.raw")

# Produtos:
# MEGC = quantidade de observações
# MEGR = raio planetário médio
# MEGT = topografia mediana
PRODUCTS = ("megc", "megr", "megt")

LATITUDES = ("00n", "44n", "44s", "88n")
LONGITUDES = ("000", "090", "180", "270")

EXTENSIONS = ("img", "lbl", "hdr", "xml")

COLLECTION_FILES = (
    "collection_data_meg128.xml",
    "collection_data_meg128_inventory.csv",
)

EXPECTED_SIZES = {
    "megc": 64_880_640,
    "megr": 129_761_280,
    "megt": 129_761_280,
}

OUTPUT.mkdir(parents=True, exist_ok=True)


def download(filename):
    destination = OUTPUT / filename
    temporary = OUTPUT / f"{filename}.part"

    if destination.exists():
        if filename.endswith(".img"):
            product = filename[:4]
            expected = EXPECTED_SIZES.get(product)

            if expected and destination.stat().st_size == expected:
                return filename, "já existe"

        elif destination.stat().st_size > 0:
            return filename, "já existe"

    url = BASE_URL + filename

    for attempt in range(1, 4):
        try:
            with urlopen(url, timeout=60) as response:
                with open(temporary, "wb") as file:
                    while True:
                        chunk = response.read(1024 * 1024)

                        if not chunk:
                            break

                        file.write(chunk)

            size = temporary.stat().st_size

            if filename.endswith(".img"):
                product = filename[:4]
                expected = EXPECTED_SIZES[product]

                if size != expected:
                    raise ValueError(
                        f"Tamanho inválido: {size}, esperado: {expected}"
                    )

            temporary.replace(destination)

            return filename, f"baixado ({size:,} bytes)"

        except HTTPError as error:
            if error.code == 404:
                return filename, "não encontrado (404)"

            message = f"HTTP {error.code}"

        except (URLError, TimeoutError, OSError, ValueError) as error:
            message = str(error)

        temporary.unlink(missing_ok=True)

        if attempt < 3:
            time.sleep(attempt * 2)

    return filename, f"FALHA: {message}"


files = list(COLLECTION_FILES)

for product in PRODUCTS:
    for latitude in LATITUDES:
        for longitude in LONGITUDES:
            prefix = f"{product}{latitude}{longitude}hb"

            for extension in EXTENSIONS:
                files.append(f"{prefix}.{extension}")

print(f"Total de arquivos: {len(files)}")
print(f"Destino: {OUTPUT.resolve()}")
print()

results = []

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {
        executor.submit(download, filename): filename
        for filename in files
    }

    for future in as_completed(futures):
        filename, status = future.result()
        results.append((filename, status))
        print(f"[{status}] {filename}")

print("\nResumo:")
print(f"Arquivos processados: {len(results)}")
print(f"Falhas: {sum(status.startswith('FALHA') for _, status in results)}")
print(f"Não encontrados: {sum('404' in status for _, status in results)}")
print(f"Diretório: {OUTPUT.resolve()}")
