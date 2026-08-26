---
name: traduce-pdf
description: Traduce un PDF de libro completo conservando maquetación, tipografía y arte (escaneado o digital), usando OCR + modelo local vía Ollama + recomposición página a página con QA automático; úsalo cuando el usuario pase un PDF y pida versión en otro idioma "igualita al original", o pida retomar/corregir un proyecto de traducción ya iniciado.
metadata:
  short-description: Traduce libros PDF conservando el diseño original
---

# Libro PDF traducido conservando el diseño

Convierte un PDF de libro (típicamente escaneado) a otro idioma manteniendo la misma
maquetación: mismas cajas de texto, tipografía equivalente, arte y mapas intactos,
**paridad de página** (la p87 traducida es la p87 original). Probado end-to-end en un
manual de rol de 258 páginas.

**El texto lo traduce un modelo LOCAL del usuario (Ollama), no tú.** Tú orquestas:
diagnosticas, reparas la maquinaria, adjudicas OCR contra el render y decides. Esta
división no es opcional — traducir un libro entero de corrido es reproducir una obra
protegida. Tú sí puedes: pasajes cortos, encabezados, etiquetas de mapa, tablas
reconstruidas y todo el trabajo de composición.

## Memoria extendida en gbrain (consúltala al arrancar)

La crónica detallada de cada proyecto (qué documento, glosarios curados, decisiones
editoriales, cómo retomarlo) vive en la memoria PRIVADA del usuario en gbrain — este
archivo trae lo crítico; allá está el detalle con contexto:
- `mcp__gbrain__search "pdf traducción"` y `mcp__gbrain__get_page` de las páginas
  `pdf-traduccion-*` — consúltalas al arrancar y antes de decisiones grandes
  (terminología ya curada, trampas por tipo de documento, proyectos retomables).

Si gbrain no está disponible en la sesión, NO te bloquees: este archivo basta para
operar; solo pierdes el detalle histórico.

Al TERMINAR un proyecto: actualiza este SKILL.md + scripts con lo aprendido (capa
ejecutable) y escribe/actualiza una página `pdf-traduccion-*` en gbrain (capa buscable),
enlazándolas entre sí en ambas direcciones. **Regla anti-inflación**: aquí las
capacidades se escriben en presente y sin historial (nada de nombres de proyecto ni
fechas en el cuerpo); la crónica de cada proyecto —qué libro, cuándo, qué salió mal—
vive SOLO en su página de gbrain.

## Quick start

1) **TRIAJE PRIMERO** — `python3 scripts/00_triaje.py <archivo.pdf>`. Nunca arranques el
   pipeline de parcheo sin esto: si el PDF es digital, ese camino desperdicia calidad.
2) Pregunta lo mínimo (§Decisiones) y crea la carpeta del proyecto con `proyecto.json`.
3) Copia `scripts/` del skill a `<proyecto>/scripts/` y crea el venv (§Instalación).
4) F0–F2: catálogo, OCR, glosario. F3: **piloto de 10 páginas** — no sigas sin piloto limpio.
5) F4: producción por tandas de capítulo en segundo plano; repara lo que marque el QA.
6) F5 arte/mapas, F6 ensamble, F7 QA final, **F7.5 validación total EN↔ES (obligatoria,
   §Ruta A — aplica igual en rutas B/C antes de entregar)**. F8 Foundry solo si aplica.

## F-1 — Triaje: ¿qué clase de PDF es? (obligatorio)

`00_triaje.py` muestrea 8 páginas repartidas y mide tres señales: **fuentes embebidas**
(¿el texto es vectorial?), **texto extraíble** y **páginas de imagen única**. La señal
decisiva es la primera: un PDF de diseño puede llevar arte a sangre *con* texto vectorial
encima, y sigue siendo digital.

| Veredicto | Qué significa | Ruta |
|---|---|---|
| **DIGITAL** | texto vectorial y fuentes reales | **A — reemplazo in-place**: extraer spans con posición y estilo (PyMuPDF), traducir, borrar y reinsertar en la misma caja. Da texto seleccionable, nitidez vectorial, archivo ligero, cero OCR y cero inpainting. |
| **HIBRIDO** | escaneo con capa de texto encima | **B**: valora la capa; si trae ruido de OCR, re-OCR con Vision sale más barato que limpiarla. Composición raster igual que C. |
| **ESCANEO** | imagen por página sin texto aprovechable | **C**: el pipeline completo F0–F7 de abajo. |

