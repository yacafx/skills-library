#!/usr/bin/env python3
"""90_digital.py — RUTA A: PDF con texto vectorial (veredicto DIGITAL del triaje).

Se trabaja sobre el PDF real: se extraen los bloques con su geometría y ESTILO
(negrita/cursiva/párrafos), el MODELO LOCAL los traduce conservando el marcado, y se
reinsertan con `insert_htmlbox`, que respeta negritas y reescala para que quepan.
El arte y los vectores no se tocan nunca.

Uso:
  venv/bin/python 90_digital.py --extrae 5 8
  venv/bin/python 90_digital.py --traduce 5 8
  venv/bin/python 90_digital.py --compone 5 8
  venv/bin/python 90_digital.py --piloto 5 8

TRES TRAMPAS RESUELTAS AQUÍ (documentadas porque cuestan horas):
1. Muchos PDF de diseño llevan el texto DUPLICADO en dos capas (efecto de sombra o
   relieve). PyMuPDF las extrae intercaladas: "PERIL PERIL IN IN PINEBROOK PINEBROOK".
   Sin desduplicar, la traducción sale repetida. → `desduplica()`.
2. Las fuentes embebidas casi siempre son SUBCONJUNTOS (solo los glifos usados): al
   reinsertar texto nuevo se comen acentos y letras ("Percepci n", "Com n Draconico").
   → NUNCA se reutilizan; se compone con familias completas (las base-14 cubren Latin-1).
3. `insert_textbox` no escribe NADA si el texto no cabe y además pierde las negritas.
   → `insert_htmlbox` con CSS: conserva estilos y reescala solo.
"""
import argparse, html as H, importlib.util, json, re, sys
from pathlib import Path

import fitz  # PyMuPDF

SC = Path(__file__).resolve().parent
P = SC.parent
sys.path.insert(0, str(SC))
import _proyecto

ES = P / "traduccion" / "es"
BLOQ = P / "traduccion" / "digital"
SALIDA = P / "render" / "paginas"
for d in (ES, BLOQ, SALIDA):
    d.mkdir(parents=True, exist_ok=True)

_spec = importlib.util.spec_from_file_location("t", SC / "35_traduce_ollama.py")
_t = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_t)
MOD = _proyecto.get("modelo", "qwen3.5:35b-a3b-coding-nvfp4")
LEGAL = re.compile(r"WIZARDS OF THE COAST|©\s*\d{4}|TM &|All rights reserved|Hasbro"
                   r"|GM Binder|gmbinder\.com|^\d{2}/\d{2}/\d{4}", re.I)


def glosario_pagina(texto_pagina):
    """Solo las entradas del glosario cuyos términos EN aparecen en la página: el TSV
    completo inflaría el prompt del modelo local en cada llamada."""
    f = P / "traduccion" / "glosario.tsv"
    if not f.exists():
        return ""
    low = texto_pagina.lower()
    filas = []
    for l in f.read_text().splitlines()[1:]:
        if "\t" not in l:
            continue
        en, es = l.split("\t")[:2]
        t = en.lower()
        variantes = [v for v in (t, t[:-1], t[:-2]) if len(v) >= 4] or [t]
        if any(v in low for v in variantes):
            filas.append(f"{en} = {es}")
    return "\n".join(filas)


def abre():
    return fitz.open(str(_proyecto.pdf_origen()))


def _sin_marcado(w):
    """Token comparable: sin ‹tokens›, negritas ni cursivas (las capas de sombra suelen
    traer marcado distinto en cada copia y así no se detectaría el duplicado)."""
    w = re.sub(r"‹[^›]*›", "", w)
    return w.replace("**", "").replace("*", "").strip(" .,;:").lower()


def desenvuelve(v):
    """El modelo a veces devuelve un dict serializado ({'traduccion': '…'}) en lugar del
    texto: si se inserta tal cual, el JSON se imprime en la página."""
    v = str(v).strip()
    mo = re.match(r"^\{\s*['\"](?:traduccion|traducción|translation|text|texto)['\"]\s*:\s*['\"](.*)['\"]\s*\}$", v, re.S)
    if mo:
        return mo.group(1).strip()
    if v.startswith("{") and v.endswith("}") and len(v) > 20:
        interior = re.findall(r"['\"]([^'\"]{15,})['\"]", v)
        if interior:
            return max(interior, key=len).strip()
    return v


