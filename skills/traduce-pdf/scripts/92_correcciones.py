#!/usr/bin/env python3
"""92_correcciones.py — aplica `traduccion/correcciones.tsv` a la traducción.

Las correcciones editoriales (terminología, registro, calcos, régimen preposicional…)
NO se aplican a mano: viven en un TSV versionado y se re-aplican después de CADA
traducción. Así una re-traducción nunca pierde el trabajo de revisión.

Formato del TSV (tabulaciones):  patrón_regex \t reemplazo \t motivo
Las líneas que empiezan por # son comentarios.

Uso:
  venv/bin/python 92_correcciones.py           # aplica a todas las páginas
  venv/bin/python 92_correcciones.py --listar  # solo muestra qué cambiaría
"""
import argparse, json, re, sys
from pathlib import Path

SC = Path(__file__).resolve().parent
P = SC.parent
sys.path.insert(0, str(SC))

TSV = P / "traduccion" / "correcciones.tsv"
ES = P / "traduccion" / "es"


def reglas():
    if not TSV.exists():
        return []
    out = []
    for i, linea in enumerate(TSV.read_text().splitlines()):
        if not linea.strip() or linea.startswith("#") or linea.startswith("patrón"):
            continue
        partes = linea.split("\t")
        if len(partes) < 2:
            continue
        try:
            out.append((re.compile(partes[0]), partes[1], partes[2] if len(partes) > 2 else ""))
        except re.error as e:
            print(f"  ⚠ regla {i+1} inválida ({e}): {partes[0][:40]}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--listar", action="store_true")
    a = ap.parse_args()
    rs = reglas()
    print(f"{len(rs)} reglas de corrección")
    total, por_regla = 0, {}
    for f in sorted(ES.glob("pag-*.json")):
        es = json.loads(f.read_text())
        n = 0
        for k, v in es.items():
            if not isinstance(v, str):
                continue
            nuevo = v
            for rx, rep, motivo in rs:
                nv = rx.sub(rep, nuevo)
                if nv != nuevo:
                    por_regla[rx.pattern] = por_regla.get(rx.pattern, 0) + 1
                    nuevo = nv
            if nuevo != v:
                es[k] = nuevo
                n += 1
        if n and not a.listar:
            f.write_text(json.dumps(es, ensure_ascii=False, indent=1))
        total += n
    print(f"{'(simulación) ' if a.listar else ''}bloques corregidos: {total}")
    for pat, veces in sorted(por_regla.items(), key=lambda x: -x[1])[:12]:
        print(f"  {veces:>3}×  {pat[:60]}")
