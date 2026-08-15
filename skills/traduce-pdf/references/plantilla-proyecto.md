# Plantilla de arranque de un proyecto nuevo

Elige el camino según el veredicto del triaje (`00_triaje.py`): **A** para PDF digital,
**B/C** para escaneo. Ambos comparten `proyecto.json` (esquema en SKILL.md §proyecto.json).

## Camino A — PDF digital (ligero: solo PyMuPDF)

```bash
mkdir -p "<proyecto>"/{scripts,traduccion/{digital,es},render/paginas,qa}
cp ~/.agents/skills/traduce-pdf/scripts/*.py "<proyecto>/scripts/"
cd "<proyecto>" && python3 -m venv scripts/venv
scripts/venv/bin/pip install pymupdf
```

```bash
V=scripts/venv/bin/python
$V scripts/90_digital.py --extrae 1 10     # bloques con geometría y estilo
$V scripts/90_digital.py --piloto 5 8      # GO/NO-GO: renderiza y MÍRALO
$V scripts/90_digital.py --traduce 1 153   # producción (reanuda solo)
$V scripts/90_digital.py --compone 1 153
$V scripts/96_qa.py                        # barrido: sin-trad, inglés, números, glosario
$V scripts/97_indice.py                    # si hay índice con puntos líder
$V scripts/95_libro.py                     # ensamble + marcadores + compresión
```

Varios PDFs de un mismo producto = un subproyecto por PDF con venv compartido y el MISMO
`traduccion/glosario.tsv` copiado a cada uno.

## Camino B/C — escaneo (OCR + inpainting)

```bash
mkdir -p "<proyecto>"/{scripts,corpus/{img,ocr,render300},traduccion/{en-bloques,es},plantillas/{fuentes/patched,modelos},render/{paginas,salida},qa,muestras}
cp ~/.agents/skills/traduce-pdf/scripts/*.py "<proyecto>/scripts/"
cd "<proyecto>" && python3.13 -m venv scripts/venv
scripts/venv/bin/pip install pyobjc-framework-Vision pyobjc-framework-Quartz weasyprint pikepdf pillow numpy torch
curl -L -o plantillas/modelos/big-lama.pt \
  https://github.com/Sanster/models/releases/download/add_big_lama/big-lama.pt
```

```bash
V=scripts/venv/bin/python
$V scripts/01_catalog.py                 # F0 catálogo + fondos 300 dpi
$V scripts/10_ocr_vision.py --out corpus/ocr   # F1 OCR
$V scripts/11_corpus.py && $V scripts/12_reclassify.py
$V scripts/23_bloques.py                 # bloques por página
$V scripts/20_entidades.py               # F2 candidatos a glosario → curar a mano
$V scripts/35_traduce_ollama.py 6 15     # F3 piloto (GO/NO-GO)
$V scripts/35_traduce_ollama.py 18 37    # F4 producción por capítulo
$V scripts/60_paneles.py 205 240         # fichas de datos, si las hay
$V scripts/71_arte.py 17 57 73           # F5 arte y mapas
$V scripts/50_assemble.py --todas        # F6 ensamble (re-corrible)
```

## Antes de empezar (ambos caminos)

Escribe `proyecto.json` en la raíz y comprueba el modelo: `ollama list` → una llamada de
prueba antes de empezar nada.

## progress.csv (rutas B/C)

Una fila por página: `pdf_page,ocr,trad,fondo,comp,v4,v5`. Es la fuente de verdad de qué
está terminado. `50_assemble.py` sin `--todas` solo mete las páginas con `comp=ok` y
`v4=ok`; con `--todas` mete todo lo que exista (útil para ver borradores).

## Comprobaciones antes de dar por terminado

- [ ] Ruta A: `96_qa.py` limpio (o solo falsos positivos documentados). Rutas B/C:
      `50_assemble.py` reporta «0 páginas siguen en EN».
- [ ] Hoja de contactos revisada VISUALMENTE (prosa, tabla, panel, mapa, arte, título).
- [ ] Detector de huérfanos: 0 reales. Detector de solapes: 0 sustanciales.
- [ ] Índice y numeración de páginas coherentes con el original.
- [ ] Overrides documentados con su motivo (no vacíos).
- [ ] Validación de contenido con Claude aplicada (ver SKILL.md §Ruta A, «Validación
      final») — el QA automático no ve errores de sentido.
- [ ] Aprendizajes retro-portados: SKILL.md/scripts + página `pdf-traduccion-*` en gbrain.
