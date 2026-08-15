#!/usr/bin/env python3
"""91_revisa.py — segundo pase: CORRECCIÓN DE ESTILO sobre el texto ya traducido.

La primera pasada traduce; esta corrige. El modelo local actúa de corrector, no de
traductor: compara con el original y arregla concordancia, clíticos, calcos del inglés,
registro inconsistente y frases que "suenan a traducción". Conserva números, marcado y
longitud aproximada.

Uso:
  venv/bin/python 91_revisa.py 1 22            # revisa el rango
  venv/bin/python 91_revisa.py 1 22 --solo-informe   # no escribe, solo reporta

Detectores deterministas incluidos (ver PATRONES): errores que el modelo repite y que
conviene cazar sin depender de su criterio.
"""
import argparse, importlib.util, json, re, sys
from pathlib import Path

SC = Path(__file__).resolve().parent
P = SC.parent
sys.path.insert(0, str(SC))
import _proyecto

_spec = importlib.util.spec_from_file_location("t", SC / "35_traduce_ollama.py")
_t = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_t)
MOD = _proyecto.get("modelo", "qwen3.5:35b-a3b-coding-nvfp4")
ES = P / "traduccion" / "es"
BLOQ = P / "traduccion" / "digital"

# (regex, descripción) — señales de traducción defectuosa, no correcciones automáticas
PATRONES = [
    (r"\w+ándote a (?:todos|ustedes)", "clítico mezclado (tú + todos): «salpicándote a todos»"),
    (r"\w+ándo(?:te|se) a (?:todos|ustedes)", "clítico mezclado"),
    (r"\bhace(?:r|n)? sentido\b", "calco: «hacer sentido» → «tener sentido»"),
    (r"\baplica(?:r|n)? para\b", "calco: «aplicar para» → «solicitar / servir para»"),
    (r"\beventualmente\b", "falso amigo: eventually → «con el tiempo/finalmente»"),
    (r"\bactualmente\b.{0,40}\b(?:no|sino)\b", "posible falso amigo: actually"),
    (r"\brealiza(?:r|n)? que\b", "falso amigo: realize → «darse cuenta»"),
    (r"\basumi(?:r|endo)\b", "posible falso amigo: assume → «suponer»"),
    (r"\bsoporta(?:r|n)?\b(?!.{0,20}peso)", "posible falso amigo: support → «admitir/permitir»"),
    (r"\ben orden de\b", "calco: «in order to» → «para»"),
    (r"\bser capaz de\b", "calco: «be able to» → «poder»"),
    (r"\btú puedes\b|\btú tienes\b", "pronombre redundante"),
    (r"\bde el\b", "contracción: «de el» → «del»"),
    (r"\ba el\b(?! \w+ó)", "contracción: «a el» → «al»"),
    (r"  +", "espacio doble"),
    (r"\bpuntos de vida\b", "término: en D&D es «puntos de golpe»"),
    (r"\bchequeo\b", "término: check → «prueba»"),
    (r"\btirada de salvado\b", "término: → «tirada de salvación»"),
    (r"\bdaño de golpeo\b", "término: → «daño contundente»"),
    (r"\bMaestro de la mazmorra\b", "nombre propio: «Dungeon Master» o «DM»"),
    (r"\bhechizos?\b", "verificar: spell → «conjuro» en SRD ES"),
    (r"[a-záéíóúñ]{2,}\.[A-ZÁÉÍÓÚÑ]", "falta espacio tras punto"),
    (r"\?[^»\s]|\![^»\s]", "puntuación pegada"),
    (r"\b(el|la|los|las) [A-Z][a-z]+ing\b", "palabra en inglés sin traducir"),
]

