#!/usr/bin/env python3
"""35_traduce_ollama.py — genera traduccion/es/pag-NNN.json con un modelo LOCAL (Ollama).

Sustituye el paso autoral del ciclo F4: dump en-bloques → ESTE SCRIPT → 30_compose → 40_qa.
El texto traducido lo produce tu modelo local en tu máquina; el script solo orquesta.

Uso:
  venv/bin/python 35_traduce_ollama.py 97            # una página
  venv/bin/python 35_traduce_ollama.py 97 111        # rango (cap 5 completo)
  venv/bin/python 35_traduce_ollama.py 97 111 -m gpt-oss:120b
  venv/bin/python 35_traduce_ollama.py 97 --forzar   # re-traducir aunque exista el .json
  venv/bin/python 35_traduce_ollama.py 97 --solo-traducir   # sin compose/QA

Después de cada página corre 30_compose + 40_qa y actualiza progress.csv si quedó limpia.
Fallas típicas y qué hacer:
  overflow  → abrir es/pag-NNN.json y acortar la traducción de ese bloque (o "size": 8.5)
  números   → casi siempre OCR del EN (ld4→1d4 ya se normaliza); si es letra-número
              (C2O=C20) agregar override en qa/v4-overrides.json
  statblock → páginas con tipos stat_* requieren formato __statblocks__ a mano
              (ver traduccion/es/pag-058.json como ejemplo)
Convenciones del es/*.json (por si editas a mano): null=dejar original (mapas),
"~"=solo parche, dict{t,type,dropcap,extiende,size}. Detalle en plan-ejecucion.md.
"""
import argparse, csv, json, re, subprocess, sys, time, unicodedata, urllib.request
from pathlib import Path

P = Path(__file__).resolve().parent.parent
EN = P / "traduccion" / "en-bloques"
ES = P / "traduccion" / "es"
API = "http://localhost:11434/api/chat"

import _proyecto
REGLAS = _proyecto.reglas_traductor()


def glosario_txt():
    filas = [l.split("\t")[:2] for l in (P / "traduccion" / "glosario.tsv").read_text().splitlines()[1:] if "\t" in l]
    return "\n".join(f"{en} = {es}" for en, es in filas)


