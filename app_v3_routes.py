"""
app_v3_routes.py — Rutas v3 para añadir a app.py
Pega este contenido al final de app.py (antes del if __name__ == '__main__')

Requiere:
  - parser_v3.py en el mismo directorio
  - Variable de entorno GEMINI_API_KEY
  - Tabla reports_v3 creada (ejecutar migrate_v3.py una vez)
"""

# ── IMPORTS ADICIONALES (añadir al bloque de imports de app.py si no están) ──
# from parser_v3 import parse_message, parse_batch, get_client
# import threading

# ════════════════════════════════════════════════════════════════════════════════
# ENDPOINTS V3
# ════════════════════════════════════════════════════════════════════════════════

from parser_v3 import parse_message as v3_parse_message
from parser_v3 import parse_batch as v3_parse_batch
from parser_v3 import get_client as v3_get_client
import threading

# Estado global del reparseo en background
_reparse_status = {
    "running": False,
    "done": 0,
    "total": 0,
    "errors": 0,
    "started_at": None,
    "finished_at": None,
    "last_error": None,
}


def _upsert_v3(cur, parsed: dict, source_id: int, body_preview: str):
    """Inserta o actualiza un registro en reports_v3."""
    cur.execute("""
        INSERT INTO reports_v3 (
            source_id, date, mediator, turn, seq,
            pis, caca, agua_ml, sueno_horas,
            estiramientos, autoagresiones, agresiones_mediador,
            agresiones_terceros, aleteos,
            medicacion, estado,
            desayuno, almuerzo, comida, merienda, cena,
            actividad, vocabulario, observaciones,
            parse_model, parse_error, body_preview, updated_at
        ) VALUES (
            %(source_id)s, %(fecha)s, %(mediador)s, %(turno)s, 1,
            %(pis)s, %(caca)s, %(agua_ml)s, %(sueno_horas)s,
            %(estiramientos)s, %(autoagresiones)s, %(agresiones_mediador)s,
            %(agresiones_terceros)s, %(aleteos)s,
            %(medicacion)s, %(estado)s,
            %(desayuno)s, %(almuerzo)s, %(comida)s, %(merienda)s, %(cena)s,
            %(actividad)s, %(vocabulario)s, %(observaciones)s,
            'gemini-2.0-flash', %(parse_error)s, %(body_preview)s, NOW()
        )
        ON CONFLICT (date, mediator, turn, seq)
        DO UPDATE SET
            pis = EXCLUDED.pis,
            caca = EXCLUDED.caca,
            agua_ml = EXCLUDED.agua_ml,
            sueno_horas = EXCLUDED.sueno_horas,
            estiramientos = EXCLUDED.estiramientos,
            autoagresiones = EXCLUDED.autoagresiones,
            agresiones_mediador = EXCLUDED.agresiones_mediador,
            agresiones_terceros = EXCLUDED.agresiones_terceros,
            aleteos = EXCLUDED.aleteos,
            medicacion = EXCLUDED.medicacion,
            estado = EXCLUDED.estado,
            desayuno = EXCLUDED.desayuno,
            almuerzo = EXCLUDED.almuerzo,
            comida = EXCLUDED.comida,
            merienda = EXCLUDED.merienda,
            cena = EXCLUDED.cena,
            actividad = EXCLUDED.actividad,
            vocabulario = EXCLUDED.vocabulario,
            observaciones = EXCLUDED.observaciones,
            parse_error = EXCLUDED.parse_error,
            updated_at = NOW()
    """, {
        **parsed,
        "source_id": source_id,
        "body_preview": body_preview[:400] if body_preview else None,
        "parse_error": parsed.get("_parse_error"),
        # Fallback de fecha/mediador desde reports si Gemini no los extrae
        "fecha": parsed.get("fecha") or parsed.get("_source_date"),
        "mediador": parsed.get("mediador") or parsed.get("_source_mediator"),
    })


