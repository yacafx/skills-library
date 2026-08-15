#!/usr/bin/env python3
"""50_assemble.py — F6: ensambla el PDF final ES a partir del original + páginas compuestas.

Toma el PDF original y sustituye cada página que ya tenga render ES limpio
(render/paginas/pag-NNN.pdf, filtrado por progress.csv comp=ok y v4=ok).
Las páginas sin traducir pasan tal cual → siempre produce un híbrido usable;
re-correr el script tras cada tanda de 35_traduce_ollama.py lo va completando.

Salidas en render/salida/:
  <título ES> - maestro.pdf   fiel, 300 dpi (imprimir)
  <título ES> - digital.pdf   JPEG re-muestreado (~150 dpi q78, tablet/lectura)

Uso:
  venv/bin/python 50_assemble.py                  # ambas salidas
  venv/bin/python 50_assemble.py --sin-digital    # solo maestro
  venv/bin/python 50_assemble.py --todas          # usar todo render existente (ignora progress.csv)
  venv/bin/python 50_assemble.py --dpi 120 --calidad 70
"""
import argparse, csv, io, json, re
from pathlib import Path

import pikepdf
from pikepdf import Name, OutlineItem
from PIL import Image

P = Path(__file__).resolve().parent.parent
import _proyecto
ORIGINAL = _proyecto.pdf_origen()
RENDER = P / "render" / "paginas"
SALIDA = P / "render" / "salida"

# estructura del libro (página PDF 1-based, prefijo del marcador)
SECCIONES = _proyecto.secciones()


def limpia(t):
    return re.sub(r"\s+", " ", t.replace("‹sc›", "").replace("‹/sc›", "").replace("⏎", " ").replace("*", "")).strip()


def titulo_es(pg):
    """Título del capítulo desde la traducción (bloques type=titulo del dump)."""
    try:
        dump = json.loads((P / "traduccion" / "en-bloques" / f"pag-{pg:03d}.json").read_text())
        es = json.loads((P / "traduccion" / "es" / f"pag-{pg:03d}.json").read_text())
    except FileNotFoundError:
        return None
    partes = []
    for b in dump["blocks"]:
        if b["type"] != "titulo":
            continue
        v = es.get(b["id"])
        if isinstance(v, dict):
            v = v.get("t", "")
        if isinstance(v, str) and v not in ("~", ""):
            partes.append(limpia(v))
    return " ".join(partes) or None


def paginas_listas(todas):
    ok = set()
    if todas:
        for f in RENDER.glob("pag-*.pdf"):
            ok.add(int(f.stem.split("-")[1]))
        return ok
    for r in list(csv.reader(open(P / "progress.csv")))[1:]:
        if r and r[0].isdigit() and r[4] == "ok" and r[5] == "ok":
            if (RENDER / f"pag-{int(r[0]):03d}.pdf").exists():
                ok.add(int(r[0]))
    return ok


def ensambla(listas):
    pdf = pikepdf.open(ORIGINAL)
    abiertos, avisos = [], []
    for pg in sorted(listas):
        src = pikepdf.open(RENDER / f"pag-{pg:03d}.pdf")
        abiertos.append(src)
        a, b = pdf.pages[pg - 1].mediabox, src.pages[0].mediabox
        wa, ha = float(a[2]) - float(a[0]), float(a[3]) - float(a[1])
        wb, hb = float(b[2]) - float(b[0]), float(b[3]) - float(b[1])
        if abs(wa - wb) > 2 or abs(ha - hb) > 2:
            avisos.append(f"  ⚠ p{pg}: tamaño difiere original={wa:.1f}×{ha:.1f} es={wb:.1f}×{hb:.1f}")
        pdf.pages[pg - 1] = src.pages[0]
    with pdf.open_outline() as outline:
        outline.root.clear()
        for pg, prefijo in SECCIONES:
            t = titulo_es(pg)
            rotulo = f"{prefijo}: {t}" if t and t.upper() != prefijo.upper() else prefijo
            outline.root.append(OutlineItem(rotulo, pg - 1))
    with pdf.open_metadata() as meta:
        meta["dc:title"] = _proyecto.titulo_es()
        meta["dc:language"] = ["es-MX"]
    return pdf, abiertos, avisos


def optimiza(ruta_master, ruta_out, dpi, calidad):
    """Re-muestrea los JPEG grandes (fondos 300 dpi) para la versión digital."""
    pdf = pikepdf.open(ruta_master)
    factor, n = dpi / 300.0, 0
    for page in pdf.pages:
        for _, raw in list(page.images.items()):
            try:
                if raw.get("/SMask") is not None:
                    continue
                im = pikepdf.PdfImage(raw).as_pil_image()
                if im.width < 1200:  # iconos/arte chico: dejar
                    continue
                if im.mode != "RGB":
                    im = im.convert("RGB")
                im = im.resize((max(1, round(im.width * factor)), max(1, round(im.height * factor))), Image.LANCZOS)
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=calidad, optimize=True)
                raw.write(buf.getvalue(), filter=Name.DCTDecode)
                raw.Width, raw.Height = im.width, im.height
                raw.ColorSpace, raw.BitsPerComponent = Name.DeviceRGB, 8
                for k in ("/DecodeParms", "/Decode"):
                    if k in raw:
                        del raw[k]
                n += 1
            except Exception as e:
                print(f"  ⚠ imagen sin optimizar en pág {page.index + 1}: {e}")
    pdf.save(ruta_out, linearize=True, compress_streams=True,
             object_stream_mode=pikepdf.ObjectStreamMode.generate)
    pdf.close()
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--todas", action="store_true", help="usar cualquier render existente, sin filtrar por progress.csv")
    ap.add_argument("--sin-digital", action="store_true")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--calidad", type=int, default=78)
    a = ap.parse_args()

    SALIDA.mkdir(parents=True, exist_ok=True)
    listas = paginas_listas(a.todas)
    total = len(pikepdf.open(ORIGINAL).pages)
    print(f"páginas ES a insertar: {len(listas)}/{total}")

    pdf, abiertos, avisos = ensambla(listas)
    print("\n".join(avisos) if avisos else "  geometría: todas coinciden")
    maestro = SALIDA / f"{_proyecto.titulo_es()} - maestro.pdf"
    pdf.save(maestro, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
    pdf.close()
    [s.close() for s in abiertos]
    print(f"✓ maestro: {maestro.name} ({maestro.stat().st_size/1e6:.0f} MB)")

    if not a.sin_digital:
        digital = SALIDA / f"{_proyecto.titulo_es()} - digital.pdf"
        n = optimiza(maestro, digital, a.dpi, a.calidad)
        print(f"✓ digital: {digital.name} ({digital.stat().st_size/1e6:.0f} MB, {n} imágenes re-muestreadas a {a.dpi} dpi q{a.calidad})")
    faltan = total - len(listas)
    print(f"híbrido: {faltan} páginas siguen en EN — re-corre este script tras cada tanda de traducción")