**Madurez real de cada ruta (no la infles al usuario):**
- **C — probada end-to-end** en un libro de 258 páginas. Es la ruta segura.
- **B** — C con el OCR abaratado; misma maquinaria.
- **A — probada end-to-end** en un zine de diseño repartido en 3 documentos y en un
  libro de rol denso de 153 páginas (tablas de clase, statblocks, listas de conjuros,
  índice, portada). Capacidades y reglas en §Ruta A; la crónica de cada proyecto y sus
  porqués viven en gbrain, no aquí.
  El piloto de páginas representativas sigue siendo obligatorio (una de cada tipo:
  prosa, tabla, lista, statblock, título de capítulo, índice, portada).

**Verificación extra cuando el veredicto es HIBRIDO:** que la capa *parezca* limpia no
basta. Se ha visto una capa que extraía 545 palabras por página y aun así traía las
cabeceras destrozadas. Contrasta 1–2 páginas de la capa contra un OCR fresco antes de
confiar en ella.

## Decisiones (pregunta esto al inicio, nada más)

- **Idioma/variante destino** (p. ej. español de México).
- **Destino**: pantalla, impresión casera o ambos (define calidad del ensamble).
- **Dominio y terminología**: ¿hay glosario oficial que respetar (SRD, norma técnica, edición previa)?
- **Modelo local**: `ollama list` y elige; verifica que responda antes de empezar.

Todo lo demás se decide con datos: el catálogo dice qué páginas son texto, arte o mapa.

## proyecto.json

```json
{
  "titulo": "Nombre original", "titulo_es": "Nombre traducido",
  "slug": "nombre-libro", "pdf_origen": "../Nombre original.pdf",
  "idioma_destino": "español de México", "dominio": "manual de rol d20",
  "modelo": "qwen3.5:35b-a3b-coding-nvfp4",
  "nombres_propios": ["Karvek", "Puertobruma"],
  "reglas_extra": ["Hit: = Impacto:", "undead = muertos vivientes"],
  "secciones": [[6, "Introducción"], [18, "Capítulo 1"]]
}
```
Todos los scripts leen de aquí vía `_proyecto.py`: no hay rutas ni títulos quemados.
Claves opcionales de la ruta A (`compose`, `portada`, `pagina_indice`, `indice_fijos`):
ver §Ruta A. Para montar la carpeta del proyecto y el orden de ejecución completo, lee
`references/plantilla-proyecto.md`.

## Instalación

```bash
python3.13 -m venv scripts/venv && scripts/venv/bin/pip install \
  pyobjc-framework-Vision pyobjc-framework-Quartz weasyprint pikepdf pillow numpy torch
```
- OCR = **Apple Vision** (macOS, 1.2 s/pág, excelente con cabeceras y cifras).
- Inpainting = **LaMa TorchScript** directo (`70_lama.py`). **No uses iopaint**: fija un
  Pillow viejo que no compila en Python moderno. Descarga `big-lama.pt` (196 MB) a
  `plantillas/modelos/`.
- Fuentes: clona/parchea las que faltan glifos del idioma destino con FontForge
  (acentos, ¿¡, Ñ). Guárdalas en `plantillas/fuentes/patched/`.

## Fases

**F0 — Catálogo** (rutas B y C). `01_catalog.py` clasifica cada página (texto / arte+caption / mapa /
mixta) y renderiza fondos 300 dpi. **Ojo: las páginas de un escaneo tienen tamaños
variables**; los fondos salen de `pdftoppm` por página (geometría real), no del JPEG crudo.

**F1 — OCR.** `10_ocr_vision.py` → `11_corpus.py` (+`12_reclassify.py`) producen líneas con
caja, tipo y columna. `23_bloques.py` agrupa en bloques, deshifena y detecta capitulares.