# ── GET /api/v3/reports ───────────────────────────────────────────────────────
@app.route("/api/v3/reports")
def v3_reports():
    """Lista paginada de informes v3 con filtros."""
    require_auth()
    page     = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    mediator = request.args.get("mediator")
    turn     = request.args.get("turn")
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")

    where, params = ["1=1"], []
    if mediator:
        where.append("mediator ILIKE %s"); params.append(f"%{mediator}%")
    if turn:
        where.append("turn = %s"); params.append(turn)
    if date_from:
        where.append("date >= %s"); params.append(date_from)
    if date_to:
        where.append("date <= %s"); params.append(date_to)

    where_sql = " AND ".join(where)
    offset = (page - 1) * per_page

    db = get_db()
    cur = db.cursor()
    cur.execute(f"SELECT COUNT(*) FROM reports_v3 WHERE {where_sql}", params)
    total = cur.fetchone()["count"]

    cur.execute(f"""
        SELECT * FROM reports_v3
        WHERE {where_sql}
        ORDER BY date DESC, mediator
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])
    rows = [dict(r) for r in cur.fetchall()]

    # Serializar fechas
    for r in rows:
        if r.get("date"):
            r["date"] = r["date"].isoformat()
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
        if r.get("updated_at"):
            r["updated_at"] = r["updated_at"].isoformat()

    return jsonify({"total": total, "page": page, "per_page": per_page, "data": rows})


# ── POST /api/v3/parse-one ────────────────────────────────────────────────────
@app.route("/api/v3/parse-one", methods=["POST"])
def v3_parse_one():
    """
    Parsea un mensaje individual con Gemini y lo guarda en reports_v3.
    Body JSON: { "text": "...", "source_id": 123 }  (source_id opcional)
    """
    require_auth()
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    source_id = data.get("source_id")

    if not text:
        return jsonify({"error": "Campo 'text' requerido"}), 400

    try:
        client = v3_get_client()
        parsed = v3_parse_message(text, client=client)
    except ValueError as e:
        return jsonify({"error": str(e)}), 503

    db = get_db()
    cur = db.cursor()
    try:
        _upsert_v3(cur, parsed, source_id, text)
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Error BD: {e}"}), 500

    return jsonify({"ok": True, "parsed": parsed})


# ── POST /api/v3/reparse-all ──────────────────────────────────────────────────
@app.route("/api/v3/reparse-all", methods=["POST"])
def v3_reparse_all():
    """
    Lanza el reparseo de TODOS los body_preview de reports en background.
    Llama a Gemini para cada uno y guarda en reports_v3.
    Devuelve inmediatamente; usa /api/v3/reparse-status para seguir el progreso.
    """
    require_auth()

    if _reparse_status["running"]:
        return jsonify({"error": "Ya hay un reparseo en curso", "status": _reparse_status}), 409

    limit = int(request.get_json().get("limit", 0) if request.get_json() else 0)

    def run_reparse():
        _reparse_status.update({
            "running": True, "done": 0, "errors": 0,
            "started_at": __import__("datetime").datetime.now().isoformat(),
            "finished_at": None, "last_error": None,
        })

        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)

        try:
            cur = conn.cursor()
            query = "SELECT id, date, mediator, turn, body_preview FROM reports WHERE body_preview IS NOT NULL AND body_preview != ''"
            if limit > 0:
                query += f" LIMIT {limit}"
            cur.execute(query)
            messages = [dict(r) for r in cur.fetchall()]
            _reparse_status["total"] = len(messages)

            client = v3_get_client()

            for i, msg in enumerate(messages):
                try:
                    body = msg.get("body_preview") or ""
                    parsed = v3_parse_message(body, client=client)
                    parsed["_source_date"] = msg["date"].isoformat() if msg.get("date") else None
                    parsed["_source_mediator"] = msg.get("mediator")

                    wcur = conn.cursor()
                    _upsert_v3(wcur, parsed, msg["id"], body)
                    conn.commit()

                    if parsed.get("_parse_error"):
                        _reparse_status["errors"] += 1
                        _reparse_status["last_error"] = parsed["_parse_error"]

                except Exception as e:
                    conn.rollback()
                    _reparse_status["errors"] += 1
                    _reparse_status["last_error"] = str(e)

                _reparse_status["done"] = i + 1
                __import__("time").sleep(0.6)  # ~100 req/min, bajo el límite gratuito de Gemini

        except Exception as e:
            _reparse_status["last_error"] = str(e)
        finally:
            conn.close()
            _reparse_status["running"] = False
            _reparse_status["finished_at"] = __import__("datetime").datetime.now().isoformat()

    thread = threading.Thread(target=run_reparse, daemon=True)
    thread.start()

    return jsonify({"ok": True, "message": "Reparseo iniciado en background", "status": _reparse_status})


# ── GET /api/v3/reparse-status ────────────────────────────────────────────────
@app.route("/api/v3/reparse-status")
def v3_reparse_status():
    """Devuelve el estado actual del reparseo en background."""
    require_auth()
    pct = 0
    if _reparse_status["total"] > 0:
        pct = round(_reparse_status["done"] / _reparse_status["total"] * 100, 1)
    return jsonify({**_reparse_status, "percent": pct})


# ── GET /api/v3/stats ─────────────────────────────────────────────────────────
@app.route("/api/v3/stats")
def v3_stats():
    """Estadísticas básicas de reports_v3."""
    require_auth()
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN parse_error IS NULL THEN 1 END) as ok,
            COUNT(CASE WHEN parse_error IS NOT NULL THEN 1 END) as errors,
            MIN(date) as date_min,
            MAX(date) as date_max,
            COUNT(DISTINCT mediator) as mediators,
            ROUND(AVG(agua_ml)) as avg_agua_ml,
            ROUND(AVG(pis), 1) as avg_pis,
            SUM(autoagresiones) as total_autoagresiones,
            SUM(agresiones_mediador) as total_agresiones_mediador,
            SUM(aleteos) as total_aleteos
        FROM reports_v3
    """)
    row = dict(cur.fetchone())
    for k in ["date_min", "date_max"]:
        if row.get(k):
            row[k] = row[k].isoformat()

    return jsonify(row)


