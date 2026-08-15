#!/usr/bin/env python3
"""00_triaje.py — PRIMER paso, antes de cualquier otra cosa: ¿qué clase de PDF es?

De la respuesta depende TODA la estrategia. Nunca arranques el pipeline de parcheo
sin correr esto: si el PDF es digital, ese camino desperdicia calidad y trabajo.

Uso: venv/bin/python 00_triaje.py [ruta.pdf]   (sin argumento usa proyecto.json)

Veredictos posibles:
  DIGITAL   texto vectorial + fuentes embebidas  → ruta A (reemplazo in-place)
  HIBRIDO   escaneo CON capa de texto utilizable → ruta B (capa como insumo, raster)
  ESCANEO   imagen por página, sin texto fiable  → ruta C (OCR + parcheo por página)
"""
import json, re, subprocess, sys
from collections import Counter
from pathlib import Path

SC = Path(__file__).resolve().parent
sys.path.insert(0, str(SC))
PDF = sys.argv[1] if len(sys.argv) > 1 else None
if not PDF:
    try:
        import _proyecto
        PDF = str(_proyecto.pdf_origen())
    except Exception:
        PDF = None
if not PDF:
    raise SystemExit("uso: 00_triaje.py <archivo.pdf>   (o define pdf_origen en proyecto.json)")


def corre(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def paginas():
    info = corre(["pdfinfo", PDF])
    mo = re.search(r"Pages:\s+(\d+)", info)
    return int(mo.group(1)) if mo else 0


def muestra(n_total, k=8):
    """páginas repartidas por el libro, saltando portada y guardas"""
    ini = min(4, n_total)
    paso = max(1, (n_total - ini) // k)
    return list(range(ini, n_total + 1, paso))[:k]


def analiza():
    n = paginas()
    if not n:
        raise SystemExit("no pude leer el PDF (¿existe? ¿poppler instalado?)")
    pags = [p for p in muestra(n) if p <= n]
    fuentes_emb, con_texto, palabras, img_full, ocr_sucio = 0, 0, [], 0, 0
    for p in pags:
        # 1) ¿fuentes embebidas en esa página?
        f = corre(["pdffonts", "-f", str(p), "-l", str(p), PDF])
        filas = [l for l in f.splitlines()[2:] if l.strip()]
        emb = [l for l in filas if re.search(r"\b(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+", l)
               and re.search(r"\b(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+", l).group(1) == "yes"]
        if emb:
            fuentes_emb += 1
        # 2) ¿texto extraíble y de qué calidad?
        t = corre(["pdftotext", "-f", str(p), "-l", str(p), "-enc", "UTF-8", PDF, "-"])
        w = len(t.split())
        palabras.append(w)
        if w > 40:
            con_texto += 1
            # basura típica de OCR: caracteres sueltos raros, mezclas letra/dígito
            raro = len(re.findall(r"[|¬~^`]|[a-z]\d[a-z]|\b[Il1]{2,}\b", t))
            if raro > w * 0.02:
                ocr_sucio += 1
        # 3) ¿una sola imagen que cubre la página? (firma de escaneo)
        im = corre(["pdfimages", "-list", "-f", str(p), "-l", str(p), PDF])
        filas_im = [l for l in im.splitlines()[2:] if l.strip()]
        if len(filas_im) == 1 and re.search(r"\bimage\b", filas_im[0]):
            img_full += 1
    k = len(pags)
    med_palabras = sorted(palabras)[k // 2]
    # La señal decisiva es SI EL TEXTO ES VECTORIAL (fuentes embebidas), no si hay
    # imágenes: un PDF de diseño lleva arte a sangre CON texto vectorial encima.
    hay_fuentes = fuentes_emb >= k * 0.7
    hay_texto = con_texto >= k * 0.5
    if hay_fuentes:
        veredicto = "DIGITAL"
    elif con_texto >= k * 0.5:
        veredicto = "HIBRIDO"      # escaneo con capa OCR encima
    else:
        veredicto = "ESCANEO"      # imagen pura, sin texto aprovechable
    avisos = []
    if hay_fuentes and not hay_texto:
        avisos.append("hay fuentes embebidas pero poco texto extraíble: puede que el texto "
                      "esté convertido a curvas, o que el libro sea muy visual. Extrae 2 páginas "
                      "y compruébalo antes de elegir ruta.")
    if img_full >= k * 0.7 and hay_fuentes:
        avisos.append("páginas con imagen a sangre + texto vectorial: al reinsertar, respeta el "
                      "orden de capas (el arte va debajo).")
    if ocr_sucio >= k * 0.3:
        avisos.append("la capa de texto trae ruido de OCR: probablemente convenga re-OCR.")
    return {
        "pdf": PDF, "paginas": n, "muestreadas": pags,
        "paginas_con_fuentes_embebidas": f"{fuentes_emb}/{k}",
        "paginas_con_texto_extraible": f"{con_texto}/{k}",
        "palabras_medianas_por_pagina": med_palabras,
        "paginas_imagen_unica": f"{img_full}/{k}",
        "capa_texto_con_ruido_ocr": f"{ocr_sucio}/{k}",
        "veredicto": veredicto, "avisos": avisos,
    }


RUTAS = {
    "DIGITAL": """RUTA A — reemplazo in-place (NO uses el parcheo por página)
  El PDF trae texto vectorial y fuentes reales. Ventajas frente al parcheo: texto
  seleccionable y buscable, nitidez vectorial, archivo ligero, cero errores de OCR,
  cero inpainting. Camino: extraer spans con posición y estilo (PyMuPDF), traducir con
  el modelo local, borrar el span original y reinsertar el traducido en la misma caja
  con la fuente embebida (o una sustituta métricamente compatible).
  AVISO: esta ruta está diseñada pero NO ejercitada de punta a punta en un libro
  completo. Valida con 2 páginas y enséñaselas al usuario antes de seguir.
  Cuidado: fuentes con subconjunto de glifos pueden no tener acentos → comprobar
  antes de reinsertar, y sustituir la fuente si falta algún glifo del idioma destino.""",
    "HIBRIDO": """RUTA B — capa de texto como insumo, composición raster
  Hay texto extraíble pero con ruido de OCR o sin fuentes utilizables. Usa la capa
  existente para ahorrarte el OCR (verificando su calidad), pero compón como en la
  ruta C. Si el ruido es alto, re-OCR con Vision sale más barato que limpiarla.""",
    "ESCANEO": """RUTA C — OCR + parcheo por página (la ruta probada para escaneos)
  Imagen por página sin texto fiable. Sigue el pipeline completo del SKILL.md:
  F0 catálogo → F1 OCR Vision → F2 glosario → F3 piloto → F4 producción → F5 arte
  → F6 ensamble → F7 QA.""",
}

if __name__ == "__main__":
    r = analiza()
    print(json.dumps({k: v for k, v in r.items() if k not in ("veredicto", "avisos")}, ensure_ascii=False, indent=1))
    print(f"\n▶ VEREDICTO: {r['veredicto']}\n")
    for a in r.get("avisos", []):
        print(f"  ⚠ {a}")
    print(RUTAS[r["veredicto"]])
    salida = SC.parent / "qa" / "triaje.json"
    if salida.parent.exists():
        salida.write_text(json.dumps(r, ensure_ascii=False, indent=1))
        print(f"\n(guardado en {salida})")