**F2 — Glosario.** `20_entidades.py` extrae candidatos; valida contra la fuente oficial y
guarda `traduccion/glosario.tsv` (EN→ES, fuente, nota). El TSV manda sobre cualquier
intuición. `21_glosario_check.py` valida coherencia.

**F3 — Piloto (GO/NO-GO).** 10 páginas representativas: prosa, tabla, panel de datos,
capitular, arte con caption. Solo si las 10 quedan limpias pasa a producción.

**F4 — Producción.** `35_traduce_ollama.py INICIO FIN` hace por página: traducir →
componer → QA → auto-reparar → `progress.csv`. Lánzalo **en segundo plano por capítulo**
y ve reparando lo que marque. `60_paneles.py` reconstruye fichas de datos (statblocks)
como paneles estructurados.

**F5 — Arte y mapas.** `71_arte.py` enmascara etiquetas, reconstruye el fondo con LaMa,
el modelo traduce y se compone con las fuentes del libro. Arte sin texto: `--sin-texto`.

**F6 — Ensamble.** `50_assemble.py --todas` sustituye páginas en el PDF original, pone
marcadores en el idioma destino y saca dos salidas (maestro 300 dpi + digital ~150 dpi).
Es re-corrible: hazlo tras cada tanda para tener siempre un híbrido usable.

**F7 — QA final.** Barrido de defectos (§Detectores), hoja de contactos de páginas
representativas y verificación visual.

**F8 — Foundry VTT** (opcional, solo material de rol). `80_foundry.py` genera diarios por
capítulo + glosario (lee ruta A o C; secciones desde proyecto.json); `81_foundry_fase2.py`
añade actores dnd5e, RollTables, escenas y handouts; se empaqueta con
`bunx @foundryvtt/foundryvtt-cli`. TRES TRAMPAS del CLI: (1) exige `_key`
(`!coleccion!id`) en CADA documento Y en los embebidos (`!journal.pages!entry.page`,
`!actors.items!…`) — sin él omite documentos o truena, y el pack queda VACÍO en
silencio; (2) `--out` es la carpeta PADRE (el CLI añade el nombre del pack; pasarle la
ruta completa anida `pack/pack`); (3) verificar SIEMPRE con `package unpack` contando
documentos — bajo bun el unpack puede fallar con «Iterator is not open», usar `npx`.

## Ruta A — pipeline completo (scripts 90–97)

- `90_digital.py --piloto/--traduce/--compone INI FIN` — extracción, traducción y
  composición por página (reanuda: salta páginas con JSON existente).

**Qué hace la composición de `90_digital.py`** (todo automático salvo lo marcado):
- Reinserción con `insert_htmlbox`; redacciones con `fill=False` (el relleno por defecto
  pinta rectángulos sobre fondos oscuros) y `PDF_REDACT_IMAGE_NONE` (el arte va debajo).
- Sonda de tinta por píxeles para rótulos de una línea: las métricas del motor HTML
  mienten ~0.65×cuerpo y sin la sonda los títulos caen sobre el bloque siguiente.
  `"compose": {"sube": true}` extiende la compensación a párrafos multilínea.
- Expansión de caja a la derecha limitada por la columna real (máx x1 de bloques
  MULTILÍNEA; los de una línea la sobreestiman); bloques de barra lateral no se expanden.
- Listones verticales rotados (1 línea y alto > 2×ancho); segmentación por salto de
  cuerpo ≥1.25× (get_text pega títulos con párrafos); capitulares fusionadas a su párrafo
  («T»+«he» → «The»); modo lista (mediana de línea ≤30 chars → conservar saltos; línea
  sangrada = continuación); run-in en versalitas reconstruido desde el EN (el modelo
  pierde los tokens).
- Tablas por celda (`tabla_frases`): números y símbolos JAMÁS se tocan; separadores de
  columna por huecos de cobertura horizontal + esqueleto numérico; en tablas de marcas
  (✦) cada palabra del encabezado se asigna al centro de columna más cercano; ordinales
  1st→1.º automáticos.
