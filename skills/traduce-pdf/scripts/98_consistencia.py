#!/usr/bin/env python3
"""98_consistencia.py — validación determinística EN↔ES de todo el libro.

Cubre lo MECÁNICO de la validación total (§SKILL «Validación final con Claude»)
para que el juicio humano/Claude se gaste solo en lo que de verdad lo necesita:

  NUM       números, dados y códigos alterados respecto al EN
  MARCADO   asteriscos o tokens ‹› desbalanceados (se imprimirían literales)
  CORTO     ES < 45 % del EN (síntoma de contenido rotado o truncado)
  LARGO     ES > 200 % del EN (síntoma de alucinación o duplicado)
  INGLES    stopwords inglesas en el ES (insensible a mayúsculas)
  DIVERGE   el MISMO texto EN traducido de dos formas distintas en el libro
  PERDIDO   nombre propio del EN que desapareció en el ES (rotación silenciosa)

Salida: qa/consistencia.tsv (pagina, bloque, tipo, detalle). Los casos
documentados en qa/overrides.tsv se omiten.
"""
import json, re, sys, unicodedata
from collections import defaultdict
from pathlib import Path

P = Path(__file__).resolve().parent.parent
_pj = json.loads((Path(__file__).resolve().parent.parent / "proyecto.json").read_text())     if (Path(__file__).resolve().parent.parent / "proyecto.json").exists() else {}

EN_DIR, ES_DIR = P / "traduccion" / "digital", P / "traduccion" / "es"
SALIDA = P / "qa" / "consistencia.tsv"

# Los que el proyecto conserva en inglés a propósito no cuentan como inglés residual.
# palabras que legítimamente quedan en EN: se alimenta de nombres_propios y
# reglas_extra del proyecto.json, más conectores genéricos
CONSERVA = {"the", "of", "and"}
CONSERVA |= {w.lower() for n in _pj.get("nombres_propios", []) for w in n.split()}
CONSERVA |= {w.lower() for r in _pj.get("reglas_extra", [])
             if "inglés" in r or "ingles" in r for w in r.replace(",", " ").split()
             if w.isalpha() and w[0].isupper()}
STOP_EN = {"with", "you", "your", "when", "this", "that", "they", "their", "from",
           "have", "can", "make", "makes", "roll", "damage", "attack", "target",
           "range", "within", "creature", "character", "spend", "mark", "gain",
           "instead", "each", "also", "into", "them", "these", "those", "while",
           "before", "after", "against", "which", "would", "could", "should"}
NUM = re.compile(r"\d+(?:[.,]\d+)?")
TOKEN = re.compile(r"‹[^›]*›")
PROPIO = re.compile(r"\b[A-Z][a-z]{3,}\b")


def norm(t):
    """Texto comparable: sin marcado, sin tokens, sin acentos, minúsculas."""
    t = TOKEN.sub("", str(t)).replace("*", "")
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip().lower()


def numeros(t):
    """Multiconjunto de números; d8+3 y 5/9 se comparan pieza por pieza."""
    return sorted(NUM.findall(TOKEN.sub("", str(t))))


MARCA_AST = re.compile(r"\*{1,3}")


def balanceado(t):
    """Parser de estado: *** alterna negrita+cursiva, ** negrita, * cursiva.
    Contar «**» con str.count da falsos positivos porque «***» contiene uno."""
    b = i = False
    for m in MARCA_AST.finditer(str(t)):
        n = len(m.group(0))
        if n == 3:
            b, i = not b, not i
        elif n == 2:
            b = not b
        else:
            i = not i
    return not b and not i


def conservados():
    """Términos del glosario cuya traducción ES es idéntica al EN: nombres propios
    que deben sobrevivir literales en la traducción."""
    f = P / "traduccion" / "glosario.tsv"
    out = set()
    if not f.exists():
        return out
    for l in f.read_text().splitlines()[1:]:
        cs = l.split("\t")
        if len(cs) >= 2 and cs[0].strip() and norm(cs[0]) == norm(cs[1]):
            for w in re.findall(r"[A-Za-z']{5,}", cs[0]):
                out.add(norm(w))
    return out


CONSERVADOS = set()


def overrides():
    f = P / "qa" / "overrides.tsv"
    ok = set()
    if not f.exists():
        return ok
    for l in f.read_text().splitlines():
        cs = l.split("\t")
        if len(cs) >= 2:
            for bid in cs[1].split(","):
                ok.add((cs[0].strip(), bid.strip()))
    return ok


def main():
    global CONSERVADOS
    CONSERVADOS = conservados()
    saltar = overrides()
    fallos = []
    por_fuente = defaultdict(set)     # texto EN normalizado -> {traducciones ES}
    donde = defaultdict(list)

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
            bid, en = b["id"], b["texto"]
            v = es.get(bid)
            if v is None or v == "~" or (str(pg), bid) in saltar:
                continue
            if isinstance(v, dict):
                v = v.get("t", "")
            if not isinstance(v, str) or not v.strip():
                continue

            if numeros(en) != numeros(v):
                fallos.append((pg, bid, "NUM", f"EN{numeros(en)} vs ES{numeros(v)}"))

            if not balanceado(v):
                fallos.append((pg, bid, "MARCADO", f"marcado desbalanceado: {v[:60]!r}"))
            abre = len(re.findall(r"‹(?!/)", v))
            cierra = len(re.findall(r"‹/", v))
            if abre != cierra:
                fallos.append((pg, bid, "MARCADO", f"tokens ‹› desbalanceados: {v[:60]!r}"))

            nen, nes = len(norm(en)), len(norm(v))
            if nen >= 60:
                if nes < nen * 0.45:
                    fallos.append((pg, bid, "CORTO", f"{nes}/{nen} chars: {v[:60]!r}"))
                elif nes > nen * 2.0:
                    fallos.append((pg, bid, "LARGO", f"{nes}/{nen} chars: {v[:60]!r}"))

            pal = set(re.findall(r"[a-z']+", norm(v)))
            ing = (pal & STOP_EN) - CONSERVA
            if ing:
                fallos.append((pg, bid, "INGLES", f"{sorted(ing)} → {v[:60]!r}"))

            # Solo cuentan los nombres que el glosario declara IDÉNTICOS en ES
            # (nombres propios conservados). Las palabras capitalizadas que sí se
            # traducen —Standard, Guild, Since— darían miles de falsos positivos.
            faltan = [n for n in set(PROPIO.findall(TOKEN.sub("", en)))
                      if norm(n) in CONSERVADOS and norm(n) not in norm(v)]
            if faltan and nen >= 40:
                fallos.append((pg, bid, "PERDIDO", f"nombres del EN ausentes: {faltan}"))

            k = norm(en)
            if len(k) >= 12:
                por_fuente[k].add(norm(v))
                donde[k].append((pg, bid, v))

    for k, versiones in por_fuente.items():
        if len(versiones) > 1:
            sitios = donde[k][:4]
            detalle = " | ".join(f"p{p}:{b}={t[:40]!r}" for p, b, t in sitios)
            pg0, bid0, _ = donde[k][0]
            fallos.append((pg0, bid0, "DIVERGE", f"«{k[:40]}» → {detalle}"))

    fallos.sort(key=lambda f: (f[0], f[1]))
    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text("\n".join("\t".join(map(str, f)) for f in fallos) + "\n")
    tipos = defaultdict(int)
    for _, _, t, _d in fallos:
        tipos[t] += 1
    print(f"{len(fallos)} hallazgos → {SALIDA}")
    for t, n in sorted(tipos.items(), key=lambda x: -x[1]):
        print(f"  {t}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
