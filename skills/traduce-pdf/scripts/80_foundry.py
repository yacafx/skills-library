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
def _capitulos():
    """Rangos (ini, fin, nombre) para los diarios.
    - "foundry_secciones": [[ini, fin, nombre], …] manda si existe (permite excluir
      portada/índice/mazos imprimibles).
    - Si no, se derivan de "secciones" [[pag, nombre], …]: cada una termina donde
      empieza la siguiente; la última en "foundry_ultima_pag" o la última página."""
    fs = _proyecto.get("foundry_secciones")
    if fs:
        return [tuple(x) for x in fs]
    secs = _proyecto.get("secciones", [])
    ult = _proyecto.get("foundry_ultima_pag")
    out = []
    for i, (ini, nombre) in enumerate(secs):
        fin = secs[i+1][0] - 1 if i+1 < len(secs) else (ult or ini)
        out.append((ini, fin, nombre))
    return out

CAP = _capitulos()


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


def _cfg_h():
    c = _proyecto.get("foundry", {})
    return c.get("h1", 18.0), c.get("h2", 12.5), c.get("footer_max", 7.0), c.get("h1_acento", 11.6)


def pagina_html(pg):
    """Piezas (nivel|None, html) de una página, desde los artefactos de la ruta
    que exista: C (en-bloques con tipos explícitos) o A (digital con geometría)."""
    fes = P / "traduccion" / "es" / f"pag-{pg:03d}.json"
    fen_c = P / "traduccion" / "en-bloques" / f"pag-{pg:03d}.json"
    fen_a = P / "traduccion" / "digital" / f"pag-{pg:03d}.json"
    if not fes.exists():
        return []
    es = json.load(open(fes))
    piezas = []

    def emite(t, tipo):
        if tipo in ("footer", "kicker"):
            return
        if tipo in ("titulo", "h_mayor", "h1"):
            piezas.append(("h1", H.escape(re.sub(r"[‹›/scpb]+?›|⏎", " ", t)).strip()))
        elif tipo == "h2":
            piezas.append(("h2", H.escape(re.sub(r"\*+", "", t).strip())))
        elif tipo == "readaloud":
            piezas.append((None, f"<blockquote>{m2h(t)}</blockquote>"))
        elif tipo == "caption":
            piezas.append((None, f"<p><em>{m2h(t)}</em></p>"))
        else:
            piezas.append((None, m2h(t)))

    if fen_c.exists():                      # ruta C: tipos explícitos del OCR
        eb = json.load(open(fen_c))
        tipos = {b["id"]: b["type"] for b in eb["blocks"]}
        for b in eb["blocks"]:
            v = es.get(b["id"])
            if v is None or v == "~":
                continue
            t = v.get("t") if isinstance(v, dict) else v
            if not isinstance(t, str) or not t.strip():
                continue
            emite(t, (v.get("type") if isinstance(v, dict) else None) or tipos.get(b["id"], "cuerpo"))
    elif fen_a.exists():                    # ruta A: jerarquía por tamaño de fuente
        h1_min, h2_min, foot_max, h1_acento = _cfg_h()
        for b in json.load(open(fen_a))["bloques"]:
            v = es.get(b["id"])
            if v is None or v == "~":
                continue
            t = v.get("t") if isinstance(v, dict) else v
            if not isinstance(t, str) or not t.strip():
                continue
            size = b.get("size", 9)
            plano = re.sub(r"\*+|\s+", " ", t).strip()
            col = b.get("color", 0)
            r, g, bl = (col >> 16) & 255, (col >> 8) & 255, col & 255
            # color de acento = ni gris/negro ni blanco (los libros marcan secciones así)
            acento = (max(r, g, bl) - min(r, g, bl)) > 40 and max(r, g, bl) > 90
            versal = plano.isupper() and b.get("lineas", 1) <= 2
            if size <= foot_max:
                tipo = "footer"
            elif size >= h1_min and b.get("lineas", 1) <= 3:
                tipo = "h1"
            elif versal and acento and size >= h1_acento:
                tipo = "h1"
            elif versal and size >= h2_min - 2 and len(plano) <= 70:
                tipo = "h2"
            else:
                tipo = "cuerpo"
            emite(t, tipo)
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
        "authors": [{"name": _proyecto.get("autor", "traduccion-personal")}],
        "packs": [{k: v for k, v in {
            "name": "diarios", "label": f"{TITULO} — Diarios", "path": "packs/diarios",
            "type": "JournalEntry", "system": _proyecto.get("foundry_system")}.items()
            if v is not None}],
    }
    (OUT / "module.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"module.json listo en {OUT}")


if __name__ == "__main__":
    construye()
