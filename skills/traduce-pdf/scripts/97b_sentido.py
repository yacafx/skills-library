#!/usr/bin/env python3
"""97b_sentido.py — sospechas de ERROR DE SENTIDO para adjudicar a mano.

Los detectores de 98_consistencia.py ven la forma (números, marcado, longitud); este
ve indicios de significado equivocado. NO decide: marca candidatos que un humano (o
Claude) confirma contra el original. Está calibrado para pocos falsos positivos.

  FALSO-AMIGO  el ES usa el calco típico de una palabra inglesa presente en el EN
  NEGACION     el EN niega («unless», «can't», «no longer») y el ES perdió la negación
  CONDICION    el EN nombra una condición/umbral y el ES nombra otro distinto
  FRECUENCIA   «once per rest/scene/session» cambiado de periodo en el ES
  RECURSO      Hope↔Fear o marcar↔gastar intercambiados respecto al EN
"""
import json, re, sys, unicodedata
from pathlib import Path

P = Path(__file__).resolve().parent.parent
_pj = json.loads((Path(__file__).resolve().parent.parent / "proyecto.json").read_text())     if (Path(__file__).resolve().parent.parent / "proyecto.json").exists() else {}

EN_DIR, ES_DIR = P / "traduccion" / "digital", P / "traduccion" / "es"
SALIDA = P / "qa" / "sentido.tsv"

# palabra_en -> (calco sospechoso, traducción correcta)
FALSOS = {
    "vicious": ("vicioso", "feroz/brutal"),
    "actually": ("actualmente", "en realidad"),
    "eventually": ("eventualmente", "con el tiempo/al final"),
    "casualty": ("casualidad", "baja/víctima"),
    "sensible": ("sensible", "sensato"),
    "attempt": ("atentar", "intentar"),
    "success": ("suceso", "éxito"),
    "library": ("librería", "biblioteca"),
    "realize": ("realizar", "darse cuenta"),
    "realizes": ("realiza", "se da cuenta"),
    "ultimate": ("último", "definitivo/supremo"),
    "assist": ("asistir", "ayudar"),
    "argument": ("argumento", "discusión"),
    "large": ("largo", "grande"),
    "actual": ("actual", "real/verdadero"),
    "eventual": ("eventual", "final"),
    "pretend": ("pretender", "fingir"),
    "support": ("soportar", "apoyar"),
    "resume": ("resumir", "reanudar"),
    "advertisement": ("advertencia", "anuncio"),
    "topic": ("tópico", "tema"),
    "quiet": ("quieto", "silencioso"),
}
NEG_EN = re.compile(r"\b(unless|can(?:no|')t|cannot|never|no longer|without|neither|nor|"
                    r"doesn't|don't|won't|isn't|aren't)\b", re.I)
NEG_ES = re.compile(r"\b(a menos que|no|nunca|jamás|sin|ni|salvo que|deja de|dejan de|"
                    r"ya no|tampoco|excepto)\b", re.I)
COND = {"restrained": "inmoviliz", "vulnerable": "vulnerable", "hidden": "ocult",
        "cloaked": "encubiert", "unstoppable": "imparable"}
FREQ = {r"once per (long )?rest": "descanso", r"once per scene": "escena",
        r"once per session": "sesión", r"once per turn": "turno"}
FREQ_ES = {"descanso": r"descanso", "escena": r"escena", "sesión": r"sesi[óo]n",
           "turno": r"turno"}


def norm(t):
    t = re.sub(r"‹[^›]*›", "", str(t)).replace("*", "")
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def main():
    fallos = []
    for fen in sorted(EN_DIR.glob("pag-*.json")):
        pg = int(fen.stem.split("-")[1])
        fes = ES_DIR / fen.name
        if not fes.exists():
            continue
        datos = json.loads(fen.read_text())
        es = json.loads(fes.read_text())
        bloques = list(datos["bloques"]) + [
            {"id": f["id"], "texto": f["texto"]} for f in datos.get("tabla_frases", [])]
        for b in bloques:
            v = es.get(b["id"])
            if isinstance(v, dict):
                v = v.get("t", "")
            if not isinstance(v, str) or not v.strip() or v == "~":
                continue
            en, esn = norm(b["texto"]), norm(v)

            for w, (calco, bien) in FALSOS.items():
                if re.search(rf"\b{w}\b", en) and re.search(rf"\b{calco}\w*\b", esn):
                    fallos.append((pg, b["id"], "FALSO-AMIGO",
                                   f"{w} → «{calco}» (¿{bien}?): {v[:70]}"))

            if NEG_EN.search(b["texto"]) and not NEG_ES.search(v) and len(esn) > 30:
                fallos.append((pg, b["id"], "NEGACION",
                               f"EN niega, ES no: {b['texto'][:55]} → {v[:55]}"))

            for cen, ces in COND.items():
                if re.search(rf"\b{cen}\b", en) and ces not in esn:
                    otras = [c for k, c in COND.items() if k != cen and c in esn]
                    if otras:
                        fallos.append((pg, b["id"], "CONDICION",
                                       f"EN «{cen}» pero ES usa «{otras[0]}…»: {v[:60]}"))

            for pat, periodo in FREQ.items():
                if re.search(pat, en):
                    if not re.search(FREQ_ES[periodo], esn):
                        fallos.append((pg, b["id"], "FRECUENCIA",
                                       f"EN «{periodo}» ausente en ES: {v[:60]}"))

            # pares de recursos del juego (EN_a, EN_b, ES_a, ES_b); configurable
            pares = _pj.get("recursos_pares") or [["hope", "fear", "esperanza", "miedo"]]
            for a, bb, ea, eb in pares:
                nea, neb = len(re.findall(a, en)), len(re.findall(bb, en))
                nsa, nsb = len(re.findall(ea, esn)), len(re.findall(eb, esn))
                if (nea or neb) and (nea, neb) != (nsa, nsb) and abs(nea - nsa) + abs(neb - nsb) >= 2:
                    fallos.append((pg, b["id"], "RECURSO",
                                   f"EN hope/fear={nea}/{neb} vs ES={nsa}/{nsb}: {v[:60]}"))

    fallos.sort(key=lambda f: (f[0], f[1]))
    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text("\n".join("\t".join(map(str, f)) for f in fallos) + "\n")
    tipos = {}
    for _, _, t, _d in fallos:
        tipos[t] = tipos.get(t, 0) + 1
    print(f"{len(fallos)} sospechas → {SALIDA}")
    for t, n in sorted(tipos.items(), key=lambda x: -x[1]):
        print(f"  {t}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
