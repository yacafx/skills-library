#!/usr/bin/env python3
"""96_qa.py — barrido de defectos sobre traduccion/es/*.json (ruta A).

Detecta por página:
  SIN-TRAD   bloque con texto que no tiene entrada en es/*.json
  INGLES     stopwords inglesas en la traducción (insensible a mayúsculas)
  NUMEROS    cifras del ES distintas a las del EN
  GLOSARIO   término EN presente en el bloque cuyo ES obligatorio no aparece
  TOKEN      restos de tokens (‹, ›) o marcado roto en el ES
Salida: qa/defectos.tsv (página, tipo, id, detalle)
"""
import json, re, sys
from pathlib import Path

P = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(P / "scripts"))

BLOQ = P / "traduccion" / "digital"
ES = P / "traduccion" / "es"

STOP_EN = re.compile(
    r"\b(the|and|with|your|you|when|while|this|that|these|from|have|cannot|"
    r"each|their|they|which|would|should|must|make|takes?|uses?|gains?|during|"
    r"until|unless|other|another|against|through|damage|creature|target|level|"
    r"spell|attack|weapon|armor|feature|choose|following)\b", re.I)
GMB = re.compile(r"GM Binder|gmbinder|WIZARDS|©", re.I)

def numeros(t):
    return sorted(re.findall(r"\d+", re.sub(r"(\d),(\d)", r"\1\2", str(t))))

# glosario term -> es (solo términos "fuertes": multiplabra o capitalizados, para no
# generar falsos positivos con palabras comunes)
glos = []
for l in (P / "traduccion" / "glosario.tsv").read_text().splitlines()[1:]:
    c = l.split("\t")
    if len(c) >= 2 and (len(c[0].split()) > 1 or c[0][:1].isupper()) and len(c[0]) > 3 and c[0] != c[1]:
        glos.append((c[0], c[1]))

defectos = []
for f in sorted(BLOQ.glob("pag-*.json")):
    pg = int(f.stem.split("-")[1])
    datos = json.loads(f.read_text())
    fes = ES / f.name
    es = json.loads(fes.read_text()) if fes.exists() else {}
    pend = {b["id"]: b["texto"] for b in datos["bloques"] if len(b["texto"]) > 2}
    pend.update({t["id"]: t["texto"] for t in datos.get("tabla_frases", []) if len(t["texto"]) > 2})
    for bid, en in pend.items():
        v = es.get(bid)
        if GMB.search(en) or len(re.sub(r"[^A-Za-z]", "", en)) < 3:
            continue
        if not isinstance(v, str) or not v.strip():
            # propio nombre corto idéntico no es defecto (Tauren, Kirin Tor…)
            if len(en) > 24 or STOP_EN.search(en):
                defectos.append((pg, "SIN-TRAD", bid, en[:70]))
            continue
        texto = v
        hits = STOP_EN.findall(texto)
        if len(hits) >= 2:
            defectos.append((pg, "INGLES", bid, f"{sorted(set(h.lower() for h in hits))} → {texto[:60]}"))
        if numeros(en) != numeros(texto):
            defectos.append((pg, "NUMEROS", bid, f"{numeros(en)} vs {numeros(texto)}"))
        if re.search(r"‹[^›]{0,24}$|^[^‹]{0,24}›|«/|/»", texto):
            defectos.append((pg, "TOKEN", bid, texto[:60]))
        for ten, tes in glos:
            if re.search(rf"(?<![A-Za-z]){re.escape(ten)}(?![a-z])", en):
                nucleo = tes.split("(")[0].strip()
                # basta que las palabras significativas aparezcan (cubre «descanso corto
                # o prolongado», reordenamientos y flexiones leves)
                palabras = [w for w in re.split(r"\W+", nucleo.lower()) if len(w) > 3]
                if palabras and any(w not in texto.lower() for w in palabras) \
                        and ten.lower() not in texto.lower():
                    defectos.append((pg, "GLOSARIO", bid, f"{ten} → falta «{nucleo}»"))

out = P / "qa" / "defectos.tsv"
out.write_text("\n".join(f"{p}\t{t}\t{b}\t{d}" for p, t, b, d in defectos))
por_tipo = {}
for _, t, _, _ in defectos:
    por_tipo[t] = por_tipo.get(t, 0) + 1
print(f"{len(defectos)} defectos → {out}")
for t, n in sorted(por_tipo.items(), key=lambda x: -x[1]):
    print(f"  {t}: {n}")
