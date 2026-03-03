import os, json, hashlib
from functools import wraps
from datetime import datetime
from flask import Flask, request, jsonify, g, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# Intentar importar psycopg2 de forma segura
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PS_AVAILABLE = True
except ImportError:
    PS_AVAILABLE = False
    print("ALERTA: No se pudo cargar psycopg2. libpq.so.5 ausente.")

from parser import parse_whatsapp

load_dotenv()
app = Flask(__name__)

# 1. INICIALIZACIÓN (Crítico: Definir 'app' antes que las rutas)
load_dotenv()
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuración
DATABASE_URL = os.environ.get('DATABASE_URL', '')
API_PASSWORD = os.environ.get('API_PASSWORD', 'haptica2025')

# 2. RUTAS DE FRONTEND
@app.route('/')
def health():
    return jsonify({'status': 'ok', 'service': 'HÁPTICA Jorge API', 'version': '1.0'})

@app.route('/dashboard')
@app.route('/dashboard/')
def frontend():
    """Sirve el dashboard HTML."""
    return send_file('index.html')

# 3. GESTIÓN DE BASE DE DATOS
def get_db():
    if 'db' not in g:
        if not DATABASE_URL:
            raise Exception("DATABASE_URL no configurada")
        g.db = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

def init_db():
    """Crea la tabla si no existe."""
    if not DATABASE_URL: return
    try:
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
                UNIQUE(date, mediator, turn)
            );
        """)
        db.commit()
        cur.close()
        db.close()
    except Exception as e:
        print(f"Error DB Init: {e}")

with app.app_context():
    init_db()

# 4. SEGURIDAD
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        pw = request.headers.get('X-Api-Password')
        if pw != API_PASSWORD:
            return jsonify({'error': 'No autorizado'}), 401
        return f(*args, **kwargs)
    return decorated

# 5. RUTAS DE LA API (Tu lógica original completa)
@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({'status': 'ok', 'db': bool(DATABASE_URL)})

@app.route('/api/reports', methods=['GET'])
def get_reports():
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM reports ORDER BY date DESC, id DESC LIMIT 100")
        rows = cur.fetchall()
        for r in rows:
            if r['date']: r['date'] = r['date'].isoformat()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
@require_auth
def upload_data():
    raw_text = request.json.get('text', '')
    if not raw_text:
        return jsonify({'error': 'No text provided'}), 400

    data = parse_whatsapp(raw_text)
    db = get_db()
    cur = db.cursor()
    inserted = 0

    for r in data:
        try:
            # Extraemos los campos del parser
            date_str = r.get('date')
            mediator = r.get('mediator')
            turn     = r.get('turn')
            vocab    = r.get('vocab', [])

            cur.execute("""
                INSERT INTO reports (
                    date, mediator, turn, mood, conducta, estiramientos, agua, pis,
                    banyo, estado, comunicacion, actividades, comidas, medicacion,
                    notas, vocab, formato, body_preview)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (date, mediator, turn) DO NOTHING
            """, (
                date_str, mediator, turn, r.get('mood'),
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
        except Exception:
            continue

    db.commit()
    return jsonify({'ok': True, 'inserted': inserted, 'total': len(data)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