def ollama(modelo, mensajes, timeout=900):
    cuerpo = {"model": modelo, "messages": mensajes, "stream": False, "format": "json",
              "options": {"temperature": 0.2, "num_ctx": 16384, "num_predict": 8192}}
    # thinking + format=json en prompts largos degenera (timeouts); qwen/deepseek lo traen por defecto
    if "qwen" in modelo or "deepseek" in modelo:
        cuerpo["think"] = False
    req = urllib.request.Request(API, json.dumps(cuerpo).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["message"]["content"]


DANIOS = {"piercing": "perforante", "slashing": "cortante", "bludgeoning": "contundente",
          "psychic": "psíquico", "necrotic": "necrótico", "radiant": "radiante",
          "force": "de fuerza", "fire": "de fuego", "cold": "de frío", "acid": "de ácido",
          "poison": "de veneno", "lightning": "de relámpago", "thunder": "de trueno"}
DANIO_EN = re.compile(r"\b(" + "|".join(DANIOS) + r")\s+damage\b")
DANIO_ES = re.compile(r"daño (?:de |por )?([a-záéíóúñA-ZÁÉÍÓÚÑ]{3,})")
NO_DANIO = {"del", "por", "con", "que", "adicional", "extra", "máximo", "normal", "igual", "doble"}


def alinea_danio(en_t, es_t):
    """Empareja posicionalmente los tipos de daño EN con las frases «daño X» del ES
    y las fuerza al canon SRD. Si los conteos no cuadran, no toca nada."""
    tipos = DANIO_EN.findall(en_t.lower())
    if not tipos:
        return es_t
    ocurr = [mo for mo in DANIO_ES.finditer(es_t) if mo.group(1).lower() not in NO_DANIO]
    if len(ocurr) != len(tipos):
        return es_t
    out = es_t
    for mo, tipo in zip(reversed(ocurr), reversed(tipos)):
        out = out[:mo.start()] + f"daño {DANIOS[tipo]}" + out[mo.end():]
    return out


RUNIN_EN = re.compile(r"^([A-Z][A-Za-z''\- ]{1,38}\.)\s+(?=[A-Z\"«])")


def marca_runins(en_t, es_t):
    """Run-ins del libro (p.ej. 'Development. …' en ***negrita-cursiva***): el OCR pierde
    el estilo; se detectan en EN (frase title-case ≤5 palabras + punto) y se marcan en ES."""
    ens, ess = en_t.split("\n\n"), es_t.split("\n\n")
    if len(ens) != len(ess):
        # párrafos EN rotos por hifenación: intentar solo el primero
        ens, ess = ens[:1], [ess[0]] if ess else []
        resto = es_t.split("\n\n")[1:]
    else:
        resto = None
    out = []
    for pe, ps in zip(ens, ess):
        me = RUNIN_EN.match(pe)
        if me and not ps.startswith(("*", "«", "‹")):
            palabras = me.group(1)[:-1].split()
            if len(palabras) <= 5 and palabras[-1][0].isupper():
                ms = re.match(r"^([A-ZÁÉÍÓÚÑ¿¡][^.:\n]{1,45}\.)\s+", ps)
                if ms:
                    ps = f"***{ms.group(1)}*** " + ps[ms.end():]
        out.append(ps)
    return "\n\n".join(out + (resto or []))


def marca_dropcap(texto, ancho=20):
    """'El cuarto fragmento de la *Vara*…' → ('E', '‹sc›l cuarto fragmento‹/sc› de la *Vara*…')"""
    letra, resto = texto[0], texto[1:]
    palabras, sc, n = resto.split(" "), [], 0
    for w in palabras:
        if n >= ancho or w.startswith(("*", "«")):
            break
        sc.append(w); n += len(w) + 1
    return letra, f"‹sc›{' '.join(sc)}‹/sc› {' '.join(palabras[len(sc):])}".strip()


def traduce_pagina(pg, modelo, glos):
    dump = json.loads((EN / f"pag-{pg:03d}.json").read_text())
    bloques = {b["id"]: b for b in dump["blocks"]}
    if any(b["type"].startswith(("stat", "panel")) for b in bloques.values()):
        print(f"  ⚠ p{pg}: tipos stat/panel — probable statblock, revisar formato a mano tras traducir")
    pedido = {bid: b["text"] for bid, b in bloques.items()}
    msj = [{"role": "system", "content": REGLAS + "\n\nGLOSARIO (en = es):\n" + glos},
           {"role": "user", "content": json.dumps(pedido, ensure_ascii=False)}]
    out = None
    for intento in range(3):
        try:
            crudo = ollama(modelo, msj)
            cand = json.loads(crudo)
            faltan = {k for k in pedido if not str(cand.get(k, "")).strip()}
            if faltan:
                raise ValueError(f"faltan claves {sorted(faltan)}")
            out = {k: str(cand[k]) for k in pedido}
            break
        except Exception as e:
            print(f"  reintento {intento+1}/3 p{pg}: {e}")
            msj.append({"role": "user", "content": f"Respuesta inválida ({e}). Devuelve el JSON completo con todas las claves."})
    if out is None:
        # fallback: bloque por bloque
        out = {}
        for bid, txt in pedido.items():
            crudo = ollama(modelo, [{"role": "system", "content": REGLAS + "\n\nGLOSARIO:\n" + glos},
                                    {"role": "user", "content": json.dumps({bid: txt}, ensure_ascii=False)}])
            resp = json.loads(crudo)
            out[bid] = str(resp.get(bid, "") or (next(iter(resp.values())) if len(resp) == 1 else ""))
    # verificación de alineación: nombres propios del EN deben aparecer en SU bloque ES
    # (detecta contenido rotado entre claves; los desalineados se re-traducen sueltos)
    mal = []
    for bid, txt in pedido.items():
        nom = {w[:4].lower() for w in re.findall(r"\b[A-Z][a-záéíóúñ]{3,}", txt) if w[:4].isalpha()}
        if len(nom) >= 2:
            eslow = sin_acentos(str(out.get(bid, "")).lower())
            if not any(sin_acentos(n) in eslow for n in nom):
                mal.append(bid)
    # bloques devueltos EN INGLÉS (idénticos al EN o con stopwords abundantes) → sueltos
    ing = []
    for bid, txt in pedido.items():
        est = str(out.get(bid, ""))
        if est.strip() and est.strip() == txt.strip():
            ing.append(bid)
        elif len(est) > 60 and len(re.findall(r"\b(the|and|with|from|that|this|are|you|is|of|for)\b", est)) >= 4:
            ing.append(bid)
    # footers que perdieron el número de capítulo (rotación) → también sueltos
    pies = [bid for bid, txt in pedido.items()
            if bloques[bid]["type"] == "footer"
            and re.search(r"CHAPTER\s+(\d+)", txt, re.I)
            and re.search(r"CHAPTER\s+(\d+)", txt, re.I).group(1) not in str(out.get(bid, ""))]
    for bid in set(mal) | set(ing) | set(pies):
        try:
            crudo = ollama(modelo, [{"role": "system", "content": REGLAS + "\n\nGLOSARIO:\n" + glos},
                                    {"role": "user", "content": json.dumps({bid: pedido[bid]}, ensure_ascii=False)}])
            resp = json.loads(crudo)
            nuevo = str(resp.get(bid, "")).strip()
            if not nuevo and len(resp) == 1:  # qwen a veces renombra la clave (b00 sobre todo)
                nuevo = str(next(iter(resp.values()))).strip()
            if nuevo:
                out[bid] = nuevo
        except Exception:
            pass
    if mal:
        print(f"  ⇄ realineados: {sorted(mal)}")
    if ing:
        print(f"  🇬🇧 re-traducidos: {sorted(ing)}")
    # post-proceso: dropcaps deterministas a partir del meta del dump
    final = {}
    for bid in sorted(out):
        t = unicodedata.normalize("NFC", out[bid]).strip()
        t = re.sub(r"(\d)\.(\d{3})\b", r"\1,\2", t)  # miles: 1.900 → 1,900
        t = re.sub(r"(?<=[a-záéíóúñ,;])\n\n(?=[a-záéíóúñ])", " ", t)  # saltos OCR a mitad de frase
        t = alinea_danio(bloques[bid]["text"], t)
        if bloques[bid]["type"] == "footer":
            mo = re.search(r"CHAPTER\s+(\d+)", bloques[bid]["text"], re.I)
            if mo and mo.group(1) not in t:  # folio determinista si el modelo lo perdió
                t = f"Capítulo {mo.group(1)} | {t.split('|')[-1].strip()}" if "|" in t else f"Capítulo {mo.group(1)}"
        if bloques[bid]["type"] == "cuerpo":
            t = marca_runins(bloques[bid]["text"], t)
        if bloques[bid]["meta"].get("dropcap") and len(t) > 30:
            letra, cuerpo = marca_dropcap(t)
            final[bid] = {"t": cuerpo, "dropcap": letra}
        else:
            final[bid] = t
    return final


def clases_catalogo():
    with open(P / "corpus" / "catalogo.csv") as f:
        return {int(r[0]): r[3] for r in list(csv.reader(f))[1:] if r and r[0].isdigit()}


def numeros_de(t):
    return sorted(re.findall(r"\d+", re.sub(r"(\d),(\d)", r"\1\2", t)))


def acorta_overflow(pg, ids, modelo, glos):
    """Los bloques que no cupieron se reescriben ~20% más cortos — por el modelo LOCAL."""
    ruta = ES / f"pag-{pg:03d}.json"
    es = json.loads(ruta.read_text())
    pedido = {}
    for bid in ids:
        v = es.get(bid)
        v = v.get("t") if isinstance(v, dict) else v
        if not isinstance(v, str):
            return False
        pedido[bid] = v
    msj = [{"role": "system", "content": REGLAS + "\n\nGLOSARIO (en = es):\n" + glos},
           {"role": "user", "content": "Estos bloques ya traducidos NO caben en su caja. Reescríbelos ~20% más cortos, conservando significado, glosario, marcado y con números y dados IDÉNTICOS. Devuelve JSON con las mismas claves.\n"
            + json.dumps(pedido, ensure_ascii=False)}]
    try:
        cand = json.loads(ollama(modelo, msj))
    except Exception:
        return False
    terminos = [l.split(" = ")[1].strip().lower() for l in glos.splitlines()
                if " = " in l and len(l.split(" = ")[1].strip()) > 4]
    cambiados = 0
    for bid in ids:
        nuevo = str(cand.get(bid, "")).strip()
        if not nuevo or numeros_de(nuevo) != numeros_de(pedido[bid]):
            continue  # guardia: el acortado no puede alterar números
        presentes = [x for x in terminos if x in pedido[bid].lower()]
        if any(x not in nuevo.lower() for x in presentes):
            continue  # guardia: ni perder términos del glosario
        if isinstance(es[bid], dict):
            es[bid]["t"] = nuevo
        else:
            es[bid] = nuevo
        cambiados += 1
    if cambiados:
        ruta.write_text(json.dumps(es, ensure_ascii=False, indent=1))
    return bool(cambiados)


def reduce_size(pg, ids, tam=8.5):
    """Última palanca contra overflow: fijar tamaño 8.5 pt (el libro usa 9.5)."""
    ruta = ES / f"pag-{pg:03d}.json"
    es = json.loads(ruta.read_text())
    cambiados = 0
    for bid in ids:
        v = es.get(bid)
        if isinstance(v, dict) and v.get("size", 99) > tam:
            v["size"] = tam; cambiados += 1
        elif isinstance(v, str) and v != "~":
            es[bid] = {"t": v, "size": tam}; cambiados += 1
    if cambiados:
        ruta.write_text(json.dumps(es, ensure_ascii=False, indent=1))
    return bool(cambiados)


def mapa_glosario():
    filas = [l.split("\t")[:2] for l in (P / "traduccion" / "glosario.tsv").read_text().splitlines()[1:] if "\t" in l]
    return {en.strip().lower(): re.sub(r"\s*\([^)]*\)", "", es).strip() for en, es in filas}


def sin_acentos(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if not unicodedata.combining(c))


def ids_overflow(linea):
    mo = re.search(r"overflow: \[([^\]]*)\]", linea)
    return re.findall(r"'(b\d+)'", mo.group(1)) if mo else []


def escalera_overflow(pg, ok, linea, modelo, glos):
    """Acortados locales (2 rondas) y luego tamaños 8.5→8.3→8.2 con acortado intermedio."""
    for ronda in (1, 2):
        ids = ids_overflow(linea)
        if ok or not ids:
            return ok, linea
        if not acorta_overflow(pg, ids, modelo, glos):
            break
        print(f"  ↻ acortado local de {ids} (ronda {ronda})")
        ok, linea = compose_qa(pg)
    for tam in (8.5, 8.3, 8.2):
        ids = ids_overflow(linea)
        if ok or not ids:
            break
        if tam != 8.5 and acorta_overflow(pg, ids, modelo, glos):
            print(f"  ↻ acortado extra {ids}")
            ok, linea = compose_qa(pg)
            ids = ids_overflow(linea)
            if ok or not ids:
                break
        if reduce_size(pg, ids, tam):
            print(f"  ↧ size {tam} en {ids}")
            ok, linea = compose_qa(pg)
    return ok, linea


def repara_glosario(pg, fallas, modelo, glos):
    """Re-traduce SOLO los bloques que contienen el término EN fallado, con requisito duro
    y verificación de que el término ES quedó en el texto. fallas: [(en, es, stem_qa)]."""
    dump = json.loads((EN / f"pag-{pg:03d}.json").read_text())
    ruta = ES / f"pag-{pg:03d}.json"
    es = json.loads(ruta.read_text())
    cambio = False
    for term_en, term_es, stem in fallas:
        for b in dump["blocks"]:
            if term_en.lower() not in b["text"].lower():
                continue
            v = es.get(b["id"])
            actual = v.get("t") if isinstance(v, dict) else v
            if not isinstance(actual, str) or actual == "~" or stem in sin_acentos(actual.lower()):
                continue
            msj = [{"role": "system", "content": REGLAS + "\n\nGLOSARIO (en = es):\n" + glos},
                   {"role": "user", "content": f"Re-traduce este bloque. OBLIGATORIO traducir «{term_en}» como «{term_es}» (ajusta género/número). Longitud similar al inglés, números idénticos.\n"
                    + json.dumps({b["id"]: b["text"]}, ensure_ascii=False)}]
            try:
                nuevo = str(json.loads(ollama(modelo, msj)).get(b["id"], "")).strip()
            except Exception:
                continue
            if not nuevo or stem not in sin_acentos(nuevo.lower()):
                continue
            if b["type"] == "cuerpo":
                nuevo = marca_runins(b["text"], nuevo)
            nuevo = re.sub(r"(\d)\.(\d{3})\b", r"\1,\2", nuevo)
            if isinstance(v, dict):
                v["t"] = nuevo
            else:
                es[b["id"]] = nuevo
            cambio = True
    if cambio:
        ruta.write_text(json.dumps(es, ensure_ascii=False, indent=1))
    return cambio


def ciclo_reparacion(pg, ok, linea, modelo, glos, mapa):
    """Escalera de overflow + reparación dirigida de glosario + segunda escalera."""
    ok, linea = escalera_overflow(pg, ok, linea, modelo, glos)
    if not ok and "glosario:" in linea:
        fallas = [(en, mapa.get(en.lower(), en), st)
                  for en, st in re.findall(r"glosario: «([^»]+)» sin «([^»]+)»", linea)]
        if fallas and repara_glosario(pg, fallas, modelo, glos):
            print(f"  ✚ glosario reparado: {[en for en, _, _ in fallas]}")
            ok, linea = compose_qa(pg)
            ok, linea = escalera_overflow(pg, ok, linea, modelo, glos)
    return ok, linea


def compose_qa(pg):
    py = sys.executable
    rc = subprocess.run([py, str(P / "scripts" / "30_compose.py"), str(pg)], capture_output=True, text=True)
    if rc.returncode != 0 or not (P / "render" / "paginas" / f"pag-{pg:03d}.pdf").exists():
        err = (rc.stderr or "").strip().splitlines()
        return False, f"p{pg} ✗ compose FALLÓ: {err[-1] if err else 'sin PDF'}"
    qa = subprocess.run([py, str(P / "scripts" / "40_qa_page.py"), str(pg)], capture_output=True, text=True)
    linea = next((l for l in qa.stdout.splitlines() if l.startswith(f"p{pg} ")), "(sin salida QA)")
    limpia = "✓" in linea
    if limpia:
        rows = list(csv.reader(open(P / "progress.csv")))
        for r in rows[1:]:
            if r and r[0].isdigit() and int(r[0]) == pg:
                r[2] = r[3] = r[4] = r[5] = "ok"
        csv.writer(open(P / "progress.csv", "w")).writerows(rows)
    return limpia, linea


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inicio", type=int); ap.add_argument("fin", type=int, nargs="?")
    ap.add_argument("-m", "--modelo", default=_proyecto.get("modelo", "qwen3.5:35b-a3b-coding-nvfp4"))
    ap.add_argument("--forzar", action="store_true", help="re-traducir aunque exista es/pag-NNN.json")
    ap.add_argument("--solo-traducir", action="store_true", help="no correr compose/QA")
    a = ap.parse_args()
    glos = glosario_txt()
    MAPA = mapa_glosario()
    clases = clases_catalogo()
    limpias, sucias = [], []
    for pg in range(a.inicio, (a.fin or a.inicio) + 1):
        destino = ES / f"pag-{pg:03d}.json"
        if clases.get(pg, "texto") != "texto":
            print(f"p{pg}: clase '{clases[pg]}' → F5, salto"); continue
        if not (EN / f"pag-{pg:03d}.json").exists():
            print(f"p{pg}: sin dump en-bloques (¿arte/mapa? correr 23_bloques.py) — salto"); continue
        if destino.exists() and not a.forzar:
            print(f"p{pg}: ya existe {destino.name} — salto (usa --forzar)"); continue
        print(f"p{pg}: traduciendo con {a.modelo}…")
        t0 = time.monotonic()
        try:
            es = traduce_pagina(pg, a.modelo, glos)
        except Exception as e:
            print(f"  ✗ p{pg} sin traducir ({type(e).__name__}) — sigo con la siguiente")
            sucias.append(pg)
            continue
        destino.write_text(json.dumps(es, ensure_ascii=False, indent=1))
        print(f"  traducida en {time.monotonic() - t0:.0f}s")
        if a.solo_traducir:
            continue
        ok, linea = compose_qa(pg)
        ok, linea = ciclo_reparacion(pg, ok, linea, a.modelo, glos, MAPA)
        (limpias if ok else sucias).append(pg)
        print(f"  {linea}")
    print(f"\nlimpias: {limpias or '—'}\ncon fallas (editar es/*.json y recomponer): {sucias or '—'}")
