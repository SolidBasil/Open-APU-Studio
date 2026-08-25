"""
smoke_dbf_encoding.py
=======================
Prueba de humo de la corrección del Hallazgo 10: _leer_dbf() probaba
latin-1 primero y cp850 como "fallback" — pero latin-1 (ISO-8859-1)
asigna un carácter a cada uno de los 256 valores de byte posibles, así
que decodificar con latin-1 casi nunca lanza una excepción, incluso en
archivos que en realidad están en cp850 (la codificación real de los DBF
que genera OPUS/Neodata). El resultado: acentos y "ñ" quedaban mal
decodificados en silencio, y el fallback a cp850 casi nunca se
ejecutaba en la práctica.

Este test construye un .dbf real (formato dBase III, sin dependencias
externas para escritura) con un campo de texto codificado en cp850
conteniendo "ñ", "á", "é" — exactamente el caso que fallaba antes — y
confirma que _leer_dbf() ahora lo decodifica correctamente por default.

Uso:
    python3 tests/smoke_dbf_encoding.py
"""
import os
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.importar.importar import _leer_dbf


def _escribir_dbf_minimo(ruta: Path, campo_nombre: str, valores: list[str], encoding: str) -> None:
    """Escribe un .dbf dBase III mínimo con un solo campo de texto (tipo C),
    codificado con `encoding`. Sin dependencias externas — el formato es
    simple y bien documentado, y así el test no depende de que exista una
    librería de escritura de DBF instalada."""
    ancho_campo = 30
    n = len(valores)
    tam_registro = 1 + ancho_campo  # 1 byte de flag de borrado + el campo
    tam_header = 32 + 32 + 1        # header fijo + 1 descriptor de campo + terminador 0x0D

    with open(ruta, "wb") as f:
        # ── Header (32 bytes) ──
        f.write(bytes([0x03]))               # versión dBase III sin memo
        f.write(bytes([24, 1, 1]))            # fecha última actualización (AA MM DD, arbitraria)
        f.write(struct.pack("<I", n))         # número de registros
        f.write(struct.pack("<H", tam_header))
        f.write(struct.pack("<H", tam_registro))
        f.write(b"\x00" * 20)                 # reservado

        # ── Descriptor de campo (32 bytes) ──
        nombre = campo_nombre.encode("ascii")[:10].ljust(11, b"\x00")
        f.write(nombre)
        f.write(b"C")                          # tipo carácter
        f.write(b"\x00" * 4)                   # reservado (dirección en memoria, no usado)
        f.write(bytes([ancho_campo]))          # longitud del campo
        f.write(bytes([0]))                    # decimales
        f.write(b"\x00" * 14)                  # reservado

        f.write(b"\x0D")                       # terminador de header

        # ── Registros ──
        for valor in valores:
            f.write(b" ")  # flag de borrado: espacio = activo
            datos = valor.encode(encoding)
            f.write(datos.ljust(ancho_campo, b" ")[:ancho_campo])

        f.write(b"\x1A")  # marcador de fin de archivo


def main():
    tmp_dir = tempfile.mkdtemp()
    ruta = Path(tmp_dir) / "TEST.DBF"

    # Texto con acentos y ñ — el caso real que falla al mezclar cp850/latin-1.
    valores = ["Instalación eléctrica", "Cimentación", "Baño y cocina", "Año 2026"]
    _escribir_dbf_minimo(ruta, "DESCRIP", valores, encoding="cp850")

    leidos = _leer_dbf(ruta)
    assert len(leidos) == len(valores), f"esperaba {len(valores)} registros, hubo {len(leidos)}"

    descripciones = [r["DESCRIP"].rstrip() for r in leidos]
    assert descripciones == valores, (
        f"el DBF en cp850 no se decodificó correctamente por default.\n"
        f"  esperado: {valores}\n"
        f"  obtenido: {descripciones}"
    )
    print(f"OK: DBF en cp850 decodificado correctamente por default: {descripciones}")

    # ── Verificación de que el bug real (latin-1 primero) sí lo rompía ──
    # Con la codificación vieja (latin-1 primero, que nunca lanza excepción
    # así que "gana" siempre), los bytes cp850 de "ó", "ñ" etc. decodifican
    # a caracteres distintos sin error. Confirmamos que ESE resultado
    # (el bug) es distinto del correcto, para no tener un test que pase
    # "por casualidad" si algún día cp850==latin-1 coincidieran.
    datos_crudos = ruta.read_bytes()
    campo_bytes = datos_crudos[33 + 32 + 1 + 1: 33 + 32 + 1 + 1 + 30]  # primer registro, tras header+flag
    decodificado_mal = campo_bytes.decode("latin-1").rstrip()
    decodificado_bien = campo_bytes.decode("cp850").rstrip()
    assert decodificado_mal != decodificado_bien, \
        "el test no es representativo: cp850 y latin-1 dieron el mismo resultado para estos bytes"
    print(f"OK: confirmado que decodificar con latin-1 daba un resultado distinto (y erróneo): "
          f"{decodificado_mal!r} vs correcto {decodificado_bien!r}")

    # ── Archivo inexistente: sigue devolviendo lista vacía, sin crashear ──
    vacio = _leer_dbf(Path(tmp_dir) / "NOEXISTE.DBF")
    assert vacio == []
    print("OK: archivo inexistente sigue devolviendo [] sin crashear")

    print("\nTODAS LAS PRUEBAS DEL HALLAZGO 10 PASARON")


if __name__ == "__main__":
    main()
