#!/usr/bin/env python3
"""81_foundry_fase2.py — F8 fases 2-4: actores dnd5e desde __statblocks__,
RollTables desde las tablas reconstruidas, escenas de los mapas y handouts de arte.
Todo re-empaquetado desde los artefactos en disco."""
import glob, html as H, json, re, secrets, subprocess, sys
from pathlib import Path

SC = Path(__file__).resolve().parent
P = SC.parent
import _proyecto
SLUG = _proyecto.slug()
TITULO = _proyecto.titulo_es()
OUT = P / "foundry" / SLUG
import importlib.util
spec = importlib.util.spec_from_file_location("f1", SC / "80_foundry.py")
F1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(F1)
uid, m2h, sb2h = F1.uid, F1.m2h, F1.sb2h

CAR = {"FUE": "str", "DES": "dex", "CON": "con", "INT": "int", "SAB": "wis", "CAR": "cha"}


def num(rx, t, cast=int, d=None):
    mo = re.search(rx, t)
    if not mo:
        return d
    v = mo.group(1).replace(",", "")
    return cast(eval(v)) if "/" in v else cast(v)


def actor_de(sb):
    if not sb.get("titulo"):
        return None
    campos = " ".join(s.get("t", "") for s in sb["secciones"] if "t" in s)
    ab = {}
    for s in sb["secciones"]:
        if "tabla" in s:
            for k, v in s["tabla"]:
                mo = re.match(r"(\d+)", v.strip())
                if k in CAR and mo:
                    ab[CAR[k]] = {"value": int(mo.group(1))}
    mov = {}
    mo = re.search(r"\*\*Velocidad\*\*([^\n*]+)", campos)
    if mo:
        v = mo.group(1)
        for pal, clave in (("volar", "fly"), ("nadar", "swim"), ("trepar", "climb"), ("excavar", "burrow")):
            m2 = re.search(pal + r"\s+(\d+)", v)
            if m2:
                mov[clave] = int(m2.group(1))
        m2 = re.match(r"\s*(\d+)", v)
        if m2:
            mov["walk"] = int(m2.group(1))
    hp = num(r"\*\*Puntos de golpe\*\*\s+(\d+)", campos, d=10)
    formula = (re.search(r"\*\*Puntos de golpe\*\*\s+\d+\s*\(([^)]+)\)", campos) or [None, ""])[1]
    cr = num(r"\*\*Desafío\*\*\s+([\d/]+)", campos, cast=float, d=0)
    items = []
    for s in sb["secciones"]:
        if "t" not in s:
            continue
        tipo_item = {"ACCIONES": "acción", "ACCIONES ADICIONALES": "acción adicional",
                     "REACCIONES": "reacción", "ACCIONES LEGENDARIAS": "acción legendaria"}.get(s.get("h"), "rasgo" if s.get("h") is None and "***" in s.get("t", "") else None)
        if not tipo_item:
            continue
        for mo in re.finditer(r"\*\*\*(.+?)\.\*\*\*\s*(.*?)(?=\*\*\*|$)", s["t"], re.S):
            items.append({"_id": uid(), "name": mo.group(1).strip()[:60], "type": "feat",
                          "system": {"description": {"value": f"<p><em>({tipo_item})</em></p>" + m2h(mo.group(2).strip())},
                                     "type": {"value": ""}},
                          "img": "icons/svg/item-bag.svg", "effects": [], "flags": {}})
    return {"_id": uid(), "name": sb["titulo"].title()[:80], "type": "npc", "img": "icons/svg/mystery-man.svg",
            "system": {"abilities": ab,
                       "attributes": {"ac": {"calc": "flat", "flat": num(r"\*\*Clase de Armadura\*\*\s+(\d+)", campos, d=10)},
                                      "hp": {"value": hp, "max": hp, "formula": formula},
                                      "movement": mov},
                       "details": {"cr": cr, "type": {"value": "", "custom": re.sub(r"\*", "", sb.get("sub") or "")},
                                   "biography": {"value": sb2h(sb)}},
                       "traits": {}},
            "items": items, "effects": [], "folder": None, "sort": 0, "flags": {},
            "prototypeToken": {"name": sb["titulo"].title()[:80]}, "ownership": {"default": 0}}


def fase_actores():
    src = OUT / "packs" / "src" / "actores"
    src.mkdir(parents=True, exist_ok=True)
    vistos, n = set(), 0
    for f in sorted(glob.glob(str(P / "traduccion" / "es" / "*.json"))):
        es = json.load(open(f))
        for sb in es.get("__statblocks__", []):
            a = actor_de(sb)
            if a and a["name"].lower() not in vistos:
                vistos.add(a["name"].lower())
                (src / f"{re.sub(r'[^a-z0-9]+', '-', a['name'].lower())}.json").write_text(
                    json.dumps(a, ensure_ascii=False, indent=1))
                n += 1
    print(f"actores: {n}")


