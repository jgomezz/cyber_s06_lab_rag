"""Cliente único para todos los proveedores del curso (kit común).

    from llm import chat
    print(chat("Resume la política en 3 puntos", provider="mistral"))

El proveedor y el modelo se definen en config.yaml; las claves, en .env.
"""
import json
import os
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")
os.environ.setdefault("LITELLM_LOG", "ERROR")

import litellm  # noqa: E402  (se importa después de cargar .env)

litellm.suppress_debug_info = True

with open(BASE / "config.yaml", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)


def provider_settings(provider: str | None = None) -> dict:
    """Devuelve modelo, URL y clave del proveedor pedido (o del proveedor por defecto)."""
    name = provider or CONFIG["default"]
    if name not in CONFIG["providers"]:
        raise ValueError(f"Proveedor '{name}' no existe en config.yaml. Opciones: {', '.join(CONFIG['providers'])}")
    p = CONFIG["providers"][name]
    settings = {"model": p["model"]}
    if p.get("api_base"):
        settings["api_base"] = p["api_base"]
    if p.get("api_key_env"):
        key = os.getenv(p["api_key_env"], "").strip()
        if not key:
            raise RuntimeError(f"Falta {p['api_key_env']} en el archivo .env (proveedor '{name}').")
        settings["api_key"] = key
    return settings


def chat(prompt: str, provider: str | None = None, system: str | None = None,
         json_mode: bool = False, temperature: float = 0.2, timeout: int = 180) -> str:
    """Envía un mensaje y devuelve el texto de la respuesta."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    kwargs = provider_settings(provider)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = litellm.completion(messages=messages, temperature=temperature, timeout=timeout, num_retries=3, **kwargs)
    except litellm.BadRequestError as e:
        # Algunos proveedores no aceptan response_format: se reintenta sin él (el prompt ya pide JSON)
        if not json_mode or "response_format" not in str(e).lower() and "json" not in str(e).lower():
            raise
        kwargs.pop("response_format", None)
        resp = litellm.completion(messages=messages, temperature=temperature, timeout=timeout, **kwargs)
    return resp.choices[0].message.content or ""


def extraer_json(texto: str):
    """Convierte la respuesta en un objeto JSON aunque venga con ```json ... ``` o texto alrededor."""
    texto = texto.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", texto, flags=re.S)
    if m:
        texto = m.group(1).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        inicio = min([i for i in (texto.find("{"), texto.find("[")) if i >= 0], default=-1)
        if inicio < 0:
            raise
        fin = max(texto.rfind("}"), texto.rfind("]"))
        return json.loads(texto[inicio:fin + 1])


def chat_json(prompt: str, esquema, provider: str | None = None, system: str | None = None, intentos: int = 2):
    """Pide un JSON y lo valida con un modelo de Pydantic. Si no es válido, reintenta explicando el error.

    Devuelve (objeto_validado, intentos_usados). Si todos fallan, lanza ValueError con el último error.
    """
    from pydantic import ValidationError
    error = ""
    for intento in range(1, intentos + 1):
        texto = chat(prompt, provider=provider, system=system, json_mode=True)
        try:
            return esquema.model_validate(extraer_json(texto)), intento
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            error = str(e).splitlines()[0]
            prompt += f"\n\nTu respuesta anterior no era válida ({error}). Responde solo el JSON con los campos y valores pedidos."
    raise ValueError(f"El modelo no entregó un JSON válido: {error}")


def chat_herramientas(messages: list, tools: list, provider: str | None = None, temperature: float = 0.0, timeout: int = 180):
    """Una vuelta de tool calling: devuelve el mensaje del modelo (puede traer tool_calls)."""
    resp = litellm.completion(messages=messages, tools=tools, tool_choice="auto", temperature=temperature,
                              timeout=timeout, **provider_settings(provider))
    return resp.choices[0].message


def smol_model(provider: str | None = None):
    """Modelo para agentes de smolagents (clases 15 a 17) con la misma configuración."""
    from smolagents import LiteLLMModel
    s = provider_settings(provider)
    return LiteLLMModel(model_id=s["model"], api_base=s.get("api_base"), api_key=s.get("api_key"), temperature=0.0)


def embed_model():
    """Modelo de embeddings de LlamaIndex según config.yaml (sección embeddings)."""
    cfg = CONFIG["embeddings"]
    if cfg["provider"] == "ollama":
        from llama_index.embeddings.ollama import OllamaEmbedding
        return OllamaEmbedding(model_name=cfg["ollama_model"], base_url=cfg["ollama_base"])
    if cfg["provider"] == "mistral":
        from llama_index.embeddings.mistralai import MistralAIEmbedding
        key = os.getenv("MISTRAL_API_KEY", "").strip()
        if not key:
            raise RuntimeError("Falta MISTRAL_API_KEY en .env para usar embeddings de Mistral.")
        return MistralAIEmbedding(model_name=cfg["mistral_model"], api_key=key)
    raise ValueError("embeddings.provider debe ser 'ollama' o 'mistral' en config.yaml")
