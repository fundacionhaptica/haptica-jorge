# haptica-jorge — Asistente IA Jorge

> Repo GitHub: `https://github.com/fundacionhaptica/haptica-jorge`
> Ubicación NAS: `/volume1/docker/haptica-jorge/` (solo clon de referencia)
> **Despliegue: Railway** (no en el NAS — tiene `Nixpacks.toml` y `Procfile`)

## Qué es

App Flask que implementa un asistente IA (Jorge) con procesamiento de documentos y chat. Usa Gemini Flash para parsear documentos y PostgreSQL para persistencia.

## Stack

```
app.py              → Flask principal
app_v3_routes.py    → Endpoints v3 (parseo, admin)
parser_v3.py        → Parser IA con Gemini Flash
migrate_v3.py       → Crea tabla reports_v3 en PostgreSQL
admin_v3.html       → Panel de control standalone
load_data.py        → Carga de datos
seed.json           → Datos iniciales
static/             → Assets frontend
```

**Runtime:** Python (ver `runtime.txt`) · **Deploy:** Railway via Nixpacks

## Variables de entorno requeridas

```
GEMINI_API_KEY      # Google Gemini Flash
DATABASE_URL        # PostgreSQL (Railway provee automáticamente)
```

## Deploy en Railway

El despliegue es automático en Railway al hacer push a `main`. Railway detecta el `Nixpacks.toml` y el `Procfile`.

```bash
# Ver logs en Railway CLI
railway logs

# Variables de entorno
railway variables
```

## Reglas críticas

1. **NUNCA commitear `GEMINI_API_KEY`** ni `DATABASE_URL`. Railway las inyecta como variables de entorno.
2. **`chat_jorge_*.txt`** contiene conversaciones reales — no compartir ni indexar.
3. La tabla `reports_v3` se crea con `migrate_v3.py` — ejecutar solo una vez en un PostgreSQL limpio.
4. `admin_v3.html` es un panel standalone que hace requests directos a la API — no tiene auth propia, no exponer públicamente sin protección.

## Cómo trabajar desde el NAS

Este repo está clonado en el NAS solo como referencia. Para desplegarlo en el NAS en lugar de Railway:
1. Crear `docker-compose.yml` con Flask + PostgreSQL
2. Añadir el contenedor a `hruiz-net` si necesita integración con el resto de apps
3. Elegir puerto libre en rango 8300–8999
4. Documentar el CLAUDE.md con el nuevo contexto de despliegue

---
## Ecosistema NAS — Contexto transversal

> Documento maestro del ecosistema: `/volume1/docker/CLAUDE.md` — léelo para el mapa completo.

**Este repo** actualmente se despliega en Railway, no en el NAS. El clon en `/volume1/docker/haptica-jorge/` es de referencia.

### Servicios relacionados en el NAS

| Servicio | Puerto | Descripción |
|---|---|---|
| `vision-router` | ia-net | Capa IA compartida del NAS (también usa Gemini/Moonshot) |
| `happtica-app` | 5010 | App principal Haptica (hruiz-net) |
| `portal-fastapi-1` | 5354 | SSO para apps hruiz |

### Puertos libres si se dockeriza en el NAS: **8300–8999**