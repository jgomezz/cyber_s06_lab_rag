# Clase 6 · Laboratorio: políticas y análisis normativo con IA

**Caso:** Andina Pagos S.A., fintech de pagos ficticia de Lima, quiere saber si su Política de Seguridad de la Información cumple el Reglamento de la Ley 29733 de protección de datos personales (DS 016-2024-JUS), sin exponer información interna.

**Lo que van a construir:** un flujo que convierte y anonimiza las políticas en su equipo, consulta el reglamento con RAG y genera una matriz de brechas en Excel, comparando dos modelos en la nube. La anonimización ocurre siempre en su equipo, antes de que algo salga.

**Tiempo total:** unos 85 minutos, en equipos de tres (tiempos referenciales).

| Escalón | Qué hacen | Tiempo | Tecnología |
|---|---|---|---|
| 1 · Obligatorio | Convertir y anonimizar las políticas | ~15 min | markitdown, Presidio (local) y revisión con Ollama Cloud |
| 2 · Objetivo de la clase | Preguntar al reglamento con RAG | ~15 min | LlamaIndex, Chroma, embeddings |
| 3 · Comparar modelos | Matriz de brechas con dos modelos | ~30 min | Salida estructurada con Pydantic |
| 4 · Desafío (equipos rápidos) | El mismo análisis en un chat gratuito | ~15 min | Claude.ai, ChatGPT o Le Chat |

Al final, todos completan la hoja **Riesgos OWASP** de la planilla (~10 min).

---

## Roles del equipo (rotan en cada escalón)

- **Piloto:** ejecuta los comandos y comparte pantalla.
- **Navegante:** lee esta guía, anticipa el siguiente paso y detecta errores antes de ejecutar.
- **Analista:** revisa los resultados y completa la planilla `Planilla del lab - Clase 6.xlsx`.

| Escalón | Piloto | Navegante | Analista |
|---|---|---|---|
| 1 | A | B | C |
| 2 | B | C | A |
| 3 | C | A | B |
| 4 y riesgos | A | B | C |

Si el equipo tiene cuatro integrantes, el cuarto es **Revisor de riesgos**: completa la hoja Riesgos OWASP durante todo el lab y entra a la rotación.

Basta con que **un** integrante tenga el ambiente funcionando.

---

## 0. Preparación (si no hicieron la Guía 0, háganla ahora)

Necesitan Python 3.11 o superior y el archivo `.env` con sus claves de **Ollama Cloud** y **Mistral** como mínimo (ver *Guía 0: preparación del ambiente y creación de cuentas*). Ollama instalado en su equipo es **opcional**: solo si tienen 16 GB de RAM o GPU.

Desde esta carpeta:

**Windows (PowerShell)**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m spacy download es_core_news_md
copy .env.example .env      # y peguen sus claves en .env
python check_env.py
```

**macOS / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download es_core_news_md
cp .env.example .env        # y peguen sus claves en .env
python check_env.py
```

`check_env.py` debe mostrar al menos dos proveedores en **OK**. Para cambiar de modelo no se toca código: se usa `--proveedor` o se edita `config.yaml`.

---

## Escalón 1 · Convertir y anonimizar (obligatorio, ~15 min)

**Pregunta:** ¿qué datos de Andina Pagos saldrían de la empresa si enviáramos estas políticas a una API gratuita?

```bash
python escalon_1_anonimizar.py
```

El script hace tres cosas, todas en su equipo salvo que cambien el proveedor:

1. **Convierte** `data/politica_seguridad_andina_pagos.docx` y `data/procedimiento_accesos_respaldos.pdf` a Markdown (`salidas/md/`).
2. **Anonimiza** con Presidio nombres, correos, teléfonos, DNI, IP y el nombre de la empresa, y los reemplaza por etiquetas como `<PERSONA_1>` (`salidas/anonimizado/`). La tabla para revertir los reemplazos queda en `salidas/privado/` y **nunca se comparte**.
3. **Revisa** con Ollama Cloud, sobre el texto ya anonimizado, si quedó algún dato identificable (`salidas/anonimizado/revision_*.json`).

**Qué hacer con el resultado**

- Abran `salidas/anonimizado/procedimiento_accesos_respaldos.md` y busquen datos que se hayan escapado.
- Busquen **falsos positivos**: palabras que Presidio reemplazó sin ser datos personales. Agréguenlas a `anonimizacion.permitidos` en `config.yaml` y vuelvan a ejecutar.
- Anoten en la hoja **E1 Anonimización**: cuántos datos detectó Presidio, qué encontró el modelo, falsos positivos y falsos negativos.

---

## Escalón 2 · Preguntar al reglamento con RAG (~15 min)

**Pregunta:** ¿puede un modelo responder sobre el reglamento sin inventar, citando el artículo?

```bash
python escalon_2_rag.py
```

La primera vez crea el índice vectorial del reglamento en `salidas/chroma/` (un fragmento por artículo). Luego responde 6 preguntas y guarda las respuestas en `salidas/respuestas_rag_<proveedor>.md`.

