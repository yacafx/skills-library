#!/usr/bin/env python3
"""_validacion.py — contrato del artefacto de VALIDACIÓN TOTAL EN↔ES (F7.5).

La validación de contenido la hace el agente orquestador (no el modelo local) leyendo
TODO el texto contra el original. Su evidencia es `qa/validacion-total.tsv`:

    # cobertura: 1-153            ← rangos de páginas revisadas (coma-separados)
    # correcciones: 214           ← total de reemplazos aplicados (informativo)
    pagina\tbloque\ttipo\tfragmento_actual\tfragmento_corregido
    ...                           ← una fila por corrección adjudicada (puede haber 0)

Un tramo sin hallazgos TAMBIÉN cuenta como revisado: lo que manda es `# cobertura`.
`95_libro.py` no produce el entregable con nombre limpio sin cobertura completa
(sale `-BORRADOR.pdf`); `96_qa.py` reporta su ausencia como defecto VALIDACION.
Escape consciente: `95_libro.py --sin-validar`.
"""
import re
from pathlib import Path

ARCHIVO = "validacion-total.tsv"


def estado(P, n_pags):
    """(ok, motivo): ¿existe el artefacto y cubre las n_pags del documento?"""
    f = Path(P) / "qa" / ARCHIVO
    if not f.exists():
        return False, f"falta qa/{ARCHIVO} — la validación total EN↔ES no está registrada"
    cov = set()
    for l in f.read_text().splitlines():
        m = re.match(r"#\s*cobertura\s*:\s*(.+)", l, re.I)
        if not m:
            continue
        for tramo in m.group(1).split(","):
            a, _, b = tramo.strip().partition("-")
            try:
                ini, fin = int(a), int(b or a)
            except ValueError:
                continue
            cov.update(range(ini, fin + 1))
    if not cov:
        return False, f"qa/{ARCHIVO} existe pero no declara «# cobertura: INI-FIN»"
    faltan = [p for p in range(1, n_pags + 1) if p not in cov]
    if faltan:
        return False, (f"cobertura incompleta: faltan {len(faltan)} páginas "
                       f"(p. ej. {faltan[:8]})")
    n_corr = sum(1 for l in f.read_text().splitlines()
                 if l.strip() and not l.startswith("#") and "\t" in l)
    return True, f"validación total registrada: {len(cov)} páginas, {n_corr} correcciones"
