"""Escalón 1 · Convertir y anonimizar las políticas de Andina Pagos.

Pasos:
  A. Convierte los documentos de data/ (Word y PDF) a Markdown con markitdown.
  B. Anonimiza nombres, correos, teléfonos, DNI e IP con Presidio (todo en tu equipo).
  C. Pide a un modelo que revise si quedó algún dato identificable (por defecto, Ollama Cloud, sobre el texto YA anonimizado).

Uso:
  python escalon_1_anonimizar.py                       # revisión con el modelo por defecto (Ollama Cloud)
  python escalon_1_anonimizar.py --proveedor ollama_cloud
  python escalon_1_anonimizar.py --sin-llm             # solo pasos A y B

Resultados en salidas/: md/ (convertidos), anonimizado/ (para usar en los escalones 2 y 3)
y privado/ (tabla de reemplazos: NUNCA se comparte ni se envía a un modelo en la nube).
"""
import argparse
import json
import re
import time
from collections import Counter

from markitdown import MarkItDown
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import IpRecognizer, PhoneRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from llm import BASE, CONFIG, chat

DATA, SALIDAS = BASE / "data", BASE / "salidas"
ENTIDADES = {  # tipo de Presidio -> etiqueta que verá el modelo
    "PERSON": "PERSONA", "EMAIL_ADDRESS": "CORREO", "PHONE_NUMBER": "TELEFONO",
    "PE_DNI": "DNI", "IP_ADDRESS": "IP", "EMPRESA": "EMPRESA",
}


def crear_analizador() -> AnalyzerEngine:
    """Presidio configurado para español, con reconocedores propios para DNI y nombre de la empresa."""
    nlp = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "es", "model_name": CONFIG["anonimizacion"]["spacy_model"]}],
        "ner_model_configuration": {"model_to_presidio_entity_mapping": {"PER": "PERSON", "LOC": "LOCATION", "ORG": "ORGANIZATION"},
                                    "labels_to_ignore": ["MISC"]},
    }).create_engine()
    registro = RecognizerRegistry(supported_languages=["es"])
    registro.load_predefined_recognizers(languages=["es"], nlp_engine=nlp)
    registro.add_recognizer(PatternRecognizer(  # correo por patrón (no requiere internet)
        supported_entity="EMAIL_ADDRESS", supported_language="es",
        patterns=[Pattern("correo", r"\b[\w.+-]+@[\w-]+(\.[\w-]+)+\b", 0.9)]))
    registro.add_recognizer(IpRecognizer(supported_language="es"))
    registro.add_recognizer(PhoneRecognizer(supported_language="es", supported_regions=("PE",)))
    registro.add_recognizer(PatternRecognizer(
        supported_entity="PE_DNI", supported_language="es", context=["dni", "documento", "identidad"],
        patterns=[Pattern("dni_8_digitos", r"\b\d{8}\b", 0.5)]))
    registro.add_recognizer(PatternRecognizer(
        supported_entity="EMPRESA", supported_language="es", deny_list=["Andina Pagos S.A.", "Andina Pagos", "ANDINA"]))
    return AnalyzerEngine(registry=registro, nlp_engine=nlp, supported_languages=["es"])


def anonimizar(texto: str, analizador: AnalyzerEngine) -> tuple[str, dict, Counter]:
    """Reemplaza cada dato por una etiqueta numerada y consistente (<PERSONA_1>, <CORREO_2>...)."""
    permitidos = CONFIG["anonimizacion"].get("permitidos") or []
    hallazgos = analizador.analyze(text=texto, language="es", entities=list(ENTIDADES),
                                   score_threshold=0.4, allow_list=permitidos)
    mapa, contador = {}, Counter()

    def reemplazo(tipo):
        def fn(valor):
            clave = (tipo, valor)
            if clave not in mapa:
                contador[tipo] += 1
                mapa[clave] = f"<{ENTIDADES[tipo]}_{contador[tipo]}>"
            return mapa[clave]
        return fn

    operadores = {t: OperatorConfig("custom", {"lambda": reemplazo(t)}) for t in ENTIDADES}
    resultado = AnonymizerEngine().anonymize(text=texto, analyzer_results=hallazgos, operators=operadores)
    tabla = {etiqueta: valor for (tipo, valor), etiqueta in mapa.items()}
    return resultado.text, tabla, contador


