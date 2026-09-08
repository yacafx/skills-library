# Plantilla de arranque de un proyecto nuevo

Elige el camino según el veredicto del triaje (`00_triaje.py`): **A** para PDF digital,
**B/C** para escaneo. Ambos usan `project.json` (contrato en `docs/project-schema.md`
del motor central); `proyecto.json` es un contrato legacy aceptado por el adaptador.

## Camino A — PDF digital (ligero: solo PyMuPDF)

```bash
traduce-pdf init "/ruta/al/original.pdf" --project "<proyecto>" \
  --title "Nombre del libro" --profile digital
traduce-pdf run triage --project "<proyecto>"
traduce-pdf preflight --project "<proyecto>"
# Resuelve templates/fonts/font-policy.json y vuelve a ejecutar preflight.
traduce-pdf doctor --project "<proyecto>"
```

```bash
traduce-pdf run extract --project "<proyecto>" -- 1 10
traduce-pdf run pilot --project "<proyecto>" -- 5 8      # GO/NO-GO: renderiza y MÍRALO
traduce-pdf run translate --project "<proyecto>" -- 1 153
traduce-pdf run compose --project "<proyecto>" -- 1 153
traduce-pdf run qa --project "<proyecto>"
traduce-pdf run index --project "<proyecto>"              # si hay índice
traduce-pdf run build --project "<proyecto>"
```

Varios PDFs de un mismo producto = un subproyecto por PDF, todos con el motor central y el
MISMO `traduccion/glosario.tsv` gestionado como recurso editorial compartido.

## Camino B/C — escaneo (OCR + inpainting)

Instala el perfil pesado una vez desde el repositorio central con
`uv tool install --force --editable '.[digital,scan]'`. Después:

```bash
traduce-pdf init "/ruta/al/original.pdf" --project "<proyecto>" \
  --title "Nombre del libro" --profile scan
traduce-pdf doctor --project "<proyecto>"
```

```bash
traduce-pdf run catalog --project "<proyecto>"             # F0
traduce-pdf run ocr --project "<proyecto>"                 # F1
traduce-pdf run reclassify --project "<proyecto>"
traduce-pdf run blocks --project "<proyecto>"
traduce-pdf run entities --project "<proyecto>"            # F2
traduce-pdf run pilot --project "<proyecto>" -- 6 15       # F3 GO/NO-GO
traduce-pdf run translate --project "<proyecto>" -- 18 37  # F4
traduce-pdf run panels --project "<proyecto>" -- 205 240
traduce-pdf run art --project "<proyecto>" -- 17 57 73     # F5
traduce-pdf run build --project "<proyecto>"               # F6
```

## Antes de empezar (ambos caminos)

Revisa el `project.json` generado y comprueba el modelo: `ollama list` → una llamada de
prueba antes de empezar nada. No crees `scripts/` ni `venv/` para proyectos nuevos.

Antes de traducir, completa la auditoría tipográfica y conecta las decisiones con el
compositor. La disponibilidad de archivos no certifica que se usen al renderizar. Los
escaneos sin fuentes vectoriales necesitan inventario visual manual; el preflight
automático no los certifica.

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
- [ ] Validación total EN↔ES aplicada y registrada en `qa/validacion-total.tsv`
      con cobertura completa (SKILL.md §F7.5) — sin ella `95_libro.py` entrega BORRADOR.
- [ ] Aprendizajes retro-portados: SKILL.md/scripts + página `pdf-traduccion-*` en gbrain.
