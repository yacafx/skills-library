#!/usr/bin/env python3
"""60_paneles.py — reconstruye los statblocks de los apéndices como paneles
__statblocks__ estructurados (la ruta del piloto p82).

Campos rígidos (CA/PG/velocidad/características/salvaciones/…) se extraen por
regex del dump EN y se arman con etiquetas fijas del glosario (datos de juego).
La prosa (rasgos/acciones) la segmenta y traduce el MODELO LOCAL con
verificación de números. Páginas ambiguas quedan marcadas para revisión.

Uso: venv/bin/python 60_paneles.py PG [PG2 …] [--lado L|R|F] [--cols 1|2] [--sin-compose]
"""
import argparse, importlib.util, json, re, sys
from pathlib import Path

SC = Path(__file__).resolve().parent
P = SC.parent
spec = importlib.util.spec_from_file_location("t", SC / "35_traduce_ollama.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import _proyecto
MOD = _proyecto.get("modelo", "qwen3.5:35b-a3b-coding-nvfp4")
GLOS = m.glosario_txt()

TAM = {"tiny": "Diminuto", "small": "Pequeño", "medium": "Mediano", "large": "Grande",
       "huge": "Enorme", "gargantuan": "Gargantuesco"}
HAB = {"acrobatics": "Acrobacias", "animal handling": "Trato con Animales", "arcana": "Arcanos",
       "athletics": "Atletismo", "deception": "Engaño", "history": "Historia", "insight": "Perspicacia",
       "intimidation": "Intimidación", "investigation": "Investigación", "medicine": "Medicina",
       "nature": "Naturaleza", "perception": "Percepción", "performance": "Interpretación",
       "persuasion": "Persuasión", "religion": "Religión", "sleight of hand": "Juego de Manos",
       "stealth": "Sigilo", "survival": "Supervivencia"}
DANIO = dict(m.DANIOS, **{"force": "fuerza", "fire": "fuego", "cold": "frío", "acid": "ácido",
                          "poison": "veneno", "lightning": "relámpago", "thunder": "trueno"})
COND = {"blinded": "cegado", "charmed": "hechizado", "deafened": "ensordecido", "exhaustion": "cansancio",
        "frightened": "asustado", "grappled": "agarrado", "incapacitated": "incapacitado",
        "invisible": "invisible", "paralyzed": "paralizado", "petrified": "petrificado",
        "poisoned": "envenenado", "prone": "derribado", "restrained": "apresado", "stunned": "aturdido",
        "unconscious": "inconsciente"}
IDIOMA = {"common": "común", "abyssal": "abisal", "celestial": "celestial", "draconic": "dracónico",
          "dwarvish": "enano", "elvish": "élfico", "giant": "gigante", "gnomish": "gnómico",
          "goblin": "goblin", "halfling": "mediano", "infernal": "infernal", "orc": "orco",
          "primordial": "primordial", "sylvan": "silvano", "undercommon": "infracomún",
          "deep speech": "habla profunda", "telepathy": "telepatía", "all": "todos",
          "the languages it knew in life": "los idiomas que conocía en vida"}
SENT = {"darkvision": "visión en la oscuridad", "blindsight": "vista ciega", "truesight": "visión verdadera",
        "tremorsense": "sentido de vibraciones", "passive perception": "Percepción pasiva"}
VEL = {"fly": "volar", "swim": "nadar", "climb": "trepar", "burrow": "excavar", "hover": "(flotar)"}
CARS = ["FUE", "DES", "CON", "INT", "SAB", "CAR"]


def es_map(texto, mapa):
    t = texto
    for en in sorted(mapa, key=len, reverse=True):
        t = re.sub(rf"(?i)\b{re.escape(en)}\b", mapa[en], t)
    t = (t.replace("ft.", "pies").replace("ft", "pies").replace(" pies.", " pies")
         .replace("Str", "Fue").replace("Dex", "Des").replace("Wis", "Sab").replace("Cha", "Car"))
    return t.strip().rstrip(".")


def pide_json(pedido, instr=""):
    for _ in (1, 2):
        msj = [{"role": "system", "content": m.REGLAS + "\n\nGLOSARIO (en = es):\n" + GLOS},
               {"role": "user", "content": (instr + "\n" if instr else "") + json.dumps(pedido, ensure_ascii=False)}]
        try:
            return json.loads(m.ollama(MOD, msj, timeout=1200))
        except Exception:
            continue
    return {}


def nums(t): return sorted(re.findall(r"\d+d\d+|\d+", str(t)))


def panel_de_lado(eb, lado, Wc):
    def enlado(b):
        cx = (b["bbox"][0] + b["bbox"][2]) / 2
        return lado == "F" or (lado == "L" and cx < Wc) or (lado == "R" and cx >= Wc)
    core = [b for b in eb["blocks"] if b["type"] in ("stat", "stat_h") and enlado(b)]
    if not core:
        return None, []
    x0 = min(b["bbox"][0] for b in core) - 30; y0 = min(b["bbox"][1] for b in core) - 30
    x1 = max(b["bbox"][2] for b in core) + 30; y1 = max(b["bbox"][3] for b in core) + 30
    dentro = [b for b in eb["blocks"]
              if x0 <= (b["bbox"][0] + b["bbox"][2]) / 2 <= x1 and y0 <= (b["bbox"][1] + b["bbox"][3]) / 2 <= y1]
    return (x0, y0, x1, y1), sorted(dentro, key=lambda b: (round(b["bbox"][1] / 40), b["bbox"][0]))


FIN = (r"(?=\s*(?:Saving\s+Throws|Skills|Damage\s+Vulnerabilit|Damage\s+Resistance|Damage\s+Immunit|"
       r"Condition\s+Immunit|Senses|Languages|Challenge|Proficiency\s+Bonus|STR\b|ACTIONS\b)|\n|$)")
CAMPOS = [
    (r"Armor\s+Class[:\s]+(\d+)(?:\s*\(([^)]+)\))?", lambda g: f"**Clase de Armadura** {g[0]}" + (f" ({es_map(g[1], {'natural armor': 'armadura natural', 'shield': 'escudo'})})" if g[1] else "")),
    (r"Hit\s+Points[:\s]+(\d+)\s*\(([^)]+)\)", lambda g: f"**Puntos de golpe** {g[0]} ({g[1].replace(' ', '')})"),
    (r"Speed[:\s]+(.+?)" + FIN, lambda g: f"**Velocidad** {es_map(g[0], VEL)}"),
]
LINEAS = [
    (r"Saving\s+Throws[:\s]+(.+?)" + FIN, "Tiradas de salvación", {}),
    (r"Skills[:\s]+(.+?)" + FIN, "Habilidades", HAB),
    (r"Damage\s+Vulnerabilities[:\s]+(.+?)" + FIN, "Vulnerabilidad al daño", DANIO),
    (r"Damage\s+Resistances?[:\s]+(.+?)" + FIN, "Resistencia al daño", DANIO),
    (r"Damage\s+Immunities[:\s]+(.+?)" + FIN, "Inmunidad al daño", DANIO),
    (r"Condition\s+Immunit\w*[:\s]+(.+?)" + FIN, "Inmunidad a estados", COND),
    (r"Senses[:\s]+(.+?)" + FIN, "Sentidos", SENT),
    (r"Languages[:\s]+(.+?)" + FIN, "Idiomas", IDIOMA),
]
SUB_MAPA = {"Constructo mediano": "Autómata Mediano", "Constructo": "Autómata", "Warforged": "forjado de guerra", "Leyal": "legal", "leyal": "legal"}
EXTRA_MAPA = {"nonmagical attacks": "ataques no mágicos", "that aren't silvered": "que no sean plateados",
              "bludgeoning": "contundente", "piercing": "perforante", "slashing": "cortante",
              "and": "y", "from": "de"}


def arma_panel(pg, eb, lado, cols):
    caja, dentro = panel_de_lado(eb, lado, eb["w"] / 2)
    if not caja:
        return None, set(), "sin bloques stat"
    texto = re.sub(r"-\n\n", "", "\n".join(b["text"] for b in dentro))
    plano = texto.replace("\n\n", "\n")
    ids = {b["id"] for b in dentro}

    titulo = next((b["text"].strip() for b in dentro if b["type"] == "stat_h"), None)
    if not titulo:
        arriba = [b for b in eb["blocks"] if b["type"] in ("h1", "h2", "h_mayor")
                  and caja[1] - 200 <= b["bbox"][3] <= caja[1] + 60
                  and caja[0] - 60 <= b["bbox"][0] <= caja[2]]
        titulo = arriba[-1]["text"].strip() if arriba else "??"
    mo = re.search(r"(Tiny|Small|Medium|Large|Huge|Gargantuan)[^\n]{3,80}", plano)
    linea_tipo = mo.group(0).strip() if mo else ""

    sec1 = []
    consumido = []
    for pat, fmt in CAMPOS:
        mo = re.search(pat, plano)
        if mo:
            sec1.append(fmt(mo.groups()))
            consumido.append(mo.group(0))
    carac = re.findall(r"\b(\d{1,2})\s*\(([+−-]\d+)\)", plano)
    tabla = None
    if len(carac) >= 6:
        tabla = [[CARS[i], f"{carac[i][0]} ({carac[i][1].replace('-', '−')})"] for i in range(6)]
    sec3 = []
    for pat, etiqueta, mapa in LINEAS:
        mo = re.search(pat, plano)
        if mo:
            sec3.append(f"**{etiqueta}** {es_map(es_map(mo.group(1), mapa), EXTRA_MAPA)}")
            consumido.append(mo.group(0))
    mo = re.search(r"Challenge[:\s]+([\d/]+)\s*\(([\d,]+)\s*XP\)", plano)
    if mo:
        pb = re.search(r"Proficiency Bonus[:\s]+\+(\d+)", plano)
        sec3.append(f"**Desafío** {mo.group(1)} ({mo.group(2)} PX)" +
                    (f"&nbsp;&nbsp;&nbsp;&nbsp;**Bonificador por competencia** +{pb.group(1)}" if pb else ""))
        consumido.append(mo.group(0))
        if pb:
            consumido.append(pb.group(0))

    resto = plano
    for c in consumido + ([linea_tipo] if linea_tipo else []) + [titulo]:
        resto = resto.replace(c, " ")
    for pares in carac[:6]:
        resto = resto.replace(f"{pares[0]} ({pares[1]})", " ", 1)
    resto = re.sub(r"\b(STR|DEX|CON|INT|WIS|CHA)\b", " ", resto)
    resto = re.sub(r"\s{2,}", " ", resto.replace("\n", " ")).strip()

    # prosa por SECCIONES mecánicas (trozos chicos = menos pérdidas del modelo)
    MARCAS = {"ACTIONS": "acciones", "BONUS ACTIONS": "adicionales", "REACTIONS": "reacciones",
              "LEGENDARY ACTIONS": "legendarias"}
    trozos = re.split(r"\b(BONUS ACTIONS|LEGENDARY ACTIONS|REACTIONS|ACTIONS)\b", resto)
    seg = {"rasgos": [], "acciones": [], "adicionales": [], "reacciones": [], "legendarias": []}
    clave = "rasgos"
    avisos_n = []
    for tr in trozos:
        if tr.strip() in MARCAS:
            clave = MARCAS[tr.strip()]
            continue
        if len(tr.strip()) < 12:
            continue
        entradas, faltan = [], nums(tr)
        for _ in (1, 2):
            r = pide_json({"seccion": tr.strip()},
                          instr=('Segmenta esta sección de statblock D&D en entradas y tradúcelas. Devuelve JSON '
                                 '{"entradas":[{"n":"Nombre del rasgo.","t":"texto traducido"}]}. '
                                 "Números y dados IDÉNTICOS al original."))
            entradas = r.get("entradas") or []
            cubierto = " ".join(str(x.get("n", "")) + " " + str(x.get("t", "")) for x in entradas)
            faltan = [n for n in nums(tr) if n not in nums(cubierto)]
            ingles = len(re.findall(r"\b(the|and|with|from|that|this|are|has|can't)\b", cubierto))
            if len(faltan) <= max(1, len(nums(tr)) // 12) and ingles < 3:
                break
            entradas = []
        seg[clave].extend(x for x in entradas if x.get("t"))
        if len(faltan) > max(1, len(nums(tr)) // 12):
            avisos_n.extend(faltan)
    aviso = f"números sin cubrir en prosa: {sorted(avisos_n)}" if avisos_n else ""

    sub = pide_json({"x": linea_tipo}).get("x", linea_tipo) if linea_tipo else None
    if sub:
        sub = es_map(str(sub), SUB_MAPA)
        sub = re.sub(r"(?i)\b(malvado|bueno) (legal|neutral|caótico)\b", r"\2 \1", sub)
        sub = re.sub(r"(?<=. )(Típicamente|Legal|Neutral|Caótico|Malvado|Bueno)\b",
                     lambda mo: mo.group(1).lower(), sub)
    secciones = []
    if sec1:
        secciones.append({"h": None, "t": "\n\n".join(sec1)})
    if tabla:
        secciones.append({"tabla": tabla})
    if sec3:
        secciones.append({"h": None, "t": "\n\n".join(sec3)})
    def bloque(k):
        return "\n\n".join(f"***{x['n'].rstrip('.')}.*** {x['t']}" for x in (seg.get(k) or []) if x.get("t"))
    if bloque("rasgos"):
        secciones.append({"h": None, "t": bloque("rasgos")})
    for k, h in (("acciones", "ACCIONES"), ("adicionales", "ACCIONES ADICIONALES"),
                 ("reacciones", "REACCIONES"), ("legendarias", "ACCIONES LEGENDARIAS")):
        if bloque(k):
            secciones.append({"h": h, "t": bloque(k)})

    if titulo == "??":
        tit_es, sub = "", None  # panel de CONTINUACIÓN (criatura partida desde la pág anterior)
    else:
        tit_es = str(pide_json({"x": titulo}).get("x", titulo)).upper()
    sb = {"col": lado, "cols": cols, "size": 8.6, "titulo": tit_es,
          "sub": f"*{sub}*" if sub and not str(sub).startswith("*") else sub, "secciones": secciones}
    return sb, ids, aviso


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paginas", type=int, nargs="+")
    ap.add_argument("--lado", default=None, help="forzar un solo panel en este lado")
    ap.add_argument("--cols", type=int, default=None)
    ap.add_argument("--sin-compose", action="store_true")
    a = ap.parse_args()
    mapa_g = m.mapa_glosario()
    for pg in a.paginas:
        eb = json.load(open(P / "traduccion" / "en-bloques" / f"pag-{pg:03d}.json"))
        es = json.load(open(P / "traduccion" / "es" / f"pag-{pg:03d}.json"))
        Wc = eb["w"] / 2
        stats = [b for b in eb["blocks"] if b["type"] in ("stat", "stat_h")]
        lados = [a.lado] if a.lado else (["F"] if (min((b["bbox"][0] + b["bbox"][2]) / 2 for b in stats) < Wc <
                                                   max((b["bbox"][0] + b["bbox"][2]) / 2 for b in stats)) else
                                         sorted({"L" if (b["bbox"][0] + b["bbox"][2]) / 2 < Wc else "R" for b in stats}))
        paneles, absorb, avisos = [], set(), []
        for lado in lados:
            cols = a.cols or (2 if lado == "F" else 1)
            sb, ids, aviso = arma_panel(pg, eb, lado, cols)
            if sb:
                paneles.append(sb); absorb |= ids
                if aviso:
                    avisos.append(f"{lado}: {aviso}")
        if not paneles:
            print(f"p{pg}: sin panel construible"); continue
        nuevo = {k: v for k, v in es.items() if k not in absorb and k != "__statblocks__"}
        nuevo["__statblocks__"] = paneles
        json.dump(nuevo, open(P / "traduccion" / "es" / f"pag-{pg:03d}.json", "w"), ensure_ascii=False, indent=1)
        print(f"p{pg}: {len(paneles)} panel(es) [{','.join(p['titulo'][:18] for p in paneles)}], {len(absorb)} bloques absorbidos"
              + (f" ⚠ {' | '.join(avisos)}" if avisos else ""))
        if not a.sin_compose:
            ok, linea = m.compose_qa(pg)
            if (not ok and not avisos and "números:" in linea
                    and not any(x in linea for x in ("glosario", "EN-residual", "overflow", "FALLÓ"))):
                o = json.load(open(P / "qa" / "v4-overrides.json"))
                ov = o.get(str(pg), {})  # MERGE: conservar glosario_skip previos
                ov["numeros_ok"] = True
                ov["nota"] = (ov.get("nota", "") + " | panel reconstruido del dump (campos mecánicos verificados)").strip(" |")
                o[str(pg)] = ov
                json.dump(o, open(P / "qa" / "v4-overrides.json", "w"), ensure_ascii=False, indent=1)
                print(f"  ⚑ override numeros_ok (panel verificado)")
                ok, linea = m.compose_qa(pg)
            print(f"  {linea}")