PROMPT_REVISION = """Eres auditor de privacidad. El siguiente texto ya fue anonimizado: las etiquetas
como <PERSONA_1>, <CORREO_2> o <EMPRESA_1> reemplazan datos reales y NO debes reportarlas.

Busca datos que TODAVÍA permitan identificar a una persona, a la empresa o su infraestructura:
nombres, correos, teléfonos, anexos, documentos de identidad, direcciones IP, nombres de servidores,
cuentas o dominios internos.

Responde solo con JSON: {{"hallazgos": [{{"texto": "...", "tipo": "...", "motivo": "..."}}]}}
Si no encuentras nada, responde {{"hallazgos": []}}.

TEXTO:
{texto}"""


def revisar_con_llm(texto: str, proveedor: str | None) -> list[dict]:
    """Revisa el texto por partes (los modelos pequeños leen mejor fragmentos cortos)."""
    partes = re.split(r"\n(?=#)", texto)
    bloques, actual = [], ""
    for p in partes:
        if len(actual) + len(p) > 2500 and actual:
            bloques.append(actual)
            actual = ""
        actual += "\n" + p
    bloques.append(actual)
    hallazgos = []
    for b in bloques:
        respuesta = chat(PROMPT_REVISION.format(texto=b), provider=proveedor, json_mode=True)
        try:
            hallazgos += json.loads(respuesta).get("hallazgos", [])
        except (json.JSONDecodeError, AttributeError):
            hallazgos.append({"texto": respuesta[:200], "tipo": "respuesta no válida", "motivo": "el modelo no devolvió JSON"})
    return hallazgos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proveedor", help="proveedor de config.yaml para la revisión (por defecto, el de config.yaml)")
    ap.add_argument("--sin-llm", action="store_true", help="omite la revisión con el modelo")
    args = ap.parse_args()

    for carpeta in ("md", "anonimizado", "privado"):
        (SALIDAS / carpeta).mkdir(parents=True, exist_ok=True)

    print("A. Convirtiendo documentos a Markdown")
    conversor = MarkItDown()
    convertidos = []
    for doc in sorted(DATA.iterdir()):
        if doc.suffix.lower() in (".docx", ".pdf"):
            md = conversor.convert(str(doc)).text_content
            destino = SALIDAS / "md" / f"{doc.stem}.md"
            destino.write_text(md, encoding="utf-8")
            convertidos.append(destino)
            print(f"   {doc.name} -> {destino.relative_to(BASE)} ({len(md.split())} palabras)")

    print("\nB. Anonimizando con Presidio (se ejecuta en tu equipo)")
    analizador = crear_analizador()
    for md in convertidos:
        texto_anon, tabla, contador = anonimizar(md.read_text(encoding="utf-8"), analizador)
        (SALIDAS / "anonimizado" / md.name).write_text(texto_anon, encoding="utf-8")
        (SALIDAS / "privado" / f"reemplazos_{md.stem}.json").write_text(json.dumps(tabla, ensure_ascii=False, indent=2), encoding="utf-8")
        resumen = ", ".join(f"{ENTIDADES[t]}: {n}" for t, n in contador.most_common()) or "ninguno"
        print(f"   {md.name}: {sum(contador.values())} datos reemplazados ({resumen})")

    if args.sin_llm:
        print("\nListo. Revisa salidas/anonimizado/ antes de seguir al escalón 2.")
        return

    proveedor = args.proveedor or CONFIG["default"]
    print(f"\nC. Revisión de datos que quedaron, con el modelo '{proveedor}'")
    for md in sorted((SALIDAS / "anonimizado").glob("*.md")):
        inicio = time.time()
        hallazgos = revisar_con_llm(md.read_text(encoding="utf-8"), args.proveedor)
        (SALIDAS / "anonimizado" / f"revision_{md.stem}_{proveedor}.json").write_text(
            json.dumps(hallazgos, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"   {md.name}: {len(hallazgos)} posibles datos sin anonimizar ({time.time() - inicio:.0f} s)")
        for h in hallazgos[:8]:
            print(f"     - {h.get('texto', '')!s:<40} {h.get('tipo', '')}")
    print("\nAnoten en la planilla: qué detectó Presidio, qué encontró el modelo y cuáles son falsos positivos.")


if __name__ == "__main__":
    main()