def fase_tablas():
    src = OUT / "packs" / "src" / "tablas"
    src.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(glob.glob(str(P / "traduccion" / "es" / "*.json"))):
        es = json.load(open(f))
        for v in es.values():
            t = v.get("t") if isinstance(v, dict) else None
            if not t or not re.search(r"\*\*d(\d+)[ —]", t):
                continue
            lineas = t.split("\n\n")
            titulo = re.sub(r"\*", "", lineas[0]).strip().title()
            dado = re.search(r"\*\*d(\d+)", t).group(1)
            resultados = []
            for ln in lineas:
                mo = re.match(r"\*\*(\d+)(?:-(\d+))?\*\* — (.+)", ln, re.S)
                if mo:
                    a, b = int(mo.group(1)), int(mo.group(2) or mo.group(1))
                    resultados.append({"_id": uid(), "type": 0, "text": re.sub(r"\*", "", mo.group(3)).strip(),
                                       "range": [a, b], "weight": b - a + 1, "drawn": False, "flags": {}})
            if len(resultados) >= 2:
                doc = {"_id": uid(), "name": f"{TITULO} — {titulo[:70]}", "formula": f"1d{dado}",
                       "results": resultados, "replacement": True, "displayRoll": True,
                       "folder": None, "sort": 0, "flags": {}, "ownership": {"default": 0}}
                (src / f"tabla-{n:02d}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
                n += 1
    print(f"rolltables: {n}")


def fase_escenas_handouts():
    from PIL import Image
    assets = OUT / "assets"
    assets.mkdir(exist_ok=True)
    src_e = OUT / "packs" / "src" / "escenas"
    src_e.mkdir(parents=True, exist_ok=True)
    NOMBRES = {122: "Bóveda de las Tres Lunas", 140: "Tumba de las Almas Descarriadas", 155: "El Belvedere Rojo"}
    for pg, nombre in NOMBRES.items():
        subprocess.run(["pdftoppm", "-r", "120", "-jpeg", str(P / "render" / "paginas" / f"pag-{pg:03d}.pdf"),
                        str(assets / f"tmp{pg}")], check=True)
        j = sorted(assets.glob(f"tmp{pg}*.jpg"))[0]
        im = Image.open(j)
        im.save(assets / f"mapa-{pg}.webp", quality=88)
        j.unlink()
        doc = {"_id": uid(), "name": f"{TITULO} — {nombre}",
               "background": {"src": f"modules/{SLUG}/assets/mapa-{pg}.webp"},
               "width": im.width, "height": im.height, "padding": 0,
               "grid": {"type": 1, "size": 100, "distance": 5, "units": "pies"},
               "tokenVision": False, "fog": {"exploration": False},
               "folder": None, "sort": 0, "flags": {}, "ownership": {"default": 0}}
        (src_e / f"mapa-{pg}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    print("escenas: 3")
    ARTE = [1, 5, 17, 57, 73, 111, 131, 149, 169, 175, 191, 244, 249, 256]
    paginas = []
    for i, pg in enumerate(ARTE):
        subprocess.run(["pdftoppm", "-r", "110", "-jpeg", str(P / "render" / "paginas" / f"pag-{pg:03d}.pdf"),
                        str(assets / f"tmpa{pg}")], check=True)
        j = sorted(assets.glob(f"tmpa{pg}*.jpg"))[0]
        Image.open(j).save(assets / f"arte-{pg}.webp", quality=86)
        j.unlink()
        paginas.append({"_id": uid(), "name": f"Lámina p{pg}", "type": "image", "sort": i * 10,
                        "title": {"show": True, "level": 1},
                        "src": f"modules/{SLUG}/assets/arte-{pg}.webp", "image": {}, "flags": {}})
    doc = {"_id": uid(), "name": f"{TITULO} — Láminas y handouts", "pages": paginas,
           "folder": None, "sort": 900, "flags": {}, "ownership": {"default": 0}}
    (OUT / "packs" / "src" / "diarios" / "handouts.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    print(f"handouts: {len(paginas)} láminas")


def manifiesto_y_pack():
    mj = json.load(open(OUT / "module.json"))
    mj["packs"] = [
        {"name": "diarios", "label": f"{TITULO} — Diarios", "path": "packs/diarios", "type": "JournalEntry", "system": "dnd5e"},
        {"name": "actores", "label": f"{TITULO} — Bestiario", "path": "packs/actores", "type": "Actor", "system": "dnd5e"},
        {"name": "tablas", "label": f"{TITULO} — Tablas", "path": "packs/tablas", "type": "RollTable", "system": "dnd5e"},
        {"name": "escenas", "label": f"{TITULO} — Mapas", "path": "packs/escenas", "type": "Scene", "system": "dnd5e"},
    ]
    mj["version"] = "0.2.0"
    (OUT / "module.json").write_text(json.dumps(mj, ensure_ascii=False, indent=1))
    for p in ("diarios", "actores", "tablas", "escenas"):
        r = subprocess.run(["bunx", "@foundryvtt/foundryvtt-cli", "package", "pack", p,
                            "--in", f"packs/src/{p}", "--out", f"packs/{p}"], cwd=OUT,
                           capture_output=True, text=True)
        print(f"pack {p}: {'✓' if r.returncode == 0 else r.stderr.strip()[-120:]}")


if __name__ == "__main__":
    fase_actores()
    fase_tablas()
    fase_escenas_handouts()
    manifiesto_y_pack()
    print("F8 COMPLETA")