def desduplica(t):
    """Quita la duplicación que producen las capas de sombra del original."""
    prev = None
    while t != prev:
        prev = t
        tok = t.split()
        lim = [_sin_marcado(w) for w in tok]
        n = len(tok)
        def _con_letras(ws):
            return any(re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", w) for w in ws)
        if (n >= 4 and n % 2 == 0 and _con_letras(lim)
                and all(lim[i] == lim[i + 1] and lim[i] for i in range(0, n, 2))):
            t = " ".join(tok[::2])
            continue                                   # w w x x y y → w x y
        hecho = False
        for k in range(min(12, n // 2), 0, -1):        # n-grama repetido en cualquier sitio
            for i in range(0, n - 2 * k + 1):
                if lim[i:i + k] == lim[i + k:i + 2 * k] and _con_letras(lim[i:i + k]):
                    t = " ".join(tok[:i + k] + tok[i + 2 * k:])
                    hecho = True
                    break
            if hecho:
                break
    return t


def _tam_linea(ln):
    """Tamaño dominante de la línea, ponderado por caracteres."""
    pesos = {}
    for sp in ln["spans"]:
        if sp["text"].strip():
            pesos[round(sp["size"])] = pesos.get(round(sp["size"]), 0) + len(sp["text"].strip())
    return max(pesos, key=pesos.get) if pesos else 0


def _segmenta(lines):
    """Parte las líneas donde el cuerpo dominante salta ≥1.25× (encabezado pegado a un
    párrafo por get_text). Las líneas de un solo carácter (capitulares) no abren corte."""
    segs, actual, prev = [], [], None
    for ln in lines:
        t = _tam_linea(ln)
        chars = sum(len(sp["text"].strip()) for sp in ln["spans"])
        if chars <= 1 and actual and prev and t and t / prev >= 1.4:
            # letra CAPITULAR: abre segmento nuevo (pertenece al párrafo que sigue,
            # no al título previo) y no impone su tamaño al resto
            segs.append(actual)
            actual, prev = [ln], None
            continue
        if actual and prev and t and chars > 1 and max(t, prev) / min(t, prev) >= 1.25:
            segs.append(actual)
            actual = []
        actual.append(ln)
        if chars > 1 and t:
            prev = t
    if actual:
        segs.append(actual)
    return segs


def _bloque_de(page, seg, bid):
    """Construye un bloque a partir de un grupo de líneas."""
    # letra CAPITULAR al frente: se funde con la primera palabra («T» + «he market» →
    # «The market») para que el modelo reciba la frase completa
    letra = ""
    if len(seg) > 1:
        c0 = "".join(sp["text"].strip() for sp in seg[0]["spans"])
        if len(c0) == 1 and _tam_linea(seg[0]) >= 1.5 * (_tam_linea(seg[1]) or 99):
            letra = c0
            bbox0 = fitz.Rect(seg[0]["bbox"])
            seg = seg[1:]
    partes, tam, fuentes, colores, serif = [], [], [], [], 0
    spans_est, limites = [], []
    tops = [ln["bbox"][1] for ln in seg]
    gaps = sorted(tops[k + 1] - tops[k] for k in range(len(tops) - 1)) if len(tops) > 1 else []
    modal = gaps[len(gaps) // 2] if gaps else 0
    x0s = [round(ln["bbox"][0], 1) for ln in seg]
    izq_comun = min(x0s) if x0s else 0
    sangrados = sum(1 for x in x0s if x > izq_comun + 4)
    bbox = fitz.Rect(seg[0]["bbox"])
    y_prev = None
    for ln in seg:
        bbox |= fitz.Rect(ln["bbox"])
        # interlineado MODAL: comparar contra él detecta los saltos de párrafo reales
        if y_prev is not None and modal and (ln["bbox"][1] - y_prev) > modal * 1.28:
            partes.append("\n\n")                   # salto de párrafo real
        y_prev = ln["bbox"][1]
        limites.append((len(partes), round(ln["bbox"][0], 1)))
        for sp in ln["spans"]:
            txt = sp["text"]
            if not txt.strip():
                continue
            tam.append(sp["size"]); fuentes.append(sp["font"]); colores.append(sp["color"])
            f = sp["flags"]
            serif += 1 if f & 4 else 0
            neg = "**" if f & 16 else ""
            cur = "*" if f & 2 else ""
            # versalitas: la fuente las hace, la sustituta necesita marcado explícito
            sc = ("‹sc›", "‹/sc›") if re.search(r"smallcaps|_sc\b|-sc\b", sp["font"], re.I) else ("", "")
            spans_est.append((len(partes), sp["color"], sp["size"]))
            partes.append(f"{sc[0]}{neg}{cur}{txt.strip()}{cur}{neg}{sc[1]} ")
    if not tam:
        return None
    col_dom = max(set(colores), key=colores.count)
    tam_dom = max(set(round(x) for x in tam), key=[round(x) for x in tam].count)
    for idx, c, s in spans_est:            # marca lo que se sale del estilo dominante
        if idx >= len(partes):
            continue
        if c != col_dom:
            partes[idx] = f"‹c:{c:06x}›{partes[idx].rstrip()}‹/c› "
        elif round(s) >= tam_dom * 1.35:
            partes[idx] = f"‹g›{partes[idx].rstrip()}‹/g› "
    # MODO LISTA (columnas de conjuros, líneas de datos de conjuro): renglones cortos que
    # deben conservar su salto de línea; las líneas sangradas son continuación de la previa
    lineas_txt = []
    for k, (a, x0) in enumerate(limites):
        fin = limites[k + 1][0] if k + 1 < len(limites) else len(partes)
        lineas_txt.append(("".join(p for p in partes[a:fin] if p != "\n\n").strip(), x0))
    con_texto = [l for l, _ in lineas_txt if l]
    lista = (len(con_texto) >= 3
             and sorted(len(re.sub(r"‹[^›]*›|\*+", "", l)) for l in con_texto)[len(con_texto) // 2] <= 30)
    if lista:
        out = []
        for l, x0 in lineas_txt:
            if not l:
                continue
            if out and x0 > izq_comun + 4:
                out[-1] += " " + l
            else:
                out.append(l)
        texto = "\n\n".join(out)
    else:
        texto = "".join(partes)
    texto = re.sub(r"[ ]{2,}", " ", texto).strip()
    texto = re.sub(r"\*\*\s*\*\*", " ", texto)
    if texto.count("**") % 2:                      # marca sin pareja: se vería literal
        i = texto.rfind("**")
        texto = texto[:i] + texto[i + 2:]
    # listas de casillas: una opción por renglón, «[ ] texto [ ]» como el original
    if texto.count("[") >= 3:
        texto = re.sub(r"\s*\[\s*\]\s*", " [ ] ", texto)
        texto = re.sub(r"\s*\[ \]\s+(?=[A-ZÁÉÍÓÚÑ¿«])", "\n\n[ ] ", texto)
        texto = re.sub(r"\s*\[ \]\s*$", "", texto)
    # fichas de datos: cada «**Etiqueta** valor» abre renglón (CA, PG, Velocidad…);
    # NO aplica a líneas de estadísticas separadas con «|» (statblocks de una tira):
    # partirlas multiplica los renglones y el bloque ya no cabe en su caja
    if "|" not in texto and len(re.findall(r"\*\*[^*]{3,30}\*\*\s*[\d+]", texto)) >= 2:
        texto = re.sub(r"\s+(?=\*\*[^*]{3,30}\*\*\s*[\d+])", "\n\n", texto)
    texto = desduplica(texto)
    if letra and texto:
        texto = letra + texto      # «T» + «he market…» → «The market…»
        bbox |= bbox0
    if not texto:
        return None
    return {
        "id": bid, "bbox": [round(v, 1) for v in bbox], "texto": texto,
        "dropcap": letra,
        "lineas": len(seg),
        "lista": lista,
        "size": round(sum(tam) / len(tam), 2),
        "size_max": round(max(tam), 2),
        "fuente": max(set(fuentes), key=fuentes.count),
        "color": max(set(colores), key=colores.count),
        "serif": serif > len(tam) / 2,
        # centrado SOLO si las líneas no comparten margen izquierdo (si lo comparten,
        # el texto va alineado a la izquierda aunque la caja esté centrada en la página)
        "centrado": (abs((bbox.x0 + bbox.x1) / 2 - page.rect.width / 2) < 12
                     and (bbox.x1 - bbox.x0) < page.rect.width * 0.8
                     and len(seg) > 1 and sangrados >= len(x0s) - 1),
    }


NUMERICO = re.compile(r"^[\d+\-—–−/.,()×x*'✦●✓✔♦]+$")
ORDINAL = re.compile(r"^(\d{1,2})(st|nd|rd|th)[.,]?$")


def _detecta_tablas(page):
    """Regiones de tabla: rect de fondo grande cuyo contenido es mayormente numérico."""
    regiones = []
    palabras = page.get_text("words")
    for d in page.get_drawings():
        r = fitz.Rect(d["rect"])
        if not (250 < r.width < 570 and 90 < r.height < 720 and r.y0 > 30):
            continue
        dentro = [w for w in palabras if fitz.Rect(w[:4]).intersects(r)]
        if len(dentro) < 25:
            continue
        num = sum(1 for w in dentro if NUMERICO.match(w[4]) or ORDINAL.match(w[4]))
        if num / len(dentro) >= 0.3:
            if not any(r.intersects(o) for o in regiones):
                regiones.append(r)
    return regiones


def _frases_tabla(page, regiones):
    """Celdas TEXTUALES de la tabla (los números y guiones no se tocan jamás).
    Palabras contiguas en la misma línea forman frase; una frase apilada justo debajo
    con solape horizontal es la continuación de la celda (encabezados de dos líneas,
    rasgos que envuelven)."""
    frases = []
    for reg in regiones:
        todas = [w for w in page.get_text("words") if fitz.Rect(w[:4]).intersects(reg)]
        # separadores de columna: franjas x donde NINGUNA fila pone texto; un umbral de
        # hueco fijo no basta (entre encabezados de columnas vecinas hay solo ~3 pt)
        def _cobertura(pals):
            cob = []
            for a, b in sorted((w[0], w[2]) for w in pals):
                if cob and a - cob[-1][1] < 2.2:
                    cob[-1][1] = max(cob[-1][1], b)
                else:
                    cob.append([a, b])
            return cob
        cob_todas = _cobertura(todas)
        separadores = [(cob_todas[k][1] + cob_todas[k + 1][0]) / 2 for k in range(len(cob_todas) - 1)]
        # esqueleto de columnas: los huecos angostos entre columnas de símbolos/números
        # también separan aunque una palabra de encabezado los puentee
        nums = [w for w in todas if NUMERICO.match(w[4]) or ORDINAL.match(w[4])]
        if len(nums) >= 12:
            cob_n = _cobertura(nums)
            for k in range(len(cob_n) - 1):
                hueco = cob_n[k + 1][0] - cob_n[k][1]
                if 3 < hueco < 18:
                    separadores.append((cob_n[k][1] + cob_n[k + 1][0]) / 2)
        ws = [w for w in todas if not NUMERICO.match(w[4]) and not ORDINAL.match(w[4])]
        ws.sort(key=lambda w: (round(w[3]), w[0]))
        simbolos = [w for w in todas if re.fullmatch(r"[✦●✓✔♦]+", w[4])]
        grupos = []
        if len(simbolos) >= 6:
            # tabla de MARCAS (sugerencias de clase): los ✦ definen los centros de
            # columna; cada palabra del encabezado se asigna a su columna más cercana
            # (un umbral de hueco no sirve: las palabras puentean columnas vecinas)
            xs = sorted((w[0] + w[2]) / 2 for w in simbolos)
            centros = []
            for x in xs:
                if centros and x - centros[-1][-1] < 7:
                    centros[-1].append(x)
                else:
                    centros.append([x])
            centros = [sum(c) / len(c) for c in centros]
            etiqueta_max = min(centros) - 15 if centros else 1e9
            celdas = {}
            for w in ws:
                cx = (w[0] + w[2]) / 2
                col = -1 if cx < etiqueta_max else min(range(len(centros)), key=lambda i: abs(centros[i] - cx))
                celdas.setdefault((round(w[3] / 4), col), []).append(w)
            for (fila, col), pal in sorted(celdas.items()):
                pal.sort(key=lambda w: w[0])
                r = fitz.Rect(pal[0][:4])
                for w in pal[1:]:
                    r |= fitz.Rect(w[:4])
                grupos.append({"rect": r, "texto": " ".join(w[4] for w in pal)})
        else:
            for w in ws:
                r = fitz.Rect(w[:4])
                corta = grupos and any(grupos[-1]["rect"].x1 - 0.2 <= s <= r.x0 + 0.2 for s in separadores)
                if (grupos and not corta and abs(grupos[-1]["rect"].y1 - r.y1) < 3
                        and r.x0 - grupos[-1]["rect"].x1 < 7):
                    grupos[-1]["rect"] |= r
                    grupos[-1]["texto"] += " " + w[4]
                else:
                    grupos.append({"rect": r, "texto": w[4]})
        # fusión vertical (celdas envueltas / encabezados apilados)
        fusionados = []
        for g in grupos:
            enc = None
            for f in fusionados:
                sol = min(f["rect"].x1, g["rect"].x1) - max(f["rect"].x0, g["rect"].x0)
                if sol > 0.55 * min(f["rect"].width, g["rect"].width) and -2 <= g["rect"].y0 - f["rect"].y1 < 4.5:
                    enc = f
                    break
            if enc:
                enc["rect"] |= g["rect"]
                enc["texto"] += " " + g["texto"]
            else:
                fusionados.append(g)
        frases.extend(f for f in fusionados if re.search(r"[A-Za-z]{2}", f["texto"]))
    return frases


# Dígitos estilizados de fuentes de display (Eveleth) que get_text reporta como
# glifos de uso privado; sin el mapa se componen como tofu (⬜).
PUA_DIGITOS = {"\ue53f": "10", "\ue540": "9", "\ue541": "1", "\ue542": "2",
               "\ue543": "3", "\ue544": "4", "\ue545": "5", "\ue546": "6",
               "\ue547": "7", "\ue548": "8"}

# Ligaduras rotas por la extracción («Diffi culty», «fl ying»): el espacio tras un
# token terminado en fi/fl/ffi/ffl seguido de minúscula es espurio. No se incluye
# «ff» (off/staff/cliff son palabras reales) ni tokens con guion previo (sci-fi).
_LIGADURA = re.compile(r"\b(?<!-)(\w*?(?:ffi|ffl|fi|fl))[ ](?=[a-z])")


def _normaliza_extraccion(t):
    for pua, d in PUA_DIGITOS.items():
        t = t.replace(pua, d)
    return _LIGADURA.sub(r"\1", t)


def _es_continuacion(p, b):
    """b continúa el párrafo de p: misma columna/estilo, contiguo verticalmente,
    p termina a media frase y b arranca en minúscula. Cura los párrafos que get_text
    parte en varios bloques (rasgos de statblock, texto que envuelve arte)."""
    if p.get("lista") or b.get("lista") or p.get("dropcap") or b.get("dropcap"):
        return False
    # comparar FAMILIA, no la fuente exacta: el arranque «***Rasgo - Acción:***» domina
    # el primer bloque con la variante BoldItalic y la continuación va en Light
    fam = lambda f: re.split(r"[-,]", f)[0]
    if fam(p["fuente"]) != fam(b["fuente"]) or abs(p["size"] - b["size"]) > 0.3:
        return False
    if abs(p["bbox"][0] - b["bbox"][0]) > 3:
        return False
    if not (-2 <= b["bbox"][1] - p["bbox"][3] <= p["size"] * 1.1):
        return False
    fin = re.sub(r"[*›»\s]+$", "", p["texto"])
    if not fin or fin[-1] in ".!?:;—":
        return False
    ini = re.sub(r"^[*‹«\s]+", "", b["texto"])
    return bool(ini) and (ini[0].islower() or ini[0].isdigit())


def _fusiona_continuaciones(bloques):
    out = []
    for b in bloques:
        if out and _es_continuacion(out[-1], b):
            p = out[-1]
            r = fitz.Rect(p["bbox"]) | fitz.Rect(b["bbox"])
            p["bbox"] = [round(v, 1) for v in r]
            sep = "" if p["texto"].rstrip().endswith("-") else " "
            p["texto"] = p["texto"].rstrip() + sep + b["texto"].lstrip()
            p["lineas"] += b["lineas"]
            p["size_max"] = max(p["size_max"], b["size_max"])
        else:
            out.append(b)
    return out


def extrae(pg, doc=None):
    """Bloques con geometría, estilo y marcado (**negrita**, *cursiva*, párrafos)."""
    propio = doc is None
    doc = doc or abre()
    page = doc[pg - 1]
    regiones = _detecta_tablas(page)
    bloques = []
    for i, b in enumerate(page.get_text("dict")["blocks"]):
        if b.get("type") != 0:
            continue
        br = fitz.Rect(b["bbox"])
        if any((br & reg).get_area() > br.get_area() * 0.5 for reg in regiones):
            continue                       # va por el camino de tabla, no el genérico
        segs = _segmenta(b["lines"])
        for j, seg in enumerate(segs):
            bid = f"b{i:02d}" if len(segs) == 1 else f"b{i:02d}{chr(97 + j)}"
            bl = _bloque_de(page, seg, bid)
            if bl:
                bloques.append(bl)
    bloques = _fusiona_continuaciones(bloques)
    for bl in bloques:
        bl["texto"] = _normaliza_extraccion(bl["texto"])
    frases = _frases_tabla(page, regiones)
    for f in frases:
        f["texto"] = _normaliza_extraccion(f["texto"])
    if propio:
        doc.close()
    return {"pagina": pg, "bloques": bloques,
            "tablas": [[round(v, 1) for v in r] for r in regiones],
            "tabla_frases": [{"id": f"t{k:02d}", "rect": [round(v, 1) for v in f["rect"]],
                              "texto": f["texto"]} for k, f in enumerate(frases)]}


def normaliza_tokens(t):
    """El modelo suele devolver los tokens con delimitadores cambiados («sc» en vez de
    ‹sc›) o mutilados. Se normalizan ANTES de convertirlos a HTML; lo que no encaje se
    borra en a_html, porque un token suelto se imprime literal en la página."""
    t = re.sub(r"[«‹<]\s*(/?)\s*(sc|g)\s*[»›>]", r"‹\1\2›", t)
    t = re.sub(r"[«‹<]\s*c\s*:\s*([0-9a-fA-F]{6})\s*[»›>]", lambda m: f"‹c:{m.group(1).lower()}›", t)
    t = re.sub(r"[«‹<]\s*/\s*c\s*[»›>]", "‹/c›", t)
    return t


def ajusta_sc(en, es):
    """Encabezado en versalitas: el modelo pierde los tokens ‹sc› o los vuelve comillas
    («creyente»). Se reconstruyen SIEMPRE desde el original, no se confía en el modelo."""
    mo = re.match(r"^‹sc›(.+)‹/sc›$", en.strip(), re.S)
    if not mo:
        return es
    limpio = re.sub(r"‹/?sc›|‹[^›]{0,10}›|[«»]", "", normaliza_tokens(es)).strip()
    if limpio and limpio[0].islower() and mo.group(1)[0].isupper():
        limpio = limpio[0].upper() + limpio[1:]
    return f"‹sc›{limpio}‹/sc›" if limpio else es


CONECTORES = {"de", "del", "la", "las", "los", "el", "en", "y", "con", "al", "a"}


def reaplica_sc_runin(en, es):
    """Rasgo con encabezado run-in en versalitas («‹sc›Storm‹/sc› ‹sc›Strike.‹/sc› When
    you…»): si el modelo perdió los tokens, se envuelve el arranque del ES contando las
    palabras plenas del prefijo EN (los conectores de/del/la… no cuentan)."""
    m = re.match(r"^((?:‹sc›[^‹]{1,40}‹/sc›[ ]*)+)(.{15,})$", en, re.S)
    if not m or "‹sc›" in es:
        return es
    plenas_en = len(m.group(1).replace("‹sc›", "").replace("‹/sc›", "").split())
    tokens = es.split()
    pref, cont, resto_i = [], 0, None
    for i2, w in enumerate(tokens):
        wl = w.lower().strip(".,:;»«")
        if cont >= plenas_en and wl not in CONECTORES:
            resto_i = i2
            break
        pref.append(w)
        if wl not in CONECTORES:
            cont += 1
    if resto_i is None or not pref:
        return es
    return "‹sc›" + " ".join(pref) + "‹/sc› " + " ".join(tokens[resto_i:])


def marcas_ok(en, es):
    """El prefijo en versalitas del original debe sobrevivir en la traducción."""
    return "‹sc›" not in en or "‹sc›" in es


def igual_al_origen(en, es):
    """Traducción idéntica al original = el modelo no tradujo: se rechaza para que el
    bloque vaya a rescate (y si tampoco ahí, se conserva el original vectorial intacto)."""
    q = lambda s: re.sub(r"[^a-záéíóúñüA-ZÁÉÍÓÚÑÜ]+", " ", normaliza_tokens(str(s)).lower()).strip()
    return q(en) == q(es)


def a_html(t, definiciones=False):
    t = normaliza_tokens(t)
    # listas de valores («Atletismo +6 Percepción +3…»): una entrada por renglón,
    # como en la ficha original; si no, salen todas seguidas y no se leen
    if len(re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]\s*\+\d", t)) >= 3:
        t = re.sub(r"(\+\d+)\s+(?=[A-ZÁÉÍÓÚÑ*])", r"\1\n\n", t)
    # línea de ataques: cada arma en su renglón
    if len(re.findall(r"a impactar", t)) >= 2:
        t = re.sub(r"(?<=[.,])\s+(?=\*\*[A-ZÁÉÍÓÚÑ])", "\n\n", t)
    # listas de definiciones: cada «**Término.**» abre entrada nueva (sangría francesa);
    # \*{2,3} cubre también los rasgos «***Nombre - Acción:***» de los statblocks
    t = re.sub(r"(?<=[.:!?»])\s+(?=\*{2,3}[^*]{2,40}?[.:]\*{2,3})", "\n\n", t)
    t = H.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t, flags=re.S)
    t = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", t, flags=re.S)
    t = t.replace("‹sc›", '<span style="font-variant:small-caps">').replace("‹/sc›", "</span>")
    t = re.sub(r"‹c:([0-9a-f]{6})›", lambda m: f'<span style="color:#{m.group(1)}">', t)
    t = t.replace("‹/c›", "</span>")
    t = t.replace("‹g›", '<span style="font-size:1.35em">').replace("‹/g›", "</span>")
    # el modelo a veces devuelve los tokens mutilados («/sc›», «‹sc», «‹c:...»):
    # cualquier resto DEBE desaparecer o se imprime literal en la página
    t = re.sub(r"‹[^›]{0,24}›?|&lt;/?(?:sc|c|g)&gt;|(?<![\w>])/(?:sc|c|g)›", "", t)
    t = re.sub(r"</?(?:sc|c|g)>", "", t)
    t = re.sub(r"&lt;/?[a-zA-Z][^&]{0,30}&gt;", "", t)      # etiquetas que soltó el modelo
    t = re.sub(r"(?<![\w=\"])/(?:span|sc|c|g|p|b|i)\s*&gt;", "", t)   # cierres sueltos
    # SOLO delimitadores de token ‹›: incluir «» aquí se come la letra inicial de
    # palabras españolas tras comillas («gran» → «ran»)
    t = re.sub(r"[‹›]\s*/?\s*(?:sc|c|g|span)\s*[‹›]?", "", t)
    parrafos = [p.strip() for p in t.split("\n\n") if p.strip()]
    cls = " class='def'" if definiciones else ""
    return "".join(f"<p{cls}>{p}</p>" for p in parrafos)


def es_lista_definiciones(t):
    """≥3 entradas que empiezan con término en negrita seguido de punto."""
    return len(re.findall(r"\*{2,3}[^*]{2,40}?[.:]\*{2,3}", t)) >= 3


def lineas_render(html, css, ancho):
    """Cuenta las líneas que el MOTOR HTML produce realmente para ese ancho.
    Medir con fitz.Font subestima el ancho (el motor resuelve font-family a otra fuente)."""
    tmp = fitz.open()
    pg = tmp.new_page(width=ancho + 40, height=400)
    pg.insert_htmlbox(fitz.Rect(10, 10, ancho + 10, 390), html, css=css)
    n = sum(len(bl["lines"]) for bl in pg.get_text("dict")["blocks"] if bl.get("type") == 0)
    tmp.close()
    return n


def offset_tinta(html, css, ancho):
    """A cuántos puntos por debajo del borde superior de la caja queda la TINTA de la
    primera línea (medida por píxeles: las métricas de bbox mienten porque el
    ascendente de la fuente del motor HTML queda muy por encima de las mayúsculas)."""
    tmp = fitz.open()
    pg = tmp.new_page(width=ancho + 40, height=600)
    pg.insert_htmlbox(fitz.Rect(10, 10, ancho + 10, 590), html, css=css)
    pix = pg.get_pixmap()          # matriz identidad: 1 px = 1 pt
    s, w, n = pix.samples, pix.width, pix.n
    tmp.close()
    for y in range(10, 300):
        fila = s[y * w * n:(y + 1) * w * n]
        if any(fila[i] < 128 for i in range(0, len(fila), n)):
            return float(y - 10)
    return 0.0


def limite_derecho(b, bloques, page):
    """Hasta dónde puede crecer la caja hacia la derecha sin invadir a un vecino ni
    salirse de la columna de texto (el español crece ~15-20 % y encoger el cuerpo
    es peor que ensanchar cuando hay espacio libre real). La columna se estima con
    el máximo x1 de los bloques MULTILÍNEA: los de una línea (números de página,
    rótulos sueltos) la sobreestiman y el texto acabaría fuera de la retícula."""
    x0, y0, x1, y1 = b["bbox"]
    multi = [o["bbox"][2] for o in bloques if o.get("lineas", 1) > 1]
    col = max(multi) if multi else max((o["bbox"][2] for o in bloques), default=x1)
    lim = min(col, page.rect.x1 - 8)
    for o in bloques:
        if o["id"] == b["id"]:
            continue
        ox0, oy0, ox1, oy1 = o["bbox"]
        if ox0 >= x1 - 1 and not (oy1 < y0 or oy0 > y1):
            lim = min(lim, ox0 - 4)
    return max(x1, lim)


def holgura(b, bloques, alto_pagina, tope=4):
    """Espacio libre debajo antes de invadir al vecino (el español crece ~20 %)."""
    x0, _, x1, y1 = b["bbox"]
    limite = alto_pagina - 4
    for o in bloques:
        if o["id"] == b["id"]:
            continue
        ox0, oy0, ox1, _ = o["bbox"]
        if oy0 >= y1 - 1 and not (ox1 < x0 or ox0 > x1):
            limite = min(limite, oy0 - 2)
    return max(0.0, min(limite - y1, tope))


def traduce(pg):
    datos = extrae(pg)
    pedido = {b["id"]: b["texto"] for b in datos["bloques"] if len(b["texto"]) > 2}
    pedido.update({f["id"]: f["texto"] for f in datos.get("tabla_frases", []) if len(f["texto"]) > 2})
    if not pedido:
        print(f"p{pg}: sin texto")
        return {}
    glos = glosario_pagina("\n".join(pedido.values()))
    salida = {}
    claves = [k for k in pedido if not LEGAL.search(pedido[k])]   # marcas/legal: se conservan
    for j in range(0, len(claves), 10):
        lote = {k: pedido[k] for k in claves[j:j + 10]}
        for _ in range(3):
            msj = [{"role": "system", "content": _t.REGLAS + ("\n\nGLOSARIO:\n" + glos if glos else "")},
                   {"role": "user", "content": json.dumps(lote, ensure_ascii=False)}]
            try:
                r = json.loads(_t.ollama(MOD, msj, timeout=1200))
            except Exception:
                continue
            bien = {k: reaplica_sc_runin(lote[k], ajusta_sc(lote[k], normaliza_tokens(desenvuelve(r.get(k, "")))))
                    for k in lote}
            ok = [k for k in lote if bien[k] and _t.numeros_de(bien[k]) == _t.numeros_de(lote[k])
                  and not igual_al_origen(lote[k], bien[k]) and marcas_ok(lote[k], bien[k])]
            salida.update({k: desduplica(bien[k]) for k in ok})
            if len(ok) == len(lote):
                break
        for k in [x for x in lote if x not in salida]:            # rescate individual
            for _ in range(2):
                msj = [{"role": "system", "content": _t.REGLAS
                        + "\n- El texto recibido está en INGLÉS: devuélvelo TRADUCIDO al español; PROHIBIDO devolverlo igual."
                        + ("\n\nGLOSARIO:\n" + glos if glos else "")},
                       {"role": "user", "content": json.dumps({k: lote[k]}, ensure_ascii=False)}]
                try:
                    r = json.loads(_t.ollama(MOD, msj, timeout=900))
                except Exception:
                    continue
                v = desenvuelve(r.get(k, "") or (next(iter(r.values())) if len(r) == 1 else ""))
                v = reaplica_sc_runin(lote[k], ajusta_sc(lote[k], normaliza_tokens(v)))
                if v and _t.numeros_de(v) == _t.numeros_de(lote[k]) and not igual_al_origen(lote[k], v):
                    salida[k] = desduplica(v)
                    break
    # Encabezado en MAYÚSCULAS → traducción en MAYÚSCULAS, impuesto aquí (el modelo
    # ignora la regla a veces); no aplica si hay ‹tokens› que se romperían.
    for k, v in salida.items():
        en0 = pedido.get(k, "")
        letras = re.sub(r"[^A-Za-zÁÉÍÓÚÑÜáéíóúñü]", "", en0)
        if len(letras) >= 3 and letras.isupper() and "‹" not in v and not v.isupper():
            salida[k] = v.upper()
    (BLOQ / f"pag-{pg:03d}.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1))
    (ES / f"pag-{pg:03d}.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1))
    conservados = len(pedido) - len(claves)
    print(f"p{pg}: {len(salida)}/{len(claves)} traducidos"
          + (f", {conservados} legales conservados" if conservados else ""))
    return salida


def _estilo_en(page, rect):
    """(tamaño, color, negrita, serif) del texto original bajo ese rect."""
    spans = []
    for b in page.get_text("dict", clip=rect)["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            spans += [s for s in ln["spans"] if s["text"].strip()]
    if not spans:
        return 8.0, 0, False, False
    s0 = max(spans, key=lambda s: len(s["text"]))
    return (s0["size"], s0["color"],
            bool(s0["flags"] & 16) or "Bold" in s0["font"], bool(s0["flags"] & 4))


def compone(pg, doc):
    fes = ES / f"pag-{pg:03d}.json"
    if not fes.exists():
        print(f"p{pg}: sin traducción")
        return False
    es = json.loads(fes.read_text())
    fbl = BLOQ / f"pag-{pg:03d}.json"
    datos = json.loads(fbl.read_text()) if fbl.exists() else extrae(pg, doc)
    page = doc[pg - 1]
    glifos = [fitz.Rect(ch[3]) for sp in page.get_texttrace() for ch in sp["chars"]]
    # Los encabezados llevan una copia VECTORIAL del texto (line-art). MuPDF solo borra
    # sub-trazos totalmente cubiertos por la redacción: una letra que sobresale 0.3 pt
    # sobrevive entera. Se cubren los dibujos chicos que caen mayormente dentro del
    # bloque (altura >3 excluye las reglas doradas de ~1.5 pt, que deben conservarse).
    trazos = []
    for dr in page.get_drawings():
        tr = fitz.Rect(dr["rect"])
        if 3 < tr.height < 60 and tr.width < page.rect.width * 0.9:
            trazos.append(tr)
    # Bloques SIN traducción (clave ausente o null) deben quedar intactos: MuPDF borra
    # todo glifo que INTERSECA el rect de redacción, así que un solape de <1 pt con el
    # bloque de abajo basta para tragarse un encabezado entero.
    protegidos = [fitz.Rect(b2["bbox"]) for b2 in datos["bloques"]
                  if es.get(b2["id"]) is None]
    pendientes, avisos = [], []
    for b in datos["bloques"]:
        v = es.get(b["id"])
        if v == "~":                       # absorbido por otro bloque: borrar sin reinsertar
            page.add_redact_annot(fitz.Rect(b["bbox"]), fill=False)
            continue
        if isinstance(v, dict) and v.get("t"):     # control fino {"t","caja","size","lineas","centrado","alin"}
            if v.get("caja"):
                # borrar el texto original COMPLETO aunque la caja nueva sea más chica
                page.add_redact_annot(fitz.Rect(b["bbox"]), fill=False)
                b = dict(b, bbox=v["caja"])
            if v.get("size"):
                b = dict(b, size=v["size"])
            if v.get("lineas"):
                b = dict(b, lineas=v["lineas"])
            if "centrado" in v:
                b = dict(b, centrado=v["centrado"])
            if v.get("alin"):
                b = dict(b, alin=v["alin"])
            v = v["t"]
        if not isinstance(v, str) or not v.strip():
            continue
        # Las capas de sombra del original pintan glifos FUERA del bbox que reporta
        # get_text (la capital del encabezado por arriba, la última letra por la derecha).
        # Se redacta la unión de los glifos realmente pintados (texttrace), acotada para
        # no invadir a los vecinos.
        r = fitz.Rect(b["bbox"])
        smax = b.get("size_max", b["size"])
        zona = fitz.Rect(r.x0 - 2, r.y0 - 2, r.x1 + 2, r.y1 + 2)
        tope = fitz.Rect(r.x0 - smax * 0.6, r.y0 - smax * 0.8, r.x1 + smax * 2.2, r.y1 + 3)
        ext = fitz.Rect(r)
        for cr in glifos:
            if cr.intersects(zona):
                ext |= (cr & tope)
        for tr in trazos:
            if tr.intersects(zona) and (tr & zona).get_area() > tr.get_area() * 0.5:
                ext |= (tr + (-1, -1, 1, 1))
        # recortar contra los bloques protegidos: si el rect solo los roza por un
        # borde, se encoge; si el solape es sustancial no hay recorte posible
        for pr in protegidos:
            if not ext.intersects(pr) or ext.contains(pr):
                continue
            inter = ext & pr
            if inter.height <= min(ext.height, pr.height) * 0.6:
                if pr.y1 <= (ext.y0 + ext.y1) / 2:
                    ext.y0 = max(ext.y0, pr.y1 + 0.25)
                elif pr.y0 >= (ext.y0 + ext.y1) / 2:
                    ext.y1 = min(ext.y1, pr.y0 - 0.25)
        page.add_redact_annot(ext, fill=False)   # sin relleno: solo borrar glifos
        pendientes.append((b, v))
    # === celdas de tabla: frases traducidas + ordinales (1st → 1.º); los números
    # de la tabla no se tocan jamás ===
    frt = {f["id"]: f for f in datos.get("tabla_frases", [])}
    regiones = [fitz.Rect(r) for r in datos.get("tablas", [])]
    celdas = []
    for fid, f in frt.items():
        v = es.get(fid)
        if not isinstance(v, str) or not v.strip() or v == "~":
            continue
        celdas.append((fitz.Rect(f["rect"]), v, _estilo_en(page, fitz.Rect(f["rect"]))))
    if regiones:
        for w in page.get_text("words"):
            mo = ORDINAL.match(w[4])
            wr = fitz.Rect(w[:4])
            if mo and any(wr.intersects(r) for r in regiones):
                celdas.append((wr, f"{mo.group(1)}.º", _estilo_en(page, wr)))
    for cr, _v, _e in celdas:
        ext = fitz.Rect(cr)
        zona = fitz.Rect(cr.x0 - 1, cr.y0 - 1, cr.x1 + 1, cr.y1 + 1)
        for g in glifos:
            if g.intersects(zona):
                ext |= (g & fitz.Rect(cr.x0 - 4, cr.y0 - 4, cr.x1 + 6, cr.y1 + 3))
        page.add_redact_annot(ext)
    if not pendientes and not celdas:
        print(f"  p{pg}: nada que componer")
        return False
    # line_art: "auto" (defecto) deja que la redacción borre los sub-trazos vectoriales
    # cubiertos (copias line-art de encabezados, estilo GM Binder); "none" protege TODO
    # el arte vectorial (zines con adornos que tocan el texto): proyecto.json →
    # "compose": {"line_art": "none"}
    if _proyecto.get("compose", {}).get("line_art", "auto") == "none":
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                              graphics=fitz.PDF_REDACT_LINE_ART_NONE)
    else:
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    for cr, v, (tam0, col0, neg0, ser0) in celdas:
        rgb = f"rgb({col0 >> 16 & 255},{col0 >> 8 & 255},{col0 & 255})"
        fam = "serif" if ser0 else "sans-serif"
        cuerpo = f"<b>{H.escape(v)}</b>" if neg0 else H.escape(v)
        caja = fitz.Rect(cr.x0 - 1, cr.y0 - 1, cr.x1 + 2, cr.y1 + 2)
        for factor in (1.0, 0.9, 0.8, 0.72, 0.64, 0.56, 0.5):
            css = (f"* {{font-family:{fam}; font-size:{tam0*factor:.1f}px; color:{rgb};"
                   f" margin:0; line-height:1.05;}}")
            sobra, _ = page.insert_htmlbox(caja, cuerpo, css=css, scale_low=0.6)
            if sobra >= 0:
                break
    # sube_multilinea: compensar la tinta baja del motor HTML también en párrafos
    # (proyecto.json → "compose": {"sube": true}; el defecto false replica el
    # comportamiento validado en libros de retícula densa)
    sube_multi = bool(_proyecto.get("compose", {}).get("sube", False))
    for b, v in pendientes:
        r = fitz.Rect(b["bbox"])
        col = b["color"]
        rgb = f"rgb({col >> 16 & 255},{col >> 8 & 255},{col & 255})"
        fam = "serif" if b.get("serif") else "sans-serif"
        alto_b, ancho_b = r.y1 - r.y0, r.x1 - r.x0
        # listón VERTICAL (texto rotado en el original): componer con rotate, no con
        # el flujo horizontal — si no, sale hecho trizas en una columna angosta
        if b.get("lineas") == 1 and alto_b > 2.0 * ancho_b and alto_b > 36:
            rot = 270 if (r.x0 + r.x1) / 2 < page.rect.width / 2 else 90
            caja_v = fitz.Rect(r.x0 - 1, r.y0 - 1, r.x1 + 2, r.y1 + 2)
            html_v = a_html(v)
            escrito = False
            for factor in (1.0, 0.9, 0.8, 0.7, 0.6):
                css_v = (f"* {{font-family:{fam}; font-size:{b['size']*factor:.1f}px;"
                         f" color:{rgb}; margin:0; line-height:1.0; text-align:left;}}")
                sobra, _ = page.insert_htmlbox(caja_v, html_v, css=css_v,
                                               scale_low=0.7, rotate=rot)
                if sobra >= 0:
                    escrito = True
                    break
            if not escrito:
                avisos.append(f"{b['id']}: vertical no cupo → {v[:45]!r}")
            continue
        # ensanchar hacia la derecha si hay espacio libre (no en bloques centrados:
        # perderían la simetría con que fueron maquetados). En multilínea el tope es
        # ~14 %: más que eso ya se sale visualmente de la retícula original.
        if b.get("centrado"):
            x1_caja = r.x1
        else:
            lim = limite_derecho(b, datos["bloques"], page)
            multi = [o["bbox"][2] for o in datos["bloques"] if o.get("lineas", 1) > 1]
            col_x = max(multi) if multi else lim
            if b.get("lineas") == 1:
                x1_caja = lim
            elif col_x - r.x1 < 25:    # el bloque ya abarca la columna: puede crecer
                x1_caja = min(lim, r.x1 + max(12.0, 0.14 * ancho_b))
            else:                      # bloque de barra lateral / caja propia: NO salirse
                x1_caja = r.x1
        sube = 0.62 * b["size"] if sube_multi else 1.0
        caja = fitz.Rect(r.x0 - 1, r.y0 - sube, x1_caja + 1,
                         r.y1 + holgura(b, datos["bloques"], page.rect.y1))
        # Un rótulo de una sola línea (p. ej. «Character Name: …») NO puede partirse en
        # dos: se calcula el cuerpo con el que el texto traducido cabe a lo ancho, y la
        # caja se coloca con la sonda de tinta (las métricas del motor HTML mienten).
        if b.get("lineas") == 1:
            fam0 = "serif" if b.get("serif") else "sans-serif"
            alin0 = b.get("alin") or ("center" if b.get("centrado") else "left")
            html0 = a_html(v)
            ancho0 = (x1_caja - r.x0) - 4
            tam = b["size"]
            while tam > 5:
                css0 = (f"* {{font-family:{fam0}; font-size:{tam:.1f}px; margin:0;"
                        f" line-height:1.05; text-align:{alin0};}}")
                if lineas_render(html0, css0, ancho0) <= 1:
                    break
                tam -= 0.5
            b = dict(b, size=round(tam, 2))
            css_fin = (f"* {{font-family:{fam0}; font-size:{tam:.1f}px; margin:0;"
                       f" line-height:1.05; text-align:{alin0};}}")
            sube1_probe = offset_tinta(html0, css_fin, max(ancho0, 30))
            # recortar la caja al ancho que el texto realmente necesita: dejarla en
            # el límite hace que el renglón invada visualmente la retícula
            if not b.get("centrado"):
                plano0 = re.sub(r"‹[^›]*›|\*+", "", v)
                base0 = ("tibo" if "**" in v else "tiro") if b.get("serif") else ("hebo" if "**" in v else "helv")
                w_need = fitz.Font(base0).text_length(plano0, tam) * 1.12 + 8
                x1_caja = min(x1_caja, r.x0 + max(ancho_b, w_need))
            # insert_htmlbox necesita ~2.2x el cuerpo en ALTO para una línea; con la
            # caja original aplica scale_low y el renglón sale diminuto aunque quepa
            # a lo ancho. Se le da aire vertical sin invadir al vecino de abajo.
            libre = holgura(b, datos["bloques"], page.rect.y1, tope=999)
            sube1 = sube1_probe if sube1_probe > 0 else 0.62 * tam
            caja = fitz.Rect(r.x0 - 1, r.y0 - sube1, x1_caja + 1,
                             min(r.y1 + libre, r.y0 - sube1 + max(r.height + 2, tam * 2.35)))
        deflist = es_lista_definiciones(v)
        html = a_html(v, definiciones=deflist)
        escrito = False
        # Si el vecino de abajo está cerca, NO crecer: el texto debe caber en la caja
        # original reduciendo el cuerpo, o los bloques se encimarán visualmente.
        holg = holgura(b, datos["bloques"], page.rect.y1)
        apretado = holg < 16 and b.get("lineas") != 1
        if apretado:
            caja = fitz.Rect(r.x0 - 1, r.y0 - 1, x1_caja + 1, r.y1 + min(holg, 3))
        factores = ((1.0, 0.92, 0.84, 0.76, 0.68, 0.6, 0.52, 0.45) if apretado
                    else (1.0, 0.92, 0.84, 0.76, 0.68, 0.6)) if not deflist else (0.95, 0.88, 0.8, 0.72, 0.64, 0.56, 0.5)
        for factor in factores:
            alin = b.get("alin") or ("center" if b.get("centrado") else "left")
            # sangría francesa como el original: término afuera, definición indentada
            extra_css = ("p.def {margin:0 0 3px 0; padding-left:11px; text-indent:-11px;}"
                         if deflist else "")
            css = (f"* {{font-family:{fam}; font-size:{b['size']*factor:.1f}px;"
                   f" color:{rgb}; margin:0; line-height:{1.05 if b.get('lineas') == 1 else 1.15};"
                   f" text-align:{alin};}} " + extra_css)
            sobra, _esc = page.insert_htmlbox(caja, html, css=css, scale_low=0.7)
            if sobra >= 0:
                escrito = True
                break
        if not escrito:
            # último recurso: escribir SIEMPRE aunque el motor tenga que encoger más;
            # dejar el bloque sin insertar pierde el texto (la redacción ya lo borró)
            css_min = (f"* {{font-family:{fam}; font-size:{b['size']*0.45:.1f}px;"
                       f" color:{rgb}; margin:0; line-height:1.1;"
                       f" text-align:{b.get('alin') or 'left'};}}")
            sobra, _esc = page.insert_htmlbox(caja, html, css=css_min, scale_low=0.3)
            if sobra >= 0:
                avisos.append(f"{b['id']}: forzado a escala mínima → {v[:45]!r}")
            else:
                avisos.append(f"{b['id']}: no cupo NI FORZADO (texto perdido) → {v[:45]!r}")
    print(f"  p{pg}: {len(pendientes)} bloques, {len(avisos)} con problema")
    for a in avisos:
        print(f"    ⚠ {a}")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for m in ("extrae", "traduce", "compone", "piloto"):
        ap.add_argument(f"--{m}", nargs=2, type=int, metavar=("INI", "FIN"))
    a = ap.parse_args()
    rango = a.extrae or a.traduce or a.compone or a.piloto
    if not rango:
        ap.error("indica --extrae / --traduce / --compone / --piloto INI FIN")
    ini, fin = rango
    if a.extrae or a.piloto:
        doc = abre()
        for pg in range(ini, fin + 1):
            d = extrae(pg, doc)
            (BLOQ / f"pag-{pg:03d}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
            print(f"p{pg}: {len(d['bloques'])} bloques")
        doc.close()
    if a.traduce or a.piloto:
        for pg in range(ini, fin + 1):
            if (ES / f"pag-{pg:03d}.json").exists() and (BLOQ / f"pag-{pg:03d}.json").exists():
                print(f"p{pg}: ya traducida, salto")
                continue
            traduce(pg)
    if a.compone or a.piloto:
        doc = abre()
        for pg in range(ini, fin + 1):
            compone(pg, doc)
        destino = SALIDA / f"paginas-{ini}-{fin}.pdf"
        doc.select(list(range(ini - 1, fin)))
        doc.save(str(destino), deflate=True)
        doc.close()
        print(f"✓ {destino}")
