"""Minimal XLSX sheet reader that ignores a broken workbook dimension.

Official USDA CNPP archives declare ``<dimension ref="A1"/>`` while storing
thousands of data rows. openpyxl read-only therefore returns only the header
cell. This reader walks worksheet XML and shared strings directly.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
CELL_REF = re.compile(r"^([A-Z]+)(\d+)$")


def _col_index(col_letters: str) -> int:
    n = 0
    for ch in col_letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    out: list[str] = []
    for si in root.findall("m:si", NS):
        texts = [t.text or "" for t in si.findall(".//m:t", NS)]
        out.append("".join(texts))
    return out


def _sheet_targets(archive: zipfile.ZipFile) -> list[str]:
    names = archive.namelist()
    return sorted(n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))


def iter_xlsx_rows(path: Path, *, sheet_index: int | None = None) -> list[list[object]]:
    """Return all rows from one worksheet as lists of cell values."""
    with zipfile.ZipFile(path) as archive:
        strings = _shared_strings(archive)
        sheets = _sheet_targets(archive)
        if not sheets:
            raise ValueError(f"No worksheets in {path}")
        target = sheets[sheet_index] if sheet_index is not None else sheets[-1]
        root = ET.fromstring(archive.read(target))
        rows_out: list[list[object]] = []
        for row_el in root.findall("m:sheetData/m:row", NS):
            cells: dict[int, object] = {}
            max_idx = -1
            for cell in row_el.findall("m:c", NS):
                ref = cell.get("r") or ""
                match = CELL_REF.match(ref)
                if not match:
                    continue
                idx = _col_index(match.group(1))
                max_idx = max(max_idx, idx)
                cell_type = cell.get("t")
                value_el = cell.find("m:v", NS)
                raw = value_el.text if value_el is not None and value_el.text is not None else ""
                if cell_type == "s":
                    try:
                        cells[idx] = strings[int(raw)]
                    except (ValueError, IndexError):
                        cells[idx] = raw
                elif cell_type == "b":
                    cells[idx] = raw == "1"
                elif raw == "":
                    cells[idx] = None
                else:
                    try:
                        if "." in raw or "e" in raw.lower():
                            cells[idx] = float(raw)
                        else:
                            cells[idx] = int(raw)
                    except ValueError:
                        cells[idx] = raw
            if max_idx < 0:
                rows_out.append([])
                continue
            rows_out.append([cells.get(i) for i in range(max_idx + 1)])
        return rows_out


def rows_as_dicts(path: Path, *, sheet_index: int | None = None) -> list[dict[str, object]]:
    rows = iter_xlsx_rows(path, sheet_index=sheet_index)
    if not rows:
        return []
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    out: list[dict[str, object]] = []
    for row in rows[1:]:
        record: dict[str, object] = {}
        for i, header in enumerate(headers):
            if not header:
                continue
            record[header] = row[i] if i < len(row) else None
        if any(v not in (None, "") for v in record.values()):
            out.append(record)
    return out
