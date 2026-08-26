#!/usr/bin/env python3
"""digital_ligero.py — versión de pantalla a partir del maestro de impresión.

Usa `Document.rewrite_images()` de PyMuPDF, que recomprime en sitio respetando
máscaras y recortes. NO uses `replace_image()` a mano para esto: pierde el SMask y
el arte termina pintado ENCIMA del texto (probado y descartado).

El texto sigue siendo vectorial y seleccionable; solo cambian las imágenes.
Después de generarla, RENDERIZA Y MÍRALA: el QA no ve imágenes.

Uso: digital_ligero.py [dpi] [calidad]
"""
import sys
from pathlib import Path

import fitz

P = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(P / "scripts"))
import _proyecto

DPI = int(sys.argv[1]) if len(sys.argv) > 1 else 150
CALIDAD = int(sys.argv[2]) if len(sys.argv) > 2 else 75

maestro = P / "render" / f"{_proyecto.slug()}-es.pdf"
salida = P / "render" / f"{_proyecto.slug()}-es-digital.pdf"
if not maestro.exists():
    raise SystemExit(f"falta el maestro: {maestro}")

doc = fitz.open(str(maestro))
doc.rewrite_images(dpi_target=DPI, quality=CALIDAD, set_to_gray=False)
doc.subset_fonts()
doc.save(str(salida), deflate=True, deflate_images=True, deflate_fonts=True,
         garbage=4, clean=True)
mb = lambda p: p.stat().st_size / 1e6
print(f"✓ {salida} ({mb(salida):.1f} MB) — maestro {mb(maestro):.1f} MB "
      f"@ {DPI} dpi / q{CALIDAD}")
print("  RENDERIZA Y MÍRALA antes de entregarla.")