- Line-art: MuPDF solo borra sub-trazos totalmente cubiertos por la redacción (una letra
  que sobresale 0.3 pt sobrevive entera). Con `"line_art": "auto"` se une a la redacción
  el dibujo chico (3–60 pt) mayormente dentro del bloque + los glifos realmente pintados
  vía `get_texttrace()` (las capas de sombra pintan fuera del bbox de get_text) —
  necesario cuando los encabezados llevan copia vectorial. Con `"line_art": "none"` el
  vectorial se protege — necesario cuando hay adornos pegados al texto que deben
  sobrevivir. Elegir según el documento en el piloto.
- Fuentes embebidas: casi siempre subconjunto Identity-H sin glifos acentuados — NO
  sirven para texto nuevo; se compone con familias completas (base-14) o con
  `"fuente_sustituta": "/ruta/a.ttf"` en proyecto.json.
- Valores del `es/pag-NNN.json` de la ruta A: además de `"texto"`, `"~"` y `null`
  (§Convenciones), dict `{t, caja, size, lineas, centrado, alin}` para fusiones a mano;
  al dar `caja` más chica que el bbox original, el original se redacta completo igual.
- **Saltos de línea en ruta A: `\n\n`** (el token ⏎ es de la ruta C y se imprime
  literal). Listas con `{t: "uno\n\ndos", lineas: N}` conservan un elemento por renglón.
- **Rasgo duplicado por segmentación** (ids tipo `b11b`): el modelo mete el rasgo
  COMPLETO en el primer segmento y las continuaciones se traducen aparte → texto doble
  en página. Se detecta como LARGO (ratio >200 %) con un vecino que repite contenido.
  Receta: bloque largo = `{t, caja: unión de los bboxes}`, continuaciones = `"~"`.
- **`desduplica()` colapsa palabras repetidas ENTRE nombres adyacentes** en bloques-lista
  («… Zombie / Zombie Pack» pierde una entrada). Al reconstruir listas contra el
  glosario, los tokens sin match suelen ser víctimas de ese colapso: reinsertar.
- **Normalizar guiones U+2011 → `-` antes del match de `glosario_pagina`**: un guion no
  separable en el original esquiva la fila del glosario y el modelo improvisa.
- **Página de contenido a 2-3 columnas**: `97_indice` puede unir segmentos de columnas
  vecinas. Alternativa que funciona: construir `es/pag-NNN.json` a mano con UN RENGLÓN
  POR ENTRADA (`{t: "*Título . . . N*\n\n…", lineas: N}`, título traducido, puntos y
  folio intactos) y componer por la vía normal. Para retocar UNA página del libro ya
  ensamblado: recomponerla sola e insertarla con `delete_page` + `insert_pdf`
  (guardando a temp + move) — mucho más barato que re-ensamblar todo.
- `95_libro.py [INI FIN]` — ensambla el libro entero sobre el PDF original, marcadores
  en idioma destino desde `secciones`, y guarda con `deflate_images` + `garbage=4`
  (**apply_redactions descomprime las imágenes**: sin esto un libro de 23 MB sale en
  216 MB; con esto, en 16). Portada e índice van por composición especial si
  proyecto.json declara `"portada"` / `"pagina_indice"`. **Compuerta**: sin la
  validación total de F7.5 el libro completo sale como `-BORRADOR.pdf`.
- `96_qa.py` — barrido: SIN-TRAD, inglés residual, números alterados, glosario, tokens,
  y `VALIDACION` (falta o cobertura incompleta de la validación total F7.5).
- `97_indice.py` — índice con puntos líder: reemplaza SOLO el segmento del título de
  cada entrada (los puntos y números de página quedan intactos); títulos de sección
  fijos en `"indice_fijos"`; ojo con números pegados al título («Background114»), se
  separan por caracteres. La página que guarda sale de `"pagina_indice"`.
- `98_consistencia.py` — validación determinística EN↔ES de TODO el libro; abarata la
  validación total (F7.5) dejando a Claude solo lo que exige juicio. Detecta `NUM`
  (números alterados), `MARCADO` (asteriscos/tokens desbalanceados), `CORTO`/`LARGO`
  (ratio ES/EN fuera de 45–200 %: delata **rotación de contenido entre claves**),
  `INGLES`, `PERDIDO` (nombre propio del EN ausente en el ES) y `DIVERGE` (el MISMO
  texto EN traducido de dos formas distintas en el libro). Córrelo ANTES de gastar
  agentes revisores.
