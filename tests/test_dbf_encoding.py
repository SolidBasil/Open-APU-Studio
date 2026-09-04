"""Pytest para encoding cp850 en DBF — migrado de smoke_dbf_encoding (Hallazgo 10)."""
import struct
from pathlib import Path

from backend.importar.importar import _leer_dbf


def _escribir_dbf_minimo(ruta: Path, campo_nombre: str, valores: list[str], encoding: str) -> None:
    ancho_campo = 30
    n = len(valores)
    tam_registro = 1 + ancho_campo
    tam_header = 32 + 32 + 1

    with open(ruta, "wb") as f:
        f.write(bytes([0x03]))
        f.write(bytes([24, 1, 1]))
        f.write(struct.pack("<I", n))
        f.write(struct.pack("<H", tam_header))
        f.write(struct.pack("<H", tam_registro))
        f.write(b"\x00" * 20)

        nombre = campo_nombre.encode("ascii")[:10].ljust(11, b"\x00")
        f.write(nombre)
        f.write(b"C")
        f.write(b"\x00" * 4)
        f.write(bytes([ancho_campo]))
        f.write(bytes([0]))
        f.write(b"\x00" * 14)

        f.write(b"\x0D")

        for valor in valores:
            f.write(b" ")
            datos = valor.encode(encoding)
            f.write(datos.ljust(ancho_campo, b" ")[:ancho_campo])

        f.write(b"\x1A")


def test_dbf_cp850_por_default(tmp_path):
    ruta = tmp_path / "TEST.DBF"
    valores = ["Instalación eléctrica", "Cimentación", "Baño y cocina", "Año 2026"]
    _escribir_dbf_minimo(ruta, "DESCRIP", valores, encoding="cp850")

    leidos = _leer_dbf(ruta)
    assert len(leidos) == len(valores)
    descripciones = [r["DESCRIP"].rstrip() for r in leidos]
    assert descripciones == valores


def test_latin1_habria_roto(tmp_path):
    ruta = tmp_path / "TEST.DBF"
    _escribir_dbf_minimo(ruta, "DESCRIP", ["Instalación eléctrica"], encoding="cp850")
    datos_crudos = ruta.read_bytes()
    campo_bytes = datos_crudos[33 + 32 + 1 + 1: 33 + 32 + 1 + 1 + 30]
    assert campo_bytes.decode("latin-1").rstrip() != campo_bytes.decode("cp850").rstrip()


def test_archivo_inexistente_vacio(tmp_path):
    assert _leer_dbf(tmp_path / "NOEXISTE.DBF") == []
