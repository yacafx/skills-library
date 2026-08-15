#!/usr/bin/env python3
"""_proyecto.py — configuración por proyecto. Todos los scripts leen de aquí en vez
de tener rutas o nombres quemados.

Cada proyecto vive en su propia carpeta con esta forma:

    <proyecto>/
      proyecto.json      ← configuración (este módulo la lee)
      scripts/           ← copia de los scripts del skill
      corpus/ traduccion/ plantillas/ render/ qa/

proyecto.json mínimo:
{
  "titulo": "Nombre del libro",
  "titulo_es": "Nombre del libro (ES)",
  "slug": "nombre-libro",
  "pdf_origen": "../Nombre del libro.pdf",
  "idioma_destino": "español de México",
  "dominio": "manual de rol D&D 5e",
  "modelo": "qwen3.5:35b-a3b-coding-nvfp4",
  "reglas_extra": ["línea de regla adicional para el traductor", "..."],
  "nombres_propios": ["Karvek", "Puertobruma"],
  "secciones": [[6, "Introducción"], [18, "Capítulo 1"], ...]
}
"""
import json
from pathlib import Path

P = Path(__file__).resolve().parent.parent
_CFG = None


def cfg():
    global _CFG
    if _CFG is None:
        f = P / "proyecto.json"
        _CFG = json.loads(f.read_text()) if f.exists() else {}
    return _CFG


def get(clave, defecto=None):
    return cfg().get(clave, defecto)


def pdf_origen():
    v = get("pdf_origen")
    if not v:
        cands = sorted(P.parent.glob("*.pdf")) + sorted(P.glob("*.pdf"))
        if not cands:
            raise SystemExit("proyecto.json sin 'pdf_origen' y no encontré ningún PDF cerca")
        return cands[0]
    r = Path(v)
    return r if r.is_absolute() else (P / v).resolve()


def slug():
    return get("slug") or "libro-es"


def titulo_es():
    return get("titulo_es") or (get("titulo", "Libro") + " (ES)")


def secciones():
    """[(pág_inicio, nombre)] para marcadores del PDF y diarios. Vacío = sin marcadores."""
    return [tuple(x) for x in get("secciones", [])]


def nombres_propios():
    """Palabras que el QA no debe contar como inglés residual."""
    return set(w.lower() for w in get("nombres_propios", []))


def reglas_traductor():
    """Prompt de sistema del traductor, armado desde la configuración del proyecto."""
    idioma = get("idioma_destino", "español de México")
    dominio = get("dominio", "libro")
    base = f"""Eres traductor profesional al {idioma} de {dominio}.
Recibes los bloques de texto de UNA página en JSON {{id: texto_origen}}. Devuelve SOLO un JSON
con las MISMAS claves y el texto traducido. Reglas obligatorias:
- Registro natural y consistente. Comillas angulares «».
- Usa EXACTAMENTE el glosario adjunto para los términos técnicos (mayúsculas/minúsculas igual).
- Conserva el marcado: **negrita**, *cursiva*, ***negrita-cursiva***. Encabezados run-in
  tipo "***Palabra.***" se conservan.
- Números, cifras y códigos IDÉNTICOS al original: nunca agregues, quites ni conviertas.
  Miles con coma (2,500), nunca con punto.
- Unidades SIN convertir (pies, millas, libras): PROHIBIDO pasar a métrico.
- Números escritos con palabra se traducen con palabra, no con dígito.
- Nombres propios y marcas NO se traducen (ver lista abajo).
- Bloques que continúan de la página anterior (empiezan en minúscula o a media frase):
  tradúcelos como continuación, sin completar la frase.
- Si el bloque es un fragmento incompleto, tradúcelo incompleto: PROHIBIDO inventar o
  completar contenido que no esté en el bloque.
- Encabezados en MAYÚSCULAS quedan en MAYÚSCULAS.
- Sé conciso: la traducción debe caber en el mismo espacio que el original (±5%)."""
    props = get("nombres_propios", [])
    if props:
        base += "\n- NO traducir nunca: " + ", ".join(props) + "."
    for r in get("reglas_extra", []):
        base += f"\n- {r}"
    return base