CORRECTOR = """Eres corrector de estilo profesional de {idioma}. Recibes pares
{{id: {{"origen": texto original, "traduccion": texto en español}}}}.

Devuelve SOLO un JSON {{id: texto corregido}} con la traducción MEJORADA. Corrige:
- Concordancia de género y número, y clíticos mal usados (p. ej. «salpicándote a todos»
  → «salpicando a todos»; «te ataca a ustedes» → «los ataca»).
- Registro: al Dungeon Master se le habla de TÚ; a los jugadores como grupo, de USTEDES.
  Nunca mezcles ambos en la misma frase.
- Calcos del inglés y frases que suenan a traducción literal: reescríbelas como las diría
  un hablante nativo, sin cambiar el significado ni la información.
- Falsos amigos (eventually, actually, realize, assume, support, library…).
- Puntuación española: «», ¿?, ¡!, comas y espacios correctos.

REGLAS DURAS: conserva EXACTAMENTE los números, dados y códigos; conserva el marcado
(**negrita**, *cursiva*, ‹sc›versalitas‹/sc›, ‹c:…›, ‹g›); mantén una longitud parecida
(±10 %); si una traducción ya está bien, devuélvela idéntica."""


def revisa_pagina(pg, solo_informe=False):
    fes = ES / f"pag-{pg:03d}.json"
    fbl = BLOQ / f"pag-{pg:03d}.json"
    if not fes.exists() or not fbl.exists():
        return [], 0
    es = json.loads(fes.read_text())
    origen = {b["id"]: b["texto"] for b in json.loads(fbl.read_text())["bloques"]}
    hallazgos = []
    for bid, txt in es.items():
        if not isinstance(txt, str):
            continue
        for rx, desc in PATRONES:
            for mo in re.finditer(rx, txt, re.I):
                ini = max(0, mo.start() - 35)
                hallazgos.append((pg, bid, desc, txt[ini:mo.end() + 35].replace("\n", " ")))
    if solo_informe:
        return hallazgos, 0
    # pase del corrector sobre los bloques con texto sustancial
    claves = [k for k, v in es.items() if isinstance(v, str) and len(v) > 40 and k in origen]
    cambios = 0
    idioma = _proyecto.get("idioma_destino", "español de México")
    for j in range(0, len(claves), 6):
        lote = {k: {"origen": origen[k], "traduccion": es[k]} for k in claves[j:j + 6]}
        for _ in range(2):
            msj = [{"role": "system", "content": CORRECTOR.format(idioma=idioma)},
                   {"role": "user", "content": json.dumps(lote, ensure_ascii=False)}]
            try:
                r = json.loads(_t.ollama(MOD, msj, timeout=1200))
            except Exception:
                continue
            aplicados = 0
            for k in lote:
                v = str(r.get(k, "")).strip()
                if not v or v == es[k]:
                    continue
                # guardias: números iguales, marcado intacto, longitud razonable
                if _t.numeros_de(v) != _t.numeros_de(es[k]):
                    continue
                if v.count("**") != es[k].count("**") or v.count("‹sc›") != es[k].count("‹sc›"):
                    continue
                if not (0.75 <= len(v) / max(1, len(es[k])) <= 1.3):
                    continue
                es[k] = v
                aplicados += 1
            cambios += aplicados
            break
    if cambios:
        fes.write_text(json.dumps(es, ensure_ascii=False, indent=1))
    return hallazgos, cambios


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ini", type=int)
    ap.add_argument("fin", type=int, nargs="?")
    ap.add_argument("--solo-informe", action="store_true")
    a = ap.parse_args()
    total_h, total_c = [], 0
    for pg in range(a.ini, (a.fin or a.ini) + 1):
        h, c = revisa_pagina(pg, a.solo_informe)
        total_h += h
        total_c += c
        if c or h:
            print(f"p{pg}: {c} bloques corregidos, {len(h)} señales")
    print(f"\nTOTAL: {total_c} correcciones aplicadas, {len(total_h)} señales detectadas")
    for pg, bid, desc, ctx in total_h[:40]:
        print(f"  p{pg} {bid} — {desc}\n      …{ctx}…")
