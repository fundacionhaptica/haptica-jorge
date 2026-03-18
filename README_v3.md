# Integración v3 en Railway — Instrucciones paso a paso

## Archivos nuevos
- `parser_v3.py` — parser IA con Gemini Flash
- `migrate_v3.py` — crea la tabla `reports_v3` en PostgreSQL
- `app_v3_routes.py` — endpoints nuevos (pegar al final de `app.py`)
- `admin_v3.html` — panel de control standalone (abrir en navegador)

---

## Paso 1 — Obtener API key de Gemini (gratis)

1. Ir a https://aistudio.google.com/apikey
2. Crear proyecto → "Get API key" → copiar la key
3. En Railway → tu proyecto → Variables → añadir:
   ```
   GEMINI_API_KEY = AIza...tu_key...
   ```

---

## Paso 2 — Añadir dependencia

En `requirements.txt` añadir:
```
google-genai>=0.8.0
```

---

## Paso 3 — Crear tabla reports_v3

**Opción A — desde Railway CLI:**
```bash
railway run python migrate_v3.py
```

**Opción B — desde el endpoint (tras el deploy):**
```
POST /api/admin/migrate-v3
```
(añadir este endpoint también a app.py si prefieres hacerlo desde el navegador)

---

## Paso 4 — Añadir rutas a app.py

Al final de `app.py`, justo antes de `if __name__ == '__main__':`, pegar:

```python
# ── V3 ROUTES ────────────────────────────────────────────────────────────────
import threading
from parser_v3 import parse_message as v3_parse_message
from parser_v3 import get_client as v3_get_client

_reparse_status = {
    "running": False, "done": 0, "total": 0, "errors": 0,
    "started_at": None, "finished_at": None, "last_error": None,
}

# [pegar aquí el contenido de app_v3_routes.py eliminando los comentarios de imports del principio]
```

---

## Paso 5 — Añadir endpoint de migración en app.py (opcional)

```python
@app.route("/api/admin/migrate-v3", methods=["GET", "POST"])
def migrate_v3_endpoint():
    require_auth()
    from migrate_v3 import migrate
    migrate()
    return jsonify({"ok": True, "message": "Tabla reports_v3 creada"})
```

---

## Paso 6 — Deploy y reparseo

1. Push a `main` → Railway hace deploy automático
2. Abrir `admin_v3.html` en el navegador
3. Introducir URL de Railway + contraseña → Conectar
4. Sección "Reparseo masivo":
   - Límite = 0 (todos los registros)
   - Pulsar "Iniciar reparseo"
   - La barra de progreso se actualiza cada 3 segundos
   - ~47 minutos para 4.725 informes a 0.6s/informe

---

## Nuevos endpoints disponibles tras el deploy

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/v3/reports` | GET | Listado paginado con filtros |
| `/api/v3/parse-one` | POST | Parsear un mensaje y guardarlo |
| `/api/v3/reparse-all` | POST | Lanzar reparseo masivo en background |
| `/api/v3/reparse-status` | GET | Estado del reparseo en curso |
| `/api/v3/stats` | GET | Estadísticas de reports_v3 |
| `/api/v3/conducta` | GET | Evolución mensual de 4 tipos de conducta |
| `/api/v3/alimentacion` | GET | Informes con desglose por toma |

---

## Límites gratuitos de Gemini Flash

- **1.500 requests/día** en el tier gratuito
- **15 requests/minuto**
- El reparseo usa 0.6s de delay = ~100 req/min → bien bajo el límite
- Para 4.725 informes: ~4 días si hay límite diario, o ~47 min si no lo hay

Si quieres acelerar, cambia el `delay` en `run_reparse()` de 0.6 a 0.2 (más rápido pero puede chocar con el límite de req/min).

---

## Columnas nuevas en reports_v3 vs reports

| Campo v3 | Equivalente v1 | Descripción |
|---|---|---|
| `autoagresiones` | parte de `conducta` | Jorge se hace daño a sí mismo |
| `agresiones_mediador` | parte de `conducta` | Agresiones al mediador |
| `agresiones_terceros` | — | Agresiones a terceros |
| `aleteos` | — | Agitación sin agresión física |
| `desayuno` | parte de `comidas` | Toma desayuno |
| `almuerzo` | parte de `comidas` | Toma almuerzo |
| `comida` | parte de `comidas` | Comida principal |
| `merienda` | parte de `comidas` | Toma merienda |
| `cena` | parte de `comidas` | Toma cena |
| `vocabulario` | `vocab` (jsonb) | Palabras/signos nuevos (texto) |
| `agua_ml` | `agua` | Agua en ml siempre (no "1l") |
| `sueno_horas` | en `notas` | Horas de sueño como decimal |
| `parse_model` | — | Modelo IA usado |
| `parse_error` | — | Error de parseo si ocurrió |