Repitan con un modelo en la nube y comparen:

```bash
python escalon_2_rag.py --proveedor mistral
python escalon_2_rag.py --pregunta "¿Qué debe contener el documento de seguridad?"
```

**Qué revisar**

- ¿Cada cita `[Art. N]` corresponde de verdad a lo que dice ese artículo en `data/reglamento_ley29733_extracto.md`?
- La pregunta 6 (monto de la multa) **no** está en el extracto: ¿el modelo lo reconoce o inventa una cifra?
- Anoten en la hoja **E2 RAG** si cada respuesta es correcta, si la cita es correcta y el tiempo.

> Los embeddings usan Mistral por defecto. Si tienen Ollama local (opcional), pueden cambiar `embeddings.provider` a `ollama`; el índice se reconstruye solo.

---

## Escalón 3 · Matriz de brechas con dos modelos (~30 min)

**Pregunta:** ¿cumple la política de Andina Pagos los 16 requisitos de `data/requisitos_reglamento.json`? ¿Responden igual dos modelos distintos?

```bash
python escalon_3_brechas.py --proveedor ollama_cloud
python escalon_3_brechas.py --proveedor mistral
python escalon_3_brechas.py --comparar salidas/matriz_brechas_ollama_cloud.xlsx salidas/matriz_brechas_mistral.xlsx
```

Para cada requisito, el script recupera los fragmentos más parecidos de la política anonimizada, pide al modelo un JSON con estado, evidencia, brecha y recomendación, lo valida con Pydantic y comprueba si la evidencia citada **existe textualmente** en la política.

**Qué revisar**

- `salidas/comparacion_modelos.xlsx`: los requisitos donde los modelos no coinciden. Lean la política y decidan quién tiene razón.
- La columna **¿Evidencia verificada?**: un "No" indica que el modelo citó algo que no está en la política.
- Anoten en la hoja **E3 Comparación** el tiempo, los resultados y su juicio de calidad de cada modelo.

> Pueden probar también `--proveedor nvidia`, `groq` u `ollama_cloud`.

---

## Escalón 4 · Desafío para equipos rápidos (~15 min)

Sigan `escalon_4_desafio.md`: el mismo análisis en un chat gratuito, con los prompts de la clase anterior adaptados, y una comparación con su matriz.

---

## Cierre del lab: riesgos OWASP (~10 min, todos los equipos)

Completen la hoja **Riesgos OWASP** de la planilla para lo que construyeron hoy. Pongan especial atención a:

- **LLM02 Divulgación de información sensible:** ¿qué pasa si la anonimización falla y el texto llega a una API gratuita que entrena con sus datos?
- **LLM07 Desinformación:** ¿qué pasa si la Gerencia Legal confía en una brecha o una cita inventada?

---

## Para el plenario (3 minutos por equipo)

1. ¿Qué dato se les escapó a la anonimización y cómo lo detectaron?
2. ¿Qué modelo usarían para la matriz de brechas de Andina Pagos y por qué?
3. ¿Cuál es la brecha más importante de la política frente al reglamento?

---

## Estructura de la carpeta

```
lab/
├── README.md                       # esta guía
├── config.yaml                     # proveedores, embeddings y anonimización
├── .env.example                    # plantilla para sus claves (copiar como .env)
├── llm.py                          # cliente único de modelos (kit común)
├── check_env.py                    # prueba de proveedores
├── rag.py                          # funciones de RAG compartidas
├── escalon_1_anonimizar.py
├── escalon_2_rag.py
├── escalon_3_brechas.py
├── escalon_4_desafio.md
├── data/
│   ├── politica_seguridad_andina_pagos.docx      # ficticia
│   ├── procedimiento_accesos_respaldos.pdf       # ficticio
│   ├── reglamento_ley29733_extracto.md           # artículos 34 a 58
│   └── requisitos_reglamento.json                # 16 requisitos a evaluar
└── salidas/                        # se crea al ejecutar
```

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `Can't find model 'es_core_news_md'` | Ejecuten `python -m spacy download es_core_news_md` con el entorno virtual activo. |
| `Connection refused` en Ollama | Abran la aplicación Ollama o ejecuten `ollama serve`. |
| Error de embeddings de Mistral | Revisen `MISTRAL_API_KEY` en `.env`. Si usan Ollama local (opcional): `ollama pull nomic-embed-text` y `embeddings.provider: ollama`. |
| El escalón 3 tarda mucho con Ollama Cloud | El plan gratuito atiende una consulta a la vez: usen `--proveedor groq` para el segundo modelo. |
| `No hay documentos anonimizados` | Ejecuten primero el escalón 1. |
| Error 429 | Límite gratuito por minuto: esperen un minuto o cambien de proveedor. |

**Todos los documentos de Andina Pagos son ficticios.** El reglamento es texto normativo público publicado en el diario oficial El Peruano el 30 de noviembre de 2024.
