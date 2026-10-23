# Escalón 4 · Desafío: el mismo análisis en un chat gratuito

**Tiempo:** unos 15 minutos, para los equipos que terminaron el escalón 3.
**Objetivo:** comparar la matriz del escalón 3 con lo que entrega un chat gratuito (Claude.ai, ChatGPT o Le Chat de Mistral) y decidir cuál usarían en Andina Pagos y con qué controles.

## Antes de pegar nada

Respondan en la planilla, hoja **E4 Desafío**:

1. ¿Qué archivo van a pegar en el chat? Usen solo `salidas/anonimizado/politica_seguridad_andina_pagos.md`, nunca el de `salidas/md/` ni la carpeta `salidas/privado/`.
2. ¿Qué dicen los términos del plan gratuito sobre el uso de sus conversaciones para entrenar modelos?
3. ¿En qué alcance de la Matriz de Alcance (Clase 4) queda este uso?

## Prompt A · Matriz de brechas en el chat

Adjunten o peguen `salidas/anonimizado/politica_seguridad_andina_pagos.md` y `data/reglamento_ley29733_extracto.md` y usen este prompt:

```
Eres auditor de cumplimiento de protección de datos personales en Perú.
Te adjunto (1) la política de seguridad anonimizada de una fintech y (2) un extracto del
Reglamento de la Ley 29733 (artículos 34 a 58).

Haz una tabla con una fila por requisito de los artículos 34, 35, 37, 46, 47, 49, 50, 51 y 52.
Columnas: artículo, requisito resumido, estado (Cumple / Parcial / No cumple), frase textual
de la política que lo respalda, brecha y recomendación en una oración.
Usa solo el contenido de los documentos adjuntos. Si la política no menciona algo, dilo.
```

## Prompt B · Mapeo a ISO/IEC 27001:2022

```
Para los artículos 46 a 52 del extracto del reglamento adjunto, haz una tabla con:
artículo o ítem, requisito resumido, controles de ISO/IEC 27001:2022 que ayudan a cumplirlo
(número y nombre), porcentaje estimado de cobertura del requisito por esos controles y la
brecha que queda entre el estándar y el reglamento.
```

## Comparen y anoten en la planilla

- ¿Qué brechas encontró el chat que no encontró su matriz del escalón 3? ¿Y al revés?
- Revisen 3 frases de "evidencia" del chat: ¿existen textualmente en la política?
- ¿El chat inventó plazos, artículos o controles? (riesgo LLM07 Desinformación)
- Si tuvieran que presentar esta matriz a la Gerencia Legal de Andina Pagos, ¿cuál usarían y qué revisión humana agregarían?
