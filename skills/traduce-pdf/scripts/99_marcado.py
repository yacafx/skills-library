#!/usr/bin/env python3
"""99_marcado.py — repara el marcado desbalanceado del ES contra el EN.

El original usa run-in PARTIDO: «***Nombre:* Gasta 3 Hope**» = el nombre en
negrita-cursiva y el resto del arranque solo en negrita. El modelo local rompe ese
patrón de tres maneras (cierra de más «:***», de menos «:*», o a medias «:**») y
deja un «**» huérfano que se imprime LITERAL en la página.

Dos fases:
  1. ALINEAR: el marcador que cierra el run-in en ES se copia del EN (el modelo no
     decide el marcado; lo dicta el original).
  2. BALANCEAR: parser de estado negrita/cursiva; lo que quede abierto se cierra al
     final del bloque. Red de seguridad para el resto de casos.

Idempotente: reprocesar un bloque ya reparado no lo cambia. Nunca toca el texto,
solo los asteriscos.
"""
import json, re, sys
from pathlib import Path

P = Path(__file__).resolve().parent.parent
EN_DIR, ES_DIR = P / "traduccion" / "digital", P / "traduccion" / "es"

RUNIN = re.compile(r"^(\*{1,3})([^*]{2,60}?[.:])(\*{1,3})")
MARCA = re.compile(r"\*{1,3}")


def balanceado(t):
    """True si el marcado abre y cierra correctamente (negrita y cursiva)."""
    b = i = False
    for m in MARCA.finditer(t):
        n = len(m.group(0))
        if n == 3:
            b, i = not b, not i
        elif n == 2:
            b = not b
        else:
            i = not i
    return not b and not i


def alinea_runin(en, es):
    """El cierre del run-in lo dicta el EN, no el modelo."""
    men, mes = RUNIN.match(en), RUNIN.match(es)
    if not men or not mes:
        return es
    if men.group(1) != mes.group(1) or men.group(3) != mes.group(3):
        return men.group(1) + mes.group(2) + men.group(3) + es[mes.end():]
    return es


def balancea(t):
    """Cierra al final lo que quedó abierto. No inventa marcado nuevo."""
    b = i = False
    for m in MARCA.finditer(t):
        n = len(m.group(0))
        if n == 3:
            b, i = not b, not i
        elif n == 2:
            b = not b
        else:
            i = not i
    cola = ""
    if b and i:
        cola = "***"
    elif b:
        cola = "**"
    elif i:
        cola = "*"
    if not cola:
        return t
    t = t.rstrip()
    # el cierre va PEGADO a la última palabra, no tras el punto final suelto
    return t + cola


def main():
    total, tocadas = 0, set()
    for fen in sorted(EN_DIR.glob("pag-*.json")):
        pg = int(fen.stem.split("-")[1])
        fes = ES_DIR / fen.name
        if not fes.exists():
            continue
        datos = json.loads(fen.read_text())
        es = json.loads(fes.read_text())
        en_por_id = {b["id"]: b["texto"] for b in datos["bloques"]}
        en_por_id.update({f["id"]: f["texto"] for f in datos.get("tabla_frases", [])})
        cambio = False
        for bid, v in list(es.items()):
            if not isinstance(v, str) or not v.strip() or v == "~":
                continue
            if balanceado(v):
                continue
            nuevo = balancea(alinea_runin(en_por_id.get(bid, ""), v))
            if nuevo != v and balanceado(nuevo):
                es[bid] = nuevo
                cambio = True
                total += 1
                tocadas.add(pg)
                print(f"p{pg} {bid}: {v[:52]!r} → {nuevo[:52]!r}")
            elif nuevo == v or not balanceado(nuevo):
                print(f"p{pg} {bid}: ⚠ NO reparable automáticamente: {v[:60]!r}")
        if cambio:
            fes.write_text(json.dumps(es, ensure_ascii=False, indent=1))
    print(f"\n{total} bloques reparados en {len(tocadas)} páginas")
    print("PAGINAS:" + ",".join(str(p) for p in sorted(tocadas)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
