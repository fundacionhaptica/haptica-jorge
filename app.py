"""
Fundación HÁPTICA — API de seguimiento de Jorge
Flask + PostgreSQL en Railway
"""
import os, json, hashlib
from functools import wraps
from datetime import datetime

from flask import Flask, request, jsonify, g, send_file
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

from parser import parse_whatsapp

# ── FRONTEND ──────────────────────────────────────────────────────────────────
@app.route('/dashboard')
@app.route('/dashboard/')
def frontend():
    """Sirve el dashboard HTML."""
    return send_file('index.html')

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ── CONFIG ─────────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '')
API_PASSWORD  = os.environ.get('API_PASSWORD', 'haptica2025')

# ── DB ─────────────────────────────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

def init_db():
    """Crea las tablas si no existen."""
    db = psycopg2.connect(DATABASE_URL)
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id            SERIAL PRIMARY KEY,
            date          DATE NOT NULL,
            mediator      TEXT NOT NULL,
            turn          TEXT,
            mood          TEXT,
            conducta      INTEGER DEFAULT 0,
            estiramientos INTEGER DEFAULT 0,
            agua          INTEGER,
            pis           INTEGER,
            banyo         TEXT,
            estado        TEXT,
            comunicacion  TEXT,
            actividades   TEXT,
            comidas       TEXT,
            medicacion    TEXT,
            notas         TEXT,
            vocab         JSONB DEFAULT '[]',
            formato       TEXT,
            body_preview  TEXT,
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(date, mediator, turn)
        );

        CREATE TABLE IF NOT EXISTS upload_log (
            id          SERIAL PRIMARY KEY,
            uploaded_at TIMESTAMPTZ DEFAULT NOW(),
            total_in_file  INTEGER,
            new_inserted   INTEGER,
            duplicates     INTEGER,
            date_from   DATE,
            date_to     DATE,
            uploaded_by TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_reports_date     ON reports(date);
        CREATE INDEX IF NOT EXISTS idx_reports_mediator ON reports(mediator);
        CREATE INDEX IF NOT EXISTS idx_reports_mood     ON reports(mood);
    """)
    db.commit()
    cur.close()
    db.close()
    print("DB inicializada ✓")

# ── AUTH ───────────────────────────────────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        pwd = request.headers.get('X-Password') or request.args.get('pwd')
        if pwd != API_PASSWORD:
            return jsonify({'error': 'No autorizado'}), 401
        return f(*args, **kwargs)
    return decorated

# ── HEALTH ─────────────────────────────────────────────────────────────────────
@app.route('/')
def health():
    return jsonify({'status': 'ok', 'service': 'HÁPTICA Jorge API', 'version': '1.0'})

@app.route('/api/ping')
@require_auth
def ping():
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT COUNT(*) as n FROM reports')
    n = cur.fetchone()['n']
    return jsonify({'status': 'ok', 'total_reports': n})

# ── UPLOAD ─────────────────────────────────────────────────────────────────────
@app.route('/api/upload', methods=['POST'])
@require_auth
def upload():
    """Recibe un .txt de WhatsApp, parsea e inserta solo los informes nuevos."""
    if 'file' not in request.files:
        return jsonify({'error': 'No se recibió archivo'}), 400

    file = request.files['file']
    try:
        text = file.read().decode('utf-8', errors='replace')
    except Exception as e:
        return jsonify({'error': f'Error leyendo archivo: {e}'}), 400

    # Parsear
    reports = parse_whatsapp(text)
    if not reports:
        return jsonify({'error': 'No se encontraron informes en el archivo'}), 400

    # Insertar solo nuevos
    db = get_db()
    cur = db.cursor()

    inserted = 0
    duplicates = 0

    for r in reports:
        try:
            cur.execute("""
                INSERT INTO reports
                  (date, mediator, turn, mood, conducta, estiramientos, agua, pis,
                   banyo, estado, comunicacion, actividades, comidas, medicacion,
                   notas, vocab, formato, body_preview)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (date, mediator, turn) DO NOTHING
            """, (
                r['date'], r['mediator'], r['turn'], r['mood'],
                r['conducta'], r['estiramientos'], r['agua'], r['pis'],
                r['banyo'], r['estado'], r['comunicacion'], r['actividades'],
                r['comidas'], r['medicacion'], r['notas'],
                json.dumps(r['vocab'], ensure_ascii=False),
                r['formato'], r['body_preview']
            ))
            if cur.rowcount > 0:
                inserted += 1
            else:
                duplicates += 1
        except Exception:
            db.rollback()
            continue

    # Log del upload
    dates = sorted(r['date'] for r in reports)
    cur.execute("""
        INSERT INTO upload_log (total_in_file, new_inserted, duplicates, date_from, date_to, uploaded_by)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (len(reports), inserted, duplicates, dates[0], dates[-1],
          request.headers.get('X-User', 'anónimo')))

    db.commit()
    cur.close()

    return jsonify({
        'ok': True,
        'total_in_file': len(reports),
        'new_inserted':  inserted,
        'duplicates':    duplicates,
        'date_from':     dates[0],
        'date_to':       dates[-1],
    })

