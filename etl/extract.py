"""Extract: lê as planilhas e devolve as tabelas como listas de dicionários, sem interpretar nada.

Usa openpyxl com data_only=True: as células com fórmula trazem o valor que o Excel guardou na última vez
que salvou (o "cache"). Esses valores só são usados para VALIDAR o recálculo, nunca como resultado.
"""
import hashlib
from datetime import datetime

import openpyxl

from . import config
from .text import norm


class Sheet:
    """Envolve uma aba e oferece leitores para o layout comum (cabeçalho na linha 12)."""

    def __init__(self, ws, planilha):
        self.ws = ws
        self.planilha = planilha
        self.name = ws.title

    def cell(self, row, col):
        return self.ws.cell(row=row, column=col).value

    def row_values(self, row):
        return [c.value for c in self.ws[row]]

    @property
    def descricao(self):
        v = self.cell(config.ROW_DESCRICAO, 1)
        return str(v).removeprefix("Descrição:").strip() if v else None

    @property
    def data(self):
        v = self.cell(config.ROW_DATA, 1)
        if not v:
            return None
        s = str(v).removeprefix("Data:").strip()
        try:
            return datetime.strptime(s, "%d/%m/%Y").date().isoformat()
        except ValueError:
            return s

    def table(self, header_row=config.ROW_HEADER, first=None, stop_on_blank=True):
        """Tabela com cabeçalho em `header_row`. Devolve [(número da linha, {cabeçalho: valor})]."""
        header = [h.strip() if isinstance(h, str) else h for h in self.row_values(header_row)]
        out = []
        for r in range(first or header_row + 1, self.ws.max_row + 1):
            vals = self.row_values(r)
            if all(v is None for v in vals):
                if stop_on_blank:
                    break
                continue
            out.append((r, {h: v for h, v in zip(header, vals) if h is not None}))
        return out

    def header(self, row=config.ROW_HEADER):
        return [h for h in self.row_values(row) if h is not None]

    def find_row(self, prefix, col=1):
        """Primeira linha cuja coluna `col` começa com `prefix` (comparação normalizada)."""
        p = norm(prefix)
        for r in range(1, self.ws.max_row + 1):
            v = self.cell(r, col)
            if isinstance(v, str) and norm(v).startswith(p):
                return r
        raise KeyError(f"{self.planilha}/{self.name}: linha começando com {prefix!r} não encontrada")

    def block_table(self, title):
        """Tabela empilhada num bloco: linha de título, cabeçalho na linha seguinte, dados até a linha vazia."""
        return self.table(header_row=self.find_row(title) + 1)

    def text_block(self, title):
        """Linhas de texto (coluna A) logo abaixo de um título, até a próxima linha vazia."""
        r0 = self.find_row(title)
        linhas = []
        for r in range(r0 + 1, self.ws.max_row + 1):
            v = self.cell(r, 1)
            if v is None and all(x is None for x in self.row_values(r)):
                break
            if v is not None:
                linhas.append(str(v).strip())
        return {"titulo": str(self.cell(r0, 1)).strip(), "linhas": linhas, "linha": r0}


class Workbook:
    def __init__(self, planilha_id, path):
        self.id = planilha_id
        self.path = path
        self.wb = openpyxl.load_workbook(path, data_only=True)

    def __getitem__(self, name):
        return Sheet(self.wb[name], self.id)

    @property
    def sheetnames(self):
        return self.wb.sheetnames


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load(raw_dir=config.RAW_DIR):
    """Abre as quatro planilhas. Falha com mensagem clara se faltar alguma."""
    books, arquivos = {}, []
    for pid, meta in config.PLANILHAS.items():
        path = raw_dir / meta["arquivo"]
        if not path.exists():
            raise FileNotFoundError(f"Planilha não encontrada: {path}. Copie os arquivos para {raw_dir}.")
        books[pid] = Workbook(pid, path)
        arquivos.append({"planilha_id": pid, "arquivo": meta["arquivo"], "sha256": sha256(path),
                         "abas": books[pid].sheetnames})
    return books, arquivos