- `99_marcado.py` — repara el marcado desbalanceado contra el EN en dos fases: alinea
  el cierre del run-in copiándolo del original y luego cierra al final lo que quede
  abierto. Idempotente; lo no reparable lo lista para adjudicar a mano.
- `97b_sentido.py` — sospechas de significado equivocado, que ningún detector de forma
  ve: `FALSO-AMIGO` (tabla EN→calco: eventually/vicious/actually/realize…),
  `NEGACION` (el EN niega y el ES perdió la negación), `CONDICION` (el EN nombra una
  condición y el ES otra), `FRECUENCIA` (once per rest/scene/session cambiado) y
  `RECURSO` (Hope↔Fear intercambiados). NO decide: marca candidatos para adjudicar
  uno a uno contra el original.

- `digital_ligero.py [dpi] [calidad]` — saca la versión de pantalla DEL maestro con
  `Document.rewrite_images()`, que recomprime respetando máscaras y recortes. **Jamás
  con `replace_image()` a mano**: pierde el SMask y el arte acaba pintado ENCIMA del
  texto (ya probado y descartado). El texto sigue vectorial; solo cambian las imágenes.

**Orden del cierre (F7–F7.5)**, cada paso alimenta al siguiente:
`99_marcado.py` → `98_consistencia.py` → `97b_sentido.py` → adjudicar cada hallazgo
contra el EN → aplicar con scripts idempotentes → recomponer SOLO las páginas tocadas
→ registrar en `qa/validacion-total.tsv` → `95_libro.py`. Los falsos positivos se
documentan en `qa/overrides.tsv` con su motivo; no se «corrige» lo que ya estaba bien.

Claves nuevas de proyecto.json (todas opcionales):
`"compose": {"line_art": "auto|none", "sube": false}` ·
`"portada": {"zona": […], "caja": […], "titulo": "…", "tamano": 52, "color": "white",
"contorno": "black"}` (efecto contorno = N copias desplazadas + relleno) ·
`"pagina_indice": 3` · `"indice_fijos": {"Chapter 1: …": "Capítulo 1: …"}`.

**Consistencia con lo YA entregado**: si existe un proyecto hermano entregado del
mismo juego/dominio, sus `es/` son la autoridad terminológica: `grep` ahí ANTES de
fijar o «corregir» un término. Dos veces por proyecto el instinto propone divergir de
una decisión ya impresa — y pierde.

**Glosario como palanca de consistencia**: el modelo local inventa un nombre distinto
para el mismo término en cada página. Antes de producción, construir el glosario
COMPLETO (todos los nombres de conjuros/habilidades/etiquetas de tabla, no solo lore) e
inyectarlo filtrado por página (`glosario_pagina`). Si el dominio tiene terminología
oficial localizada (juegos, normas técnicas), verificarla contra la fuente oficial antes
de producción — las fuentes concretas ya validadas están en las notas privadas de gbrain.

### F7.5 — Validación total EN↔ES (GO/NO-GO, OBLIGATORIA)

Tras el QA automático, el orquestador (no el modelo local) revisa **TODO** el texto
EN↔ES por tramos: agentes paralelos que reportan reemplazos exactos
`página\tbloque\ttipo\tfragmento_actual\tfragmento_corregido`; el orquestador adjudica
CADA hallazgo contra el EN antes de aplicar — los revisores también se equivocan e
inventan términos. En un libro denso salen ~6 correcciones/página que los detectores
no ven: género en viñetas, falsos amigos (*vicious*→vicioso, *check*→tirada vs prueba),
rotaciones de contenido entre claves (cazarlas también con ES < 45 % del largo del EN),
celdas de tabla mal etiquetadas. Aplicación idempotente: si el fragmento nuevo ya está,
cuenta como aplicado (sobrevive a relanzamientos).