# ── WEBHOOK WHATSAPP BUSINESS API (futuro) ─────────────────────────────────────
@app.route('/api/webhook/whatsapp', methods=['GET', 'POST'])
def whatsapp_webhook():
    """
    Webhook para WhatsApp Business API.
    GET: verificación de Meta (challenge)
    POST: recepción de mensajes en tiempo real
    """
    if request.method == 'GET':
        # Verificación de Meta
        verify_token = os.environ.get('WA_VERIFY_TOKEN', 'haptica_verify')
        mode      = request.args.get('hub.mode')
        token     = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == verify_token:
            return challenge, 200
        return 'Forbidden', 403

    # POST: mensaje entrante
    data = request.get_json(silent=True)
    if not data:
        return 'ok', 200

    try:
        entries = data.get('entry', [])
        for entry in entries:
            for change in entry.get('changes', []):
                messages = change.get('value', {}).get('messages', [])
                for msg in messages:
                    if msg.get('type') == 'text':
                        body   = msg['text']['body']
                        sender = msg.get('from', 'desconocido')
                        ts     = msg.get('timestamp', '')
                        if ts:
                            date_str = datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d')
                        else:
                            date_str = datetime.now().strftime('%Y-%m-%d')
                        # Parsear como informe individual
                        from parser import parse_report, is_mediator
                        if len(body) >= 80:
                            report = parse_report(date_str, sender, body)
                            db = get_db()
                            cur = db.cursor()
                            cur.execute("""
                                INSERT INTO reports
                                  (date, mediator, turn, mood, conducta, estiramientos, agua, pis,
                                   banyo, estado, comunicacion, actividades, comidas, medicacion,
                                   notas, vocab, formato, body_preview)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                ON CONFLICT (date, mediator, turn) DO NOTHING
                            """, (
                                report['date'], report['mediator'], report['turn'], report['mood'],
                                report['conducta'], report['estiramientos'], report['agua'], report['pis'],
                                report['banyo'], report['estado'], report['comunicacion'], report['actividades'],
                                report['comidas'], report['medicacion'], report['notas'],
                                json.dumps(report['vocab'], ensure_ascii=False),
                                report['formato'], report['body_preview']
                            ))
                            db.commit()
    except Exception as e:
        print(f"Webhook error: {e}")

    return 'ok', 200

