#!/usr/bin/env python3
"""80_foundry.py — F8 fase 1: módulo companion de Foundry v14 con los DIARIOS
por capítulo (páginas por sección) + diario-glosario, generados desde los
artefactos del pipeline (traduccion/es/*.json + en-bloques). El texto ya vive
en disco; esto solo lo re-empaqueta a HTML/JSON de Foundry.

Salida: foundry/<slug>/ (module.json + packs/src/…). Compilar packs:
  cd foundry/<slug> && bunx @foundryvtt/foundryvtt-cli package pack diarios --in packs/src/diarios --out packs/diarios
"""
import html as H
import json, re, secrets
from pathlib import Path

P = Path(__file__).resolve().parent.parent
import _proyecto
SLUG = _proyecto.slug()
TITULO = _proyecto.titulo_es()
OUT = P / "foundry" / SLUG
CAP = [  # (pág inicio, pág fin, nombre)
    (6, 17, "Introducción"), (18, 37, "Capítulo 1"), (38, 57, "Capítulo 2"),
    (58, 73, "Capítulo 3"), (74, 93, "Capítulo 4"), (94, 111, "Capítulo 5"),
    (112, 131, "Capítulo 6"), (132, 149, "Capítulo 7"), (150, 169, "Capítulo 8"),
    (170, 175, "Capítulo 9"), (176, 191, "Capítulo 10"), (192, 204, "Capítulo 11"),
    (205, 240, "Apéndice A: Bestiario"), (241, 256, "Apéndice B"), (257, 257, "Rastreador de Secretos"),
]


def uid():
    return secrets.token_hex(8)


def m2h(t):
    t = H.escape(t)
    t = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", t, flags=re.S)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t, flags=re.S)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t, flags=re.S)
    t = t.replace("‹sc›", '<span style="font-variant:small-caps">').replace("‹/sc›", "</span>")
    t = t.replace("⏎", "<br>")
    paras = [f"<p>{p.strip()}</p>" for p in t.split("\n\n") if p.strip()]
    return "".join(paras)


def sb2h(sb):
    partes = [f"<h3>{H.escape(sb.get('titulo') or '')}</h3>"] if sb.get("titulo") else []
    if sb.get("sub"):
        partes.append(m2h(sb["sub"]))
    for sec in sb.get("secciones", []):
        if "tabla" in sec:
            celdas = "".join(f"<td style='text-align:center'><b>{a}</b><br>{v}</td>" for a, v in sec["tabla"])
            partes.append(f"<table><tr>{celdas}</tr></table>")
        else:
            if sec.get("h"):
                partes.append(f"<h4>{H.escape(sec['h'])}</h4>")
            partes.append(m2h(sec.get("t", "")))
    return "".join(partes)


def pagina_html(pg):
    fes = P / "traduccion" / "es" / f"pag-{pg:03d}.json"
    fen = P / "traduccion" / "en-bloques" / f"pag-{pg:03d}.json"
    if not fes.exists() or not fen.exists():
        return []
    es = json.load(open(fes))
    eb = json.load(open(fen))
    tipos = {b["id"]: b["type"] for b in eb["blocks"]}
    piezas = []  # (nivel_encabezado|None, html)
    for b in eb["blocks"]:
        bid = b["id"]
        v = es.get(bid)
        if v is None or v == "~":
            continue
        t = v.get("t") if isinstance(v, dict) else v
        if not isinstance(t, str) or not t.strip():
            continue
        tipo = (v.get("type") if isinstance(v, dict) else None) or tipos.get(bid, "cuerpo")
        if tipo in ("footer", "kicker"):
            continue
        if tipo in ("titulo", "h_mayor", "h1"):
            piezas.append(("h1", H.escape(re.sub(r"[‹›/scpb]+?›|⏎", " ", t)).strip()))
        elif tipo == "h2":
            piezas.append(("h2", H.escape(t.strip())))
        elif tipo == "readaloud":
            piezas.append((None, f"<blockquote>{m2h(t)}</blockquote>"))
        elif tipo == "caption":
            piezas.append((None, f"<p><em>{m2h(t)}</em></p>"))
        else:
            piezas.append((None, m2h(t)))
    for sb in es.get("__statblocks__", []):
        piezas.append((None, sb2h(sb)))
    return piezas


def construye():
    src = OUT / "packs" / "src" / "diarios"
    src.mkdir(parents=True, exist_ok=True)
    for ini, fin, nombre in CAP:
        paginas_fd = []
        actual_nombre, actual_html = nombre, []
        orden = 0
        for pg in range(ini, fin + 1):
            for nivel, contenido in pagina_html(pg):
                if nivel == "h1" and actual_html:
                    orden += 10
                    paginas_fd.append({"_id": uid(), "name": actual_nombre[:120], "type": "text",
                                       "title": {"show": False, "level": 1}, "sort": orden,
                                       "text": {"format": 1, "content": "".join(actual_html)}})
                    actual_nombre, actual_html = contenido, [f"<h1>{contenido}</h1>"]
                elif nivel == "h1":
                    actual_nombre = contenido
                    actual_html.append(f"<h1>{contenido}</h1>")
                elif nivel == "h2":
                    actual_html.append(f"<h2>{contenido}</h2>")
                else:
                    actual_html.append(contenido)
        if actual_html:
            orden += 10
            paginas_fd.append({"_id": uid(), "name": actual_nombre[:120], "type": "text",
                               "title": {"show": False, "level": 1}, "sort": orden,
                               "text": {"format": 1, "content": "".join(actual_html)}})
        doc = {"_id": uid(), "name": f"{TITULO} — {nombre}", "pages": paginas_fd,
               "folder": None, "sort": 0, "flags": {}, "ownership": {"default": 0}}
        (src / f"{nombre.lower().replace(' ', '-').replace(':', '')}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=1))
        print(f"{nombre}: {len(paginas_fd)} páginas de diario")
    # glosario
    filas = [l.split("\t")[:2] for l in (P / "traduccion" / "glosario.tsv").read_text().splitlines()[1:] if "\t" in l]
    tabla = "".join(f"<tr><td>{H.escape(a)}</td><td>{H.escape(b)}</td></tr>" for a, b in sorted(filas))
    doc = {"_id": uid(), "name": f"{TITULO} — Glosario",
           "pages": [{"_id": uid(), "name": "Glosario", "type": "text", "sort": 10,
                      "title": {"show": True, "level": 1},
                      "text": {"format": 1, "content": f"<table><tr><th>EN</th><th>ES</th></tr>{tabla}</table>"}}],
           "folder": None, "sort": 0, "flags": {}, "ownership": {"default": 0}}
    (src / "glosario.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    manifest = {
        "id": SLUG, "title": f"{TITULO} — Companion (uso personal)",
        "description": "Diarios en español generados del pipeline de traducción personal.",
        "version": "0.1.0", "compatibility": {"minimum": "12", "verified": "14"},
        "authors": [{"name": "yacaFx"}],
        "packs": [{"name": "diarios", "label": f"{TITULO} — Diarios", "path": "packs/diarios",
                   "type": "JournalEntry", "system": "dnd5e"}],
    }
    (OUT / "module.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"module.json listo en {OUT}")


if __name__ == "__main__":
    construye()
