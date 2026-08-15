#!/usr/bin/env python3
"""21_glosario_check.py — Gate V3 (parte automática).
1) TSV bien formado, sin duplicados de 'en'.
2) Filas fuente=SRD*: el término ES debe aparecer en el texto del SRD correspondiente.
3) Filas V-AUTO (conjuros): busca la forma exacta en el SRD y reporta la que encuentre.
"""
import csv, re, os, unicodedata, random

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(BASE, "traduccion")
srd51 = open(os.path.join(T, "ref", "srd51-es.txt"), encoding="utf-8").read()
srd521 = open(os.path.join(T, "ref", "srd521-es.txt"), encoding="utf-8").read()

rows = list(csv.DictReader(open(os.path.join(T, "glosario.tsv")), delimiter="\t"))
print(f"filas: {len(rows)}")
vistos = {}
for r in rows:
    if r["en"] in vistos:
        print("  DUP:", r["en"])
    vistos[r["en"]] = r

def esta(term, txt):
    # busca la parte útil más larga del término ES
    partes = re.split(r"\s*/\s*|\s*\(\s*", term)
    cand = max(partes, key=len).strip(" )")
    cand = re.sub(r"^(el|la|los|las|un|una)\s+", "", cand, flags=re.I)
    return (cand.lower() in txt.lower(), cand)

fallas = []
for r in rows:
    if r["fuente"].startswith("SRD"):
        txt = srd521 if "5.2.1" in r["fuente"] else srd51
        ok, cand = esta(r["es"], txt)
        if not ok:
            fallas.append((r["en"], r["es"], cand))
print(f"\nSRD sin coincidencia ({len(fallas)}):")
for f in fallas:
    print("  ✗", f[0], "->", f[1], f"(busqué «{f[2]}»)")

print("\nV-AUTO (conjuros) — lo que dice el SRD 5.1:")
for r in rows:
    if r["fuente"] == "V-AUTO":
        base = r["en"].split("(")[0].strip()
        # heurística: buscar palabra clave del ES propuesto
        clave = re.sub(r"^(el|la)\s+", "", r["es"].split()[-1].lower())
        hits = sorted(set(m.group(0) for m in re.finditer(
            r"[A-ZÁÉÍÓÚÑ][a-záéíóúüñ]*(?:\s+[a-záéíóúüñ]+){0,2}", srd51)
            if clave[:6] in m.group(0).lower()))[:4]
        print(f"  {base:18} propuesto «{r['es']}» | SRD contiene: {hits if hits else '—'}")

print("\n=== MUESTRA ALEATORIA (20) PARA SPOT-CHECK HUMANO ===")
random.seed(42)
for r in random.sample(rows, 20):
    print(f"  {r['en']:42} → {r['es']:44} [{r['fuente']}]")