# ── GET /api/v3/conducta ──────────────────────────────────────────────────────
@app.route("/api/v3/conducta")
def v3_conducta():
    """Evolución mensual de los 4 tipos de conducta."""
    require_auth()
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT
            TO_CHAR(date, 'YYYY-MM') as month,
            SUM(autoagresiones)      as autoagresiones,
            SUM(agresiones_mediador) as agresiones_mediador,
            SUM(agresiones_terceros) as agresiones_terceros,
            SUM(aleteos)             as aleteos,
            COUNT(*)                 as informes
        FROM reports_v3
        WHERE date IS NOT NULL
        GROUP BY month
        ORDER BY month
    """)
    return jsonify([dict(r) for r in cur.fetchall()])


# ── GET /api/v3/alimentacion ──────────────────────────────────────────────────
@app.route("/api/v3/alimentacion")
def v3_alimentacion():
    """Informes con desglose de alimentación por toma."""
    require_auth()
    mediator = request.args.get("mediator")
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")

    where, params = ["(desayuno IS NOT NULL OR almuerzo IS NOT NULL OR comida IS NOT NULL OR merienda IS NOT NULL OR cena IS NOT NULL)"], []
    if mediator:
        where.append("mediator ILIKE %s"); params.append(f"%{mediator}%")
    if date_from:
        where.append("date >= %s"); params.append(date_from)
    if date_to:
        where.append("date <= %s"); params.append(date_to)

    db = get_db()
    cur = db.cursor()
    cur.execute(f"""
        SELECT date, mediator, turn, desayuno, almuerzo, comida, merienda, cena
        FROM reports_v3
        WHERE {" AND ".join(where)}
        ORDER BY date DESC
        LIMIT 200
    """, params)
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        if r.get("date"):
            r["date"] = r["date"].isoformat()
    return jsonify(rows)
