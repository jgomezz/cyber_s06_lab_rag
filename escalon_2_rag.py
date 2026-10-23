"""Escalón 2 · Preguntarle al reglamento con RAG.

Indexa el extracto del Reglamento de la Ley 29733 (un fragmento por artículo) y responde
preguntas citando los artículos usados. El modelo solo puede responder con lo recuperado.

Uso:
  python escalon_2_rag.py                                # las 6 preguntas de la guía
  python escalon_2_rag.py --proveedor mistral            # mismas preguntas con otro modelo
  python escalon_2_rag.py --pregunta "¿Qué es la disociación?"
  python escalon_2_rag.py --reconstruir                  # vuelve a crear el índice

Resultado: salidas/respuestas_rag_<proveedor>.md
"""
import argparse
import time

import rag
from llm import CONFIG, chat

PREGUNTAS = [
    "¿En qué plazo se debe notificar a la autoridad un incidente de seguridad de datos personales y qué debe incluir la notificación?",
    "¿Cada cuánto tiempo deben verificarse los privilegios asignados a los usuarios?",
    "¿Por cuánto tiempo deben conservarse los registros de interacción con datos personales?",
    "¿Qué exige el reglamento sobre las copias de respaldo?",
    "¿Se puede usar WhatsApp u otra mensajería no institucional en el tratamiento de datos personales?",
    "¿Cuál es el monto de la multa por no notificar un incidente de seguridad?",
]

SISTEMA = """Eres un asistente de cumplimiento normativo. Respondes en español y SOLO con la
información del CONTEXTO, que contiene artículos del Reglamento de la Ley 29733 de Perú.
Reglas:
- Cita entre corchetes el artículo de cada afirmación, por ejemplo [Art. 46].
- Si el contexto no contiene la respuesta, di exactamente: "El extracto del reglamento no lo indica."
- No inventes plazos, montos ni artículos."""


def responder(idx, pregunta: str, proveedor: str | None, k: int) -> dict:
    inicio = time.time()
    fragmentos = rag.buscar(idx, pregunta, k=k)
    prompt = f"CONTEXTO:\n{rag.contexto(fragmentos)}\n\nPREGUNTA: {pregunta}"
    respuesta = chat(prompt, provider=proveedor, system=SISTEMA)
    return {"pregunta": pregunta, "respuesta": respuesta.strip(), "segundos": round(time.time() - inicio, 1),
            "fuentes": [f"{f['fuente']} ({f['puntaje']})" for f in fragmentos]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proveedor", help="proveedor de config.yaml (por defecto, el de 'default')")
    ap.add_argument("--pregunta", help="una pregunta propia en vez de las de la guía")
    ap.add_argument("-k", type=int, default=4, help="cantidad de fragmentos a recuperar (por defecto 4)")
    ap.add_argument("--reconstruir", action="store_true", help="borra y vuelve a crear el índice")
    args = ap.parse_args()
    proveedor = args.proveedor or CONFIG["default"]

    print("Preparando el índice del reglamento")
    idx = rag.indice("reglamento", rag.docs_reglamento, reconstruir=args.reconstruir)

    salida = [f"# Respuestas RAG · modelo: {proveedor} · embeddings: {CONFIG['embeddings']['provider']}\n"]
    for n, pregunta in enumerate([args.pregunta] if args.pregunta else PREGUNTAS, 1):
        r = responder(idx, pregunta, args.proveedor, args.k)
        print(f"\n[{n}] {r['pregunta']}\n{r['respuesta']}\n   Fuentes recuperadas: {', '.join(r['fuentes'])} · {r['segundos']} s")
        salida.append(f"## {n}. {r['pregunta']}\n\n{r['respuesta']}\n\n*Fuentes: {', '.join(r['fuentes'])} · {r['segundos']} s*\n")

    rag.SALIDAS.mkdir(exist_ok=True)
    archivo = rag.SALIDAS / f"respuestas_rag_{proveedor}.md"
    archivo.write_text("\n".join(salida), encoding="utf-8")
    print(f"\nGuardado en {archivo.relative_to(rag.BASE)}. Verifiquen cada cita contra data/reglamento_ley29733_extracto.md")


if __name__ == "__main__":
    main()