Antes de gastar agentes, resolver los DIVERGE por REGLAS DE MASA con jerarquía de
canonicidad: (1) el apéndice de referencia manda sobre los mazos imprimibles; (2) la
página real de la sección/clase manda sobre listados, ejemplos y hojas de referencia
(que adoptan la redacción conservando MAYÚSCULAS/negritas locales); (3) entre
duplicados del capítulo de adversarios, el statblock real manda sobre el ejemplo
anotado. Al aplicar hallazgos de agentes: CADA reemplazo lleva una GUARDA (regex sobre
el EN del bloque) — los revisores contradicen el glosario a veces y la guarda lo
detiene. Si un agente reporta con tope de hallazgos, pedirle el resto. Y en `96_qa`,
~80 % de los falsos GLOSARIO son conjugaciones («marques» vs «marcar un Estrés»):
filtrar por raíz (4 primeras letras) antes de revisar a mano.

**Esta fase NO es opcional y deja evidencia**: registra `qa/validacion-total.tsv` con
`# cobertura: INI-FIN` (rangos revisados; un tramo sin hallazgos también cuenta) y una
fila por corrección aplicada (contrato en `_validacion.py`). La compuerta es mecánica:
`95_libro.py` produce `-BORRADOR.pdf` si la cobertura no abarca todas las páginas, y
`96_qa.py` lo reporta como defecto `VALIDACION`. Saltártela exige decisión EXPLÍCITA
del usuario (`--sin-validar`) — nunca la tomes tú solo.

## Convenciones de `traduccion/es/pag-NNN.json`

| Valor | Significado |
|---|---|
| `"texto"` | traducción del bloque |
| `"~"` | solo parchar/borrar (su contenido va absorbido en otro bloque) |
| `null` | dejar el original intacto (arte, códigos idénticos, bloques solo-dígitos) |
| dict de control fino | ruta C: `{"t","type","dropcap","extiende","size","caja"}` · ruta A: `{"t","caja","size","lineas","centrado","alin"}` |

- `extiende: ["b04","b05"]` fusiona bloques partidos por el OCR (**los absorbidos ya no se
  componen: nunca metas ahí una celda que deba traducirse aparte**).
- `caja: [x0,y0,x1,y1]` sustituye la geometría cuando el OCR perdió líneas (adjudícala
  contra un recorte del render).
- `__statblocks__` para fichas de datos estructuradas.
- Marcado: `***negrita-cursiva***`, `**negrita**`, `*cursiva*`, `‹sc›versalitas‹/sc›`, `⏎`.

## Reglas duras (aprendidas a la mala — respétalas)

**Modelo local**
- `think:false` en qwen/deepseek: *thinking* + JSON forzado en prompts largos = timeout infinito.
- Verifica **siempre** lo que devuelve: números idénticos, términos de glosario presentes,
  nada de inglés residual, y que los nombres propios del bloque original aparezcan en su
  traducción (detecta **contenido rotado entre claves**, un fallo silencioso y peligroso).
- El modelo a veces renombra la clave o devuelve vacío: acepta clave única como fallback.
- Traduce nombres propios si lo dejas: lista negra explícita + barrido posterior.
- Traduce nombres de PERSONAJES en los ejemplos de juego y créditos de artista (una fila
  de glosario genérica tipo «Bear→Oso» le pega al artista Bear): los bloques de crédito
  («© … 20XX» + nombre) van a `null`, y los diálogos de ejemplo se barren buscando los
  nombres del reparto.
- Traduce «Tier» y unidades del juego aunque las reglas lo prohíban: fila EN==ES en el
  glosario («Tier→Tier») arma el detector PERDIDO y evita recaídas silenciosas.
- Rota rangos en statlines: correr POR TANDA un detector barato que extrae el rango
  (Melee/Very Close/…) de la misma posición en EN y ES y los compara. Caza errores que
  cambian el alcance de un adversario en mesa.

**Composición**
- El tamaño se topa por el interlineado del OCR: en fragmentos de una línea eso lo vuelve
  diminuto. Un `size` explícito **con `caja`** manda sobre ese tope.
- El parche de un panel debe cubrir **todos** los bloques absorbidos, o el texto original
  queda visible debajo (síntoma: "texto encimado").
