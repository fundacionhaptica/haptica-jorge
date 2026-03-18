"""
parser_v3.py — Parser IA para informes de mediación · Fundación Háptica
Usa Gemini Flash 2.0 (gratuito) para extraer campos estructurados.
Tabla destino: reports_v3 (en paralelo con reports, sin tocarlo)
"""
import os
import json
import time
import logging
from typing import Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# ── PROMPT DEL SISTEMA ────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Eres un parser especializado en informes de mediación para personas con sordoceguera de la Fundación Háptica (Zaragoza).
Tu tarea es extraer campos estructurados de mensajes de WhatsApp escritos por mediadores.

CAMPOS A EXTRAER (devuelve SIEMPRE todos, null si no aparece):
- mediador: nombre del mediador (sin "(Mediador)", "(Mediadora)" ni emojis)
- fecha: fecha del informe en formato YYYY-MM-DD (la fecha del TURNO reportado, no la del mensaje WhatsApp)
- turno: "Mañana", "Tarde" o "Noche" (normaliza: "mañanas"→"Mañana", "tardes"→"Tarde")
- pis: número entero de veces que ha hecho pis (null si no menciona)
- caca: número entero (0 si "no" o "cacas no", null si no menciona)
- agua_ml: agua bebida en mililitros como entero (convierte: "1l"/"1 litro"→1000, "1.5 litros"→1500, "500ml"→500, "0.5L"→500)
- sueno_horas: horas de sueño como decimal ("3:25"→3.42, "7h30m"→7.5, null si no menciona)
- estiramientos: valor numérico 0-5 de la escala de estiramientos (null si no menciona)

CONDUCTA — distingue siempre entre estos cuatro tipos:
- autoagresiones: número de episodios donde Jorge se hace daño a sí mismo (mordiscos propios, golpes a su cuerpo, cabezazos)
- agresiones_mediador: número de episodios donde agrede al mediador (arañazos, mordiscos al mediador, golpes, tirones de pelo)
- agresiones_terceros: número de episodios de agresión a otras personas que no son el mediador
- aleteos: número de episodios de agitación SIN agresión física (aleteos, gritos, balanceo de agitación, extensión/flexión repetitiva de brazos por nervios)
Si dice "picos de conducta: 0" o "sin incidencias" → todos a 0.
Si dice "picos de conducta: 1" sin especificar tipo → autoagresiones:1, resto 0.

ALIMENTACIÓN — separa por tomas:
- desayuno: contenido (null si no menciona)
- almuerzo: contenido (null si no menciona)
- comida: contenido de la comida principal (null si "con X" sin detalle)
- merienda: contenido (null si no menciona)
- cena: contenido (null si "con X" sin detalle)

- medicacion: lista de medicamentos separados por " / " (incluye dosis si se menciona)
- estado: descripción del estado de ánimo, preserva matices y variantes con "/"
- actividad: lista de actividades realizadas separadas por " / "
- vocabulario: palabras/signos nuevos trabajados, separados por coma (null si no menciona)
- observaciones: logros, notas, observaciones adicionales relevantes

REGLAS CRÍTICAS:
1. La fecha del mensaje WhatsApp [entre corchetes] NO es la fecha del informe. El informe puede referirse al día anterior.
2. Raúl Blasco: "1l", "1 litro" = siempre 1000ml.
3. "Pis=4/caca=0" → pis:4, caca:0.
4. Si dice "Comida: con Elena" sin más detalle → comida:null.
5. Devuelve SOLO JSON válido, sin markdown, sin explicaciones, sin texto extra.