# ── DATOS ──────────────────────────────────────────────────────────────────────
@app.route('/api/reports')
@require_auth
def get_reports():
    """Devuelve todos los informes con filtros opcionales."""
    db = get_db()
    cur = db.cursor()

    where = ['1=1']
    params = []

    if request.args.get('from'):
        where.append('date >= %s'); params.append(request.args['from'])
    if request.args.get('to'):
        where.append('date <= %s'); params.append(request.args['to'])
    if request.args.get('mediator'):
        where.append('mediator = %s'); params.append(request.args['mediator'])
    if request.args.get('turn'):
        where.append('turn = %s'); params.append(request.args['turn'])
    if request.args.get('mood'):
        where.append('mood = %s'); params.append(request.args['mood'])
    if request.args.get('conducta') == '1':
        where.append('conducta > 0')
    if request.args.get('conducta') == '0':
        where.append('conducta = 0')

    sql = f"""
        SELECT id, date, mediator, turn, mood, conducta, estiramientos,
               agua, pis, estado, comunicacion, actividades, comidas,
               medicacion, notas, vocab, formato, body_preview
        FROM reports
        WHERE {' AND '.join(where)}
        ORDER BY date DESC, id DESC
    """
    cur.execute(sql, params)
    rows = cur.fetchall()

    # Serializar
    result = []
    for r in rows:
        d = dict(r)
        d['date'] = d['date'].isoformat() if d['date'] else None
        if isinstance(d['vocab'], str):
            d['vocab'] = json.loads(d['vocab'])
        result.append(d)

    return jsonify({'reports': result, 'total': len(result)})

