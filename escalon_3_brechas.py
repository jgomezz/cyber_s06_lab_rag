"""Escalón 3 · Matriz de brechas: políticas de Andina Pagos frente al reglamento.

Para cada requisito de data/requisitos_reglamento.json busca en las políticas
anonimizadas (RAG) y pide al modelo una evaluación en JSON validada con Pydantic.
Comprueba además que la "evidencia" citada exista de verdad en la política.

Uso:
  python escalon_3_brechas.py --proveedor ollama_cloud
  python escalon_3_brechas.py --proveedor mistral
  python escalon_3_brechas.py --comparar salidas/matriz_brechas_ollama_cloud.xlsx salidas/matriz_brechas_mistral.xlsx

Resultados: salidas/matriz_brechas_<proveedor>.xlsx y salidas/comparacion_modelos.xlsx
"""
import argparse
import json
import re
import time
import unicodedata
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ValidationError

import rag
from llm import CONFIG, chat


class Evaluacion(BaseModel):
    estado: Literal["Cumple", "Parcial", "No cumple"]
    evidencia: str
    brecha: str
    recomendacion: str


SISTEMA = """Eres auditor de cumplimiento de protección de datos personales en Perú.
Evalúas si la política interna de una empresa cumple un requisito del reglamento.
Usa SOLO el texto de la POLÍTICA entregado. Responde únicamente con un objeto JSON con estas claves:
  "estado": "Cumple" | "Parcial" | "No cumple"
  "evidencia": frase copiada TEXTUALMENTE de la política que respalda tu evaluación ("" si no hay)
  "brecha": qué falta para cumplir ("" si cumple)
  "recomendacion": cambio concreto a la política, en una oración"""

PROMPT = """REQUISITO ({articulo}): {requisito}

POLÍTICA (fragmentos recuperados):
{contexto}

Evalúa el requisito y responde solo con el JSON."""


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def evidencia_verificada(evidencia: str, fragmentos: list[dict]) -> str:
    """¿La cita existe en lo recuperado? Detecta evidencia inventada (LLM07 Desinformación)."""
    if not evidencia.strip():
        return "Sin cita"
    ev = normalizar(evidencia)
    return "Sí" if ev and ev in normalizar(" ".join(f["texto"] for f in fragmentos)) else "No"


def evaluar(req: dict, idx, proveedor: str | None) -> dict:
    fragmentos = rag.buscar(idx, req["requisito"], k=3)
    prompt = PROMPT.format(articulo=req["articulo"], requisito=req["requisito"], contexto=rag.contexto(fragmentos))
    inicio, error = time.time(), ""
    for intento in range(2):  # un reintento si el JSON no es válido
        texto = chat(prompt, provider=proveedor, system=SISTEMA, json_mode=True)
        try:
            ev = Evaluacion.model_validate(json.loads(texto))
            break
        except (json.JSONDecodeError, ValidationError) as e:
            error = str(e).splitlines()[0]
            prompt += f"\n\nTu respuesta anterior no era válida ({error}). Responde solo el JSON con los valores permitidos."
    else:
        ev = Evaluacion(estado="No cumple", evidencia="", brecha=f"ERROR: el modelo no entregó JSON válido ({error})", recomendacion="")
    return {"ID": req["id"], "Artículo": req["articulo"], "Requisito": req["requisito"], "Estado": ev.estado,
            "Evidencia en la política": ev.evidencia, "¿Evidencia verificada?": evidencia_verificada(ev.evidencia, fragmentos),
            "Brecha": ev.brecha, "Recomendación": ev.recomendacion,
            "Secciones consultadas": ", ".join(sorted({f["fuente"] for f in fragmentos})),
            "Segundos": round(time.time() - inicio, 1), "Intentos": intento + 1}


def guardar_excel(df: pd.DataFrame, archivo, anchos: dict):
    with pd.ExcelWriter(archivo, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="Matriz")
        hoja = xw.sheets["Matriz"]
        for col, ancho in anchos.items():
            hoja.column_dimensions[col].width = ancho
        hoja.freeze_panes = "D2"


def comparar(a: str, b: str):
    da, db = pd.read_excel(a), pd.read_excel(b)
    na, nb = rag.Path(a).stem.replace("matriz_brechas_", ""), rag.Path(b).stem.replace("matriz_brechas_", "")
    df = da[["ID", "Artículo", "Requisito", "Estado"]].merge(db[["ID", "Estado"]], on="ID", suffixes=(f" ({na})", f" ({nb})"))
    df["¿Coinciden?"] = (df[f"Estado ({na})"] == df[f"Estado ({nb})"]).map({True: "Sí", False: "No"})
    acuerdo = (df["¿Coinciden?"] == "Sí").mean()
    archivo = rag.SALIDAS / "comparacion_modelos.xlsx"
    guardar_excel(df, archivo, {"A": 6, "B": 14, "C": 70, "D": 16, "E": 16, "F": 12})
    print(df[["ID", f"Estado ({na})", f"Estado ({nb})", "¿Coinciden?"]].to_string(index=False))
    print(f"\nCoinciden en {acuerdo:.0%} de los requisitos. Detalle en {archivo.relative_to(rag.BASE)}")
    print("Los requisitos donde no coinciden son los que el equipo debe revisar leyendo la política.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proveedor", help="proveedor de config.yaml (por defecto, el de 'default')")
    ap.add_argument("--reconstruir", action="store_true", help="vuelve a indexar las políticas")
    ap.add_argument("--comparar", nargs=2, metavar=("MATRIZ_A", "MATRIZ_B"), help="compara dos matrices ya generadas")
    args = ap.parse_args()
    if args.comparar:
        return comparar(*args.comparar)

    proveedor = args.proveedor or CONFIG["default"]
    requisitos = json.loads((rag.DATA / "requisitos_reglamento.json").read_text(encoding="utf-8"))
    print("Preparando el índice de las políticas anonimizadas")
    idx = rag.indice("politica", rag.docs_politica, reconstruir=args.reconstruir)

    filas, inicio = [], time.time()
    for req in requisitos:
        fila = evaluar(req, idx, args.proveedor)
        filas.append(fila)
        print(f"  {fila['ID']} {fila['Artículo']:<16} {fila['Estado']:<10} evidencia verificada: {fila['¿Evidencia verificada?']:<8} ({fila['Segundos']} s)")

    df = pd.DataFrame(filas)
    archivo = rag.SALIDAS / f"matriz_brechas_{proveedor}.xlsx"
    guardar_excel(df, archivo, {"A": 6, "B": 14, "C": 60, "D": 12, "E": 50, "F": 12, "G": 50, "H": 50, "I": 28, "J": 10, "K": 9})
    resumen = df["Estado"].value_counts().to_dict()
    no_verif = (df["¿Evidencia verificada?"] == "No").sum()
    print(f"\n{resumen} · {no_verif} citas no encontradas en la política · {time.time() - inicio:.0f} s en total")
    print(f"Matriz guardada en {archivo.relative_to(rag.BASE)}")


if __name__ == "__main__":
    main()