- Los títulos se centran en la página completa salvo que declaren `caja`.
- WeasyPrint: nunca `<p>` dentro de `<span>` (línea fantasma); `columns` no funciona en
  divs absolutos (haz el reparto de columnas midiendo con PIL); `box-shadow` no existe.
- Parches **todos** antes que los textos (orden de capas).
- Los regex de limpieza de tokens deben ceñirse a ‹›: si incluyen «» se comen la letra
  inicial de palabras españolas tras comillas («gran» → «ran»).
- Rótulos multi-palabra del original con espaciado de letras («N E E D F O R S P E E D»):
  tradúcelos con espaciado NORMAL; si conservas los espacios entre letras, los espacios
  de palabra desaparecen al componer («NECESIDADDEVELOCIDAD»).

**Trabajo sobre imagen**
- **Respalda el fondo antes de editarlo** (`corpus/render300-orig/`) y, si dudas de su
  pureza, regenéralo del PDF fuente con `pdftoppm`.
- Después de cualquier composición sobre imagen: **renderiza y míralo**. El QA no ve
  imágenes. Tres veces en este proyecto el QA dijo ✓ con el resultado visualmente roto.
- Vision barre también los márgenes: filtra créditos de artista verticales (x < 4 % del
  ancho) y nombres sueltos en mayúsculas.

**Diagnóstico**
- Escaneos de texto **siempre insensibles a mayúsculas** (`Their` capitalizado sobrevivió
  tres rondas de limpieza).
- Antes de editar un bloque, **imprime su valor crudo**; no supongas su forma.
- Falsos positivos comunes del validador: «celestial bodies» (cuerpos celestes),
  «Piercing the Illusion» (encabezado, no daño), «lightning-quick» (modismo). Documenta
  con `glosario_skip` en `qa/v4-overrides.json`, no "corrijas" lo que ya estaba bien.
- Si el compose falla, debe **fallar ruidosamente**: verifica returncode y existencia del
  PDF (un bug de tamaño 0 pasó 38 páginas con ✓ ciego).

## Ciclo de auto-reparación (ya implementado en `35_traduce_ollama.py`)

1. **Overflow** → acortar el bloque con el modelo (2 rondas, guardias de números y glosario)
   → escalera de tamaños 8.5 → 8.3 → 8.2 con acortado intermedio → `caja` extendida.
2. **Glosario** → re-traducir *solo* los bloques con el término fallado, con requisito duro
   y verificación de que el término aparezca.
3. **Números** → casi siempre es OCR del original revuelto: adjudica contra un recorte del
   render y documenta `numeros_ok` en overrides.
4. **Inglés residual / rotación** → re-traducción suelta del bloque.

**Cuándo parar y preguntar al usuario:** cambio de alcance (traducir o no portada,
créditos, marcas registradas), rehacer una página completa desde cero, o un defecto que
solo él puede juzgar estéticamente. Todo lo demás resuélvelo tú.

## Detectores de defectos (F7)

- **Huérfanos**: bloques con texto sin entrada en el JSON — whitelistea `extiende` y
  `resto-L/R` o tendrás ~120 falsos positivos por 1 real.
- **Solapes**: cajas de bloques compuestos que se intersectan >40 px × >12 px.
- **Sin traducir**: stopwords del idioma origen en el JSON traducido, sin distinguir mayúsculas.
- **Hoja de contactos**: renderiza 10 páginas representativas y míralas.

## Rendimiento realista

| Etapa | Tiempo |
|---|---|
| OCR | ~1.2 s/página |
| Traducción (modelo local 35B) | 10–30 s/página |
| Ciclo completo con QA y reparaciones | 30–90 s/página |
| Capítulo de 20 páginas | 15–25 min |
| Libro de 250 páginas | 2–3 sesiones largas |
| LaMa por región | 3–8 s (GPU MPS) |

Espera **40–60 % de páginas limpias a la primera** en material denso; el resto pasa por
reparación. Es normal y está automatizado.

## Uso personal

Este flujo es para material del que el usuario ya posee copia y para su uso privado.
Deja constancia en el proyecto y **no publiques ni distribuyas** el resultado.
