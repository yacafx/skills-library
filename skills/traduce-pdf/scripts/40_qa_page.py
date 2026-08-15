#!/usr/bin/env python3
"""40_qa_page.py — V4: validación automática por página compuesta.
(a) inglés residual  (b) paridad numérica EN↔ES (multiconjunto de cifras y dados)
(d) glosario aplicado  (e) overflow (del fit report)  (f) signos españoles
Salida: qa/v4/pag-NNN.json + resumen en consola.  Uso: 40_qa_page.py 20 35 ...
"""
import json, os, re, sys, csv
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN_STOP = set("""the and with that this from have has been are were will would could should
their there where which while when they them then than because during against between
through about after before under over other another only also each much many more most
some such very your you into out upon these those does doesn't don't can't isn't within""".split())
import _proyecto
BLANCA = _proyecto.nombres_propios() | set("ok pdf npc dm gm".split())

# glosario: pares EN→ES de una sola pieza, aplicables por búsqueda
GLO = []
for row in csv.DictReader(open(f"{BASE}/traduccion/glosario.tsv"), delimiter="\t"):
    en, es = row["en"], row["es"]
    if "/" in en or "(" in en or len(en) < 5 or "/" in es:
        continue
    es2 = es.split("(")[0].strip()
    es2 = re.sub(r"^(el|la|los|las)\s+", "", es2, flags=re.I).lower()
    ult = es2.split()[-1]
    ult = ult[:-1] if len(ult) > 6 and ult[-1] in "aeoáéís" else ult
    raiz = (" ".join(es2.split()[:-1]) + " " + ult).strip() if len(es2.split()) == 1 else ult
    if en.lower() in ("challenge", "senses", "speed", "scrying"):
        continue
    GLO.append((en.lower(), raiz))

def textos_pagina(pg):
    eb = json.load(open(f"{BASE}/traduccion/en-bloques/pag-{pg:03d}.json"))
    es = json.load(open(f"{BASE}/traduccion/es/pag-{pg:03d}.json"))
    en_txt, es_txt = [], []
    ids_traducidos = set()
    for bid, val in es.items():
        if bid.startswith("__"): continue
        ids_traducidos.add(bid)
        if val is None or val == "~": continue
        es_txt.append(val["t"] if isinstance(val, dict) else val)
    for sb in es.get("__statblocks__", []):
        es_txt.append(sb["titulo"]); es_txt.append(sb.get("sub") or "")
        for sec in sb["secciones"]:
            if "tabla" in sec:
                es_txt.extend(f"{a} {v}" for a, v in sec["tabla"])
            else:
                es_txt.append((sec.get("h") or "") + " " + sec["t"])
    # EN: bloques traducidos + los absorbidos por statblocks (stat/stat_h y cuerpo dentro del panel)
    paneles = []
    if es.get("__statblocks__"):
        core = [b for b in eb["blocks"] if b["type"] in ("stat", "stat_h")]
        if core:
            paneles.append((min(b["bbox"][0] for b in core)-30, min(b["bbox"][1] for b in core)-30,
                            max(b["bbox"][2] for b in core)+30, max(b["bbox"][3] for b in core)+30))
    def en_panel(b):
        cx=(b["bbox"][0]+b["bbox"][2])/2; cy=(b["bbox"][1]+b["bbox"][3])/2
        return any(x0<=cx<=x1 and y0<=cy<=y1 for x0,y0,x1,y1 in paneles)
    extendidos = set()
    for v in es.values():
        if isinstance(v, dict) and isinstance(v.get("extiende"), list):
            extendidos.update(v["extiende"])
    for b in eb["blocks"]:
        val = es.get(b["id"], "__ausente__")
        if val not in (None, "~", "__ausente__"):
            en_txt.append(b["text"])
        elif val == "__ausente__" and (en_panel(b) or b["id"] in extendidos):
            en_txt.append(b["text"])
    return " ".join(en_txt), " ".join(es_txt)

DADO = re.compile(r"\d+d\d+")
NUM = re.compile(r"\d[\d,]*")

def numeros(t):
    t = re.sub(r"[’']", "", t)
    t = re.sub(r"\b[lI](d\d)", r"1\1", t)  # OCR: ld4/Id4 -> 1d4
    t = re.sub(r"\bd(\d+)\b", r"1d\1", t)  # "a d4" == "1d4"
    c = Counter(DADO.findall(t))
    t2 = DADO.sub(" ", t)
    c.update(NUM.findall(t2.replace(",", "")))
    return c

def v4(pg):
    en, es = textos_pagina(pg)
    rep = {"pg": pg, "fallas": []}
    # (a) EN residual
    ovr0 = {}
    op0 = f"{BASE}/qa/v4-overrides.json"
    if os.path.exists(op0):
        ovr0 = json.load(open(op0)).get(str(pg), {})
    toks = re.findall(r"[a-zA-Z']{3,}", es.lower())
    resid = [w for w in toks if w in EN_STOP and w not in BLANCA]
    if len(resid) > 1 and not ovr0.get("residual_ok"):
        rep["fallas"].append(f"EN-residual: {Counter(resid).most_common(4)}")
    # (b) paridad numérica
    ovr = {}
    op = f"{BASE}/qa/v4-overrides.json"
    if os.path.exists(op):
        ovr = json.load(open(op)).get(str(pg), {})
    ne, ns = numeros(en), numeros(es)
    solo_en = ne - ns; solo_es = ns - ne
    if ovr.get("numeros_ok"):
        solo_en = solo_es = {}
    if solo_en or solo_es:
        rep["fallas"].append(f"números: solo-EN {dict(solo_en)} | solo-ES {dict(solo_es)}")
    # (d) glosario
    import unicodedata
    def noacc(x): return "".join(c for c in unicodedata.normalize("NFD", x) if unicodedata.category(c) != "Mn")
    en_low, es_low = en.lower(), noacc(es.lower())
    skip_glo = set(ovr.get("glosario_skip", []))
    for g_en, g_es in GLO:
        if g_en in skip_glo:
            continue
        if re.search(r"\b"+re.escape(g_en)+r"\b", en_low) and noacc(g_es) not in es_low:
            rep["fallas"].append(f"glosario: «{g_en}» sin «{g_es}»")
    # (e) overflow
    fitp = f"{BASE}/qa/fit/pag-{pg:03d}.json"
    if os.path.exists(fitp):
        mal = [f["id"] for f in json.load(open(fitp)) if not f["cabe"] and f["id"] != "__sb__"]
        if mal:
            rep["fallas"].append(f"overflow: {mal}")
    # (f) signos
    if es.count("?") > es.count("¿") + 1:
        rep["fallas"].append(f"¿ faltantes: {es.count('?')}? vs {es.count('¿')}¿")
    if re.search(r"[ÃÂ�]", es):
        rep["fallas"].append("mojibake detectado")
    os.makedirs(f"{BASE}/qa/v4", exist_ok=True)
    json.dump(rep, open(f"{BASE}/qa/v4/pag-{pg:03d}.json", "w"), ensure_ascii=False, indent=1)
    estado = "✓" if not rep["fallas"] else "✗"
    print(f"p{pg} {estado} " + ("; ".join(rep["fallas"])[:180] if rep["fallas"] else ""))
    return not rep["fallas"]

if __name__ == "__main__":
    ok = sum(v4(int(a)) for a in sys.argv[1:])
    print(f"V4: {ok}/{len(sys.argv)-1} páginas limpias")