FORMATO DE RESPUESTA (exactamente estos campos):
{"mediador":null,"fecha":null,"turno":null,"pis":null,"caca":null,"agua_ml":null,"sueno_horas":null,"estiramientos":null,"autoagresiones":null,"agresiones_mediador":null,"agresiones_terceros":null,"aleteos":null,"medicacion":null,"estado":null,"desayuno":null,"almuerzo":null,"comida":null,"merienda":null,"cena":null,"actividad":null,"vocabulario":null,"observaciones":null}"""

EMPTY_RESULT = {
    "mediador": None, "fecha": None, "turno": None,
    "pis": None, "caca": None, "agua_ml": None, "sueno_horas": None,
    "estiramientos": None,
    "autoagresiones": None, "agresiones_mediador": None,
    "agresiones_terceros": None, "aleteos": None,
    "medicacion": None, "estado": None,
    "desayuno": None, "almuerzo": None, "comida": None,
    "merienda": None, "cena": None,
    "actividad": None, "vocabulario": None, "observaciones": None,
}


def get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY no configurada en variables de entorno")
    return genai.Client(api_key=api_key)


def parse_message(text: str, client: Optional[genai.Client] = None, retries: int = 3) -> dict:
    """
    Parsea un mensaje de WhatsApp y devuelve un dict con todos los campos.
    Hace hasta `retries` intentos ante errores de API o JSON inválido.
    """
    if not text or len(text.strip()) < 30:
        return {**EMPTY_RESULT}

    if client is None:
        client = get_client()

    last_error = None
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.0,
                    max_output_tokens=1024,
                ),
                contents=text[:3000],  # limitar tokens de entrada
            )
            raw = response.text.strip()

            # Limpiar posibles bloques markdown
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            parsed = json.loads(raw)

            # Asegurar que todos los campos existen
            result = {**EMPTY_RESULT, **parsed}

            # Normalizar tipos numéricos
            for int_field in ["pis", "caca", "agua_ml", "estiramientos",
                               "autoagresiones", "agresiones_mediador",
                               "agresiones_terceros", "aleteos"]:
                v = result.get(int_field)
                if v is not None:
                    try:
                        result[int_field] = int(float(str(v)))
                    except (ValueError, TypeError):
                        result[int_field] = None

            for float_field in ["sueno_horas"]:
                v = result.get(float_field)
                if v is not None:
                    try:
                        result[float_field] = round(float(str(v)), 2)
                    except (ValueError, TypeError):
                        result[float_field] = None

            # Normalizar turno
            turno = result.get("turno") or ""
            turno_map = {
                "mañana": "Mañana", "manana": "Mañana", "mañanas": "Mañana",
                "tarde": "Tarde", "tardes": "Tarde",
                "noche": "Noche", "noches": "Noche",
            }
            result["turno"] = turno_map.get(turno.lower().strip(), turno) if turno else None

            return result

        except json.JSONDecodeError as e:
            last_error = f"JSON inválido (intento {attempt+1}): {e}"
            logger.warning(last_error)
            time.sleep(1)
        except Exception as e:
            last_error = f"Error API Gemini (intento {attempt+1}): {e}"
            logger.warning(last_error)
            time.sleep(2 ** attempt)  # backoff exponencial

    logger.error(f"parse_message falló tras {retries} intentos: {last_error}")
    return {**EMPTY_RESULT, "_parse_error": last_error}


def parse_batch(messages: list[dict], client: Optional[genai.Client] = None,
                delay: float = 0.5, on_progress=None) -> list[dict]:
    """
    Parsea una lista de mensajes con rate limiting.
    Cada item de `messages` debe tener al menos: {'id': ..., 'body': ...}
    `on_progress(done, total)` se llama después de cada parseo si se proporciona.
    """
    if client is None:
        client = get_client()

    results = []
    total = len(messages)

    for i, msg in enumerate(messages):
        body = msg.get("body") or msg.get("body_preview") or ""
        parsed = parse_message(body, client=client)
        parsed["_source_id"] = msg.get("id")
        parsed["_source_date"] = msg.get("date")
        parsed["_source_mediator"] = msg.get("mediator")
        results.append(parsed)

        if on_progress:
            on_progress(i + 1, total)

        if delay > 0 and i < total - 1:
            time.sleep(delay)

    return results