@app.route('/api/stats')
@require_auth
def get_stats():
    """Estadísticas agregadas para el dashboard."""
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT
            COUNT(*)                                          AS total,
            MIN(date)                                         AS date_from,
            MAX(date)                                         AS date_to,
            ROUND(AVG(CASE WHEN agua < 3000 THEN agua END))  AS avg_agua,
            ROUND(AVG(CASE
                WHEN mood='muy_positivo' THEN 4
                WHEN mood='positivo'     THEN 3
                WHEN mood='neutro'       THEN 2
                WHEN mood='negativo'     THEN 1
                ELSE 2.5 END)::numeric, 2)                   AS avg_mood,
            ROUND(100.0 * SUM(CASE WHEN conducta=0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_sin_picos,
            ROUND(100.0 * SUM(CASE WHEN mood IN ('positivo','muy_positivo') THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_positivo,
            COUNT(DISTINCT mediator)                         AS n_mediators
        FROM reports
    """)
    stats = dict(cur.fetchone())

    # Por mes (últimos 36)
    cur.execute("""
        SELECT
            TO_CHAR(date,'YYYY-MM')                          AS month,
            COUNT(*)                                         AS total,
            ROUND(AVG(CASE
                WHEN mood='muy_positivo' THEN 4 WHEN mood='positivo' THEN 3
                WHEN mood='neutro' THEN 2       WHEN mood='negativo' THEN 1
                ELSE 2.5 END)::numeric,2)                    AS avg_mood,
            ROUND(100.0*SUM(CASE WHEN conducta>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_picos,
            ROUND(AVG(CASE WHEN agua<3000 THEN agua END))    AS avg_agua
        FROM reports
        GROUP BY month
        ORDER BY month DESC
        LIMIT 36
    """)
    monthly = [dict(r) for r in cur.fetchall()]

    # Por mediador
    cur.execute("""
        SELECT
            mediator,
            COUNT(*)   AS total,
            ROUND(100.0*SUM(CASE WHEN conducta>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_picos,
            ROUND(AVG(CASE
                WHEN mood='muy_positivo' THEN 4 WHEN mood='positivo' THEN 3
                WHEN mood='neutro' THEN 2       WHEN mood='negativo' THEN 1
                ELSE 2.5 END)::numeric,2)       AS avg_mood,
            MIN(date)  AS first_date,
            MAX(date)  AS last_date
        FROM reports
        GROUP BY mediator
        ORDER BY total DESC
    """)
    by_med = []
    for r in cur.fetchall():
        d = dict(r)
        d['first_date'] = d['first_date'].isoformat() if d['first_date'] else None
        d['last_date']  = d['last_date'].isoformat()  if d['last_date']  else None
        by_med.append(d)

    # Distribución mood
    cur.execute("SELECT mood, COUNT(*) AS n FROM reports GROUP BY mood ORDER BY n DESC")
    mood_dist = [dict(r) for r in cur.fetchall()]

    # Upload log
    cur.execute("""
        SELECT uploaded_at, total_in_file, new_inserted, duplicates, date_from, date_to, uploaded_by
        FROM upload_log ORDER BY uploaded_at DESC LIMIT 10
    """)
    uploads = []
    for r in cur.fetchall():
        d = dict(r)
        d['uploaded_at'] = d['uploaded_at'].isoformat() if d['uploaded_at'] else None
        d['date_from']   = d['date_from'].isoformat()   if d['date_from']   else None
        d['date_to']     = d['date_to'].isoformat()     if d['date_to']     else None
        uploads.append(d)

    for k in ['date_from','date_to']:
        if stats.get(k): stats[k] = stats[k].isoformat()

    return jsonify({
        'summary':  stats,
        'monthly':  monthly,
        'by_mediator': by_med,
        'mood_dist': mood_dist,
        'upload_log': uploads,
    })

@app.route('/api/mediators')
@require_auth
def get_mediators():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT DISTINCT mediator FROM reports ORDER BY mediator")
    return jsonify({'mediators': [r['mediator'] for r in cur.fetchall()]})

@app.route('/api/upload-log')
@require_auth
def get_upload_log():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT * FROM upload_log ORDER BY uploaded_at DESC LIMIT 20
    """)
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        for k in ['uploaded_at','date_from','date_to']:
            if d.get(k): d[k] = d[k].isoformat()
        rows.append(d)
    return jsonify({'logs': rows})

# ── SEED: cargar el histórico completo ────────────────────────────────────────
@app.route('/api/seed', methods=['POST'])
@require_auth
def seed():
    """
    Carga el historial completo desde un JSON pre-procesado.
    Solo para la migración inicial. Protegido con contraseña de admin.
    """
    admin_pwd = os.environ.get('ADMIN_PASSWORD', '')
    if request.headers.get('X-Admin-Password') != admin_pwd or not admin_pwd:
        return jsonify({'error': 'Requiere X-Admin-Password de admin'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'Envía el JSON como form-data "file"'}), 400

    data = json.loads(request.files['file'].read().decode('utf-8'))
    db = get_db()
    cur = db.cursor()
    inserted = 0

    for r in data:
        try:
            date_str = r.get('date') or r.get('d', '')
            if len(date_str) == 10 and date_str[4] == '-':
                pass  # ya YYYY-MM-DD
            elif '/' in date_str:
                parts = date_str.split('/')
                if len(parts[0]) == 2:  # DD/MM/YYYY
                    date_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"

            mediator = r.get('mediator') or r.get('m', '')
            turn     = r.get('turn')     or r.get('t', '')
            mood     = r.get('mood')     or r.get('mo', '?')
            vocab    = r.get('vocab')    or r.get('vo', [])

            cur.execute("""
                INSERT INTO reports
                  (date, mediator, turn, mood, conducta, estiramientos, agua, pis,
                   banyo, estado, comunicacion, actividades, comidas, medicacion,
                   notas, vocab, formato, body_preview)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (date, mediator, turn) DO NOTHING
            """, (
                date_str, mediator, turn, mood,
                r.get('conducta') or r.get('c', 0),
                r.get('estiramientos', 0),
                r.get('agua') or r.get('ag'),
                r.get('pis') or r.get('p'),
                r.get('banyo') or r.get('b', ''),
                r.get('estado') or r.get('st', ''),
                r.get('comunicacion') or r.get('co', ''),
                r.get('actividades') or r.get('ac', ''),
                r.get('comidas') or r.get('cm', ''),
                r.get('medicacion') or r.get('me', ''),
                r.get('notas') or r.get('no', ''),
                json.dumps(vocab, ensure_ascii=False),
                r.get('formato') or r.get('fmt', 'v1'),
                r.get('body_preview', '')[:300],
            ))
            if cur.rowcount > 0:
                inserted += 1
        except Exception as e:
            continue

    db.commit()
    return jsonify({'ok': True, 'inserted': inserted, 'total': len(data)})

# ── MAIN ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if DATABASE_URL:
        init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
