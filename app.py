import os, json
from functools import wraps
from datetime import datetime
from flask import Flask, request, jsonify, g, send_file
from flask_cors import CORS
from dotenv import load_dotenv

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

from parser import parse_whatsapp

load_dotenv()
app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

DATABASE_URL   = os.environ.get('DATABASE_URL', '')
API_PASSWORD   = os.environ.get('API_PASSWORD', 'haptica2025')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'hapticaadmin2025')

# Normalización de nombres de mediadores
NAME_MAP = {
    'Mediador Raúl Blasco': 'Raúl Blasco',
    'Javier Cuidador': 'Javier',
    'Jonathan Cuidador': 'Jonathan',
    'Mediadora Eva Miguel Mediadora Eva Miguel': 'Eva Miguel',
    'Mapi Martinez Clerigué': 'Mapi Martínez',
    'Maria Jesus Morales': 'María Jesús (familia)',
    'Mediador Eli': 'Eli',
    'Ari Mediadora': 'Ari',
    'Greg Mediador': 'Gregory',
    'Elena  Mediadora': 'Elena',
    'Ainhoa Mediadora': 'Ainhoa',
    'Belen Auqui Mediador': 'Belén Auqui',
    'Irene Irene Buera': 'Irene Buera',
    'Irene Mediadora': 'Irene',
    'Laura Sobrino': 'Laura',
    'Mediadora Rebeca Burillo': 'Rebeca',
    'Mediadora  Maria': 'María',
    'Leyre Mediadora': 'Leyre',
    'Carmen Asensio Gerente': 'Carmen (dirección)',
    'Amalia Mediadora': 'Amalia',
    'Delia Mediadora': 'Delia',
    'Mediadora Sofi': 'Sophie',
    'Fran Cuidador': 'Franklin',
    'Karol Mediadora': 'Karol',
    'Carla Mediadora': 'Carla',
    'Dulce Mediadora': 'Dulce Alef',
    'Alicia Mediadora': 'Alicia',
    'Veronica Mediadora': 'Verónica',
    'Alba Mediadora': 'Alba',
    'Adri': 'Adri',
    'Luna Mediadora': 'Luna',
    'Paula Monge': 'Paula',
    'Vanessa ✨': 'Vanessa',
    'Blanca Yunquera': 'Blanca',
    'Angel España Morales': 'Ángel (familia)',
    'Susana España': 'Susana (familia)',
    'Maria España': 'María (familia)',
    'Carlos De Paz': 'Carlos',
}

def normalize_mediator(name):
    clean = name.lstrip('\u200e').replace('~', '').strip()
    return NAME_MAP.get(clean, clean)

def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db:
        try: db.close()
        except: pass

def init_db():
    if not DATABASE_URL or not psycopg2: return
    try:
        db = psycopg2.connect(DATABASE_URL)
        cur = db.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id SERIAL PRIMARY KEY, date DATE NOT NULL,
                mediator TEXT NOT NULL, turn TEXT DEFAULT 'sin especificar',
                mood TEXT DEFAULT '?', conducta INTEGER DEFAULT 0,
                estiramientos INTEGER DEFAULT 0, agua INTEGER, pis INTEGER,
                banyo TEXT DEFAULT '', estado TEXT DEFAULT '',
                comunicacion TEXT DEFAULT '', actividades TEXT DEFAULT '',
                comidas TEXT DEFAULT '', medicacion TEXT DEFAULT '',
                notas TEXT DEFAULT '', vocab JSONB DEFAULT '[]',
                formato TEXT DEFAULT 'v1', body_preview TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(date, mediator, turn)
            );
            CREATE TABLE IF NOT EXISTS upload_log (
                id SERIAL PRIMARY KEY, uploaded_at TIMESTAMPTZ DEFAULT NOW(),
                total_in_file INTEGER, new_inserted INTEGER, duplicates INTEGER,
                date_from DATE, date_to DATE, uploaded_by TEXT DEFAULT 'dashboard'
            );
            CREATE TABLE IF NOT EXISTS annotations (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                type TEXT NOT NULL,
                label TEXT NOT NULL,
                description TEXT DEFAULT '',
                color TEXT DEFAULT '#E8833A',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(date);
            CREATE INDEX IF NOT EXISTS idx_reports_mediator ON reports(mediator);
        """)
        db.commit(); cur.close(); db.close()
        print("DB lista")
        import threading
        threading.Thread(target=auto_seed, daemon=True).start()
        threading.Thread(target=normalize_existing_mediators, daemon=True).start()
    except Exception as e:
        print(f"init_db error: {e}")

def auto_seed():
    seed_file = os.path.join(os.path.dirname(__file__), 'seed.json')
    if not os.path.exists(seed_file): return
    try:
        db = psycopg2.connect(DATABASE_URL)
        cur = db.cursor()
        cur.execute('SELECT COUNT(*) as n FROM reports')
        n = cur.fetchone()[0]
        if n > 0:
            print(f"DB ya tiene {n} registros, skip seed")
            cur.close(); db.close(); return
        print("Cargando seed.json...")
        with open(seed_file, encoding='utf-8') as f:
            data = json.load(f)
        inserted = 0
        for r in data:
            med = normalize_mediator(r.get('mediator', ''))
            try:
                cur.execute("""INSERT INTO reports
                    (date,mediator,turn,mood,conducta,estiramientos,agua,pis,
                     banyo,estado,comunicacion,actividades,comidas,medicacion,
                     notas,vocab,formato,body_preview)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (date,mediator,turn) DO NOTHING""",
                    (r.get('date'), med, r.get('turn','sin especificar'),
                     r.get('mood','?'), r.get('conducta',0), r.get('estiramientos',0),
                     r.get('agua'), r.get('pis'), r.get('banyo',''), r.get('estado',''),
                     r.get('comunicacion',''), r.get('actividades',''), r.get('comidas',''),
                     r.get('medicacion',''), r.get('notas',''),
                     json.dumps(r.get('vocab',[]), ensure_ascii=False),
                     r.get('formato','v1'), r.get('body_preview','')[:300]))
                if cur.rowcount > 0: inserted += 1
            except: db.rollback()
        db.commit()
        print(f"Seed: {inserted} registros")
        cur.close(); db.close()
    except Exception as e:
        print(f"auto_seed error: {e}")

def normalize_existing_mediators():
    """Normaliza los nombres de mediadores ya en BD."""
    try:
        db = psycopg2.connect(DATABASE_URL)
        cur = db.cursor()
        updated = 0
        for orig, norm in NAME_MAP.items():
            if orig != norm:
                cur.execute("UPDATE reports SET mediator=%s WHERE mediator=%s", (norm, orig))
                updated += cur.rowcount
        db.commit()
        if updated: print(f"Normalizados {updated} registros de mediadores")
        cur.close(); db.close()
    except Exception as e:
        print(f"normalize error: {e}")

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        pwd = request.headers.get('X-Password') or request.args.get('pwd') or ''
        if pwd != API_PASSWORD:
            return jsonify({'error': 'No autorizado'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def health():
    return jsonify({'status': 'ok', 'service': 'HAPTICA Jorge API', 'version': '2.0'})

@app.route('/dashboard')
@app.route('/dashboard/')
def frontend():
    return send_file('index.html')

@app.route('/api/ping')
def ping():
    pwd = request.headers.get('X-Password') or request.args.get('pwd') or ''
    if pwd != API_PASSWORD:
        return jsonify({'error': 'No autorizado'}), 401
    try:
        db = get_db(); cur = db.cursor()
        cur.execute('SELECT COUNT(*) as n FROM reports')
        n = cur.fetchone()['n']
        return jsonify({'status': 'ok', 'total_reports': n})
    except:
        return jsonify({'status': 'ok', 'total_reports': 0})

@app.route('/api/upload', methods=['POST'])
@require_auth
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No se recibio archivo'}), 400
    text = request.files['file'].read().decode('utf-8', errors='replace')
    reports = parse_whatsapp(text)
    if not reports:
        return jsonify({'error': 'No se encontraron informes'}), 400
    db = get_db(); cur = db.cursor()
    inserted = duplicates = 0
    for r in reports:
        med = normalize_mediator(r['mediator'])
        try:
            cur.execute("""INSERT INTO reports
                (date,mediator,turn,mood,conducta,estiramientos,agua,pis,
                 banyo,estado,comunicacion,actividades,comidas,medicacion,
                 notas,vocab,formato,body_preview)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (date,mediator,turn) DO NOTHING""",
                (r['date'], med, r['turn'], r['mood'], r['conducta'],
                 r['estiramientos'], r['agua'], r['pis'], r['banyo'], r['estado'],
                 r['comunicacion'], r['actividades'], r['comidas'], r['medicacion'],
                 r['notas'], json.dumps(r['vocab'], ensure_ascii=False),
                 r['formato'], r['body_preview']))
            if cur.rowcount > 0: inserted += 1
            else: duplicates += 1
        except: db.rollback()
    dates = sorted(r['date'] for r in reports)
    try:
        cur.execute("INSERT INTO upload_log (total_in_file,new_inserted,duplicates,date_from,date_to) VALUES (%s,%s,%s,%s,%s)",
                    (len(reports), inserted, duplicates, dates[0], dates[-1]))
    except: pass
    db.commit()
    return jsonify({'ok': True, 'total_in_file': len(reports), 'new_inserted': inserted,
                    'duplicates': duplicates, 'date_from': dates[0], 'date_to': dates[-1]})

@app.route('/api/reports')
@require_auth
def get_reports():
    db = get_db(); cur = db.cursor()
    where, params = ['1=1'], []
    for k, col in [('from','date >='),('to','date <='),('mediator','mediator ='),('turn','turn ='),('mood','mood =')]:
        if request.args.get(k): where.append(f'{col} %s'); params.append(request.args[k])
    if request.args.get('conducta') == '1': where.append('conducta > 0')
    if request.args.get('conducta') == '0': where.append('conducta = 0')
    cur.execute(f"""SELECT id,date,mediator,turn,mood,conducta,estiramientos,
               agua,pis,estado,comunicacion,actividades,comidas,
               medicacion,notas,vocab,formato,body_preview,banyo
        FROM reports WHERE {' AND '.join(where)}
        ORDER BY date DESC,id DESC""", params)
    result = []
    for r in cur.fetchall():
        d = dict(r)
        d['date'] = d['date'].isoformat() if d['date'] else None
        if isinstance(d['vocab'], str):
            try: d['vocab'] = json.loads(d['vocab'])
            except: d['vocab'] = []
        result.append(d)
    return jsonify({'reports': result, 'total': len(result)})

@app.route('/api/stats')
@require_auth
def get_stats():
    db = get_db(); cur = db.cursor()
    cur.execute("""SELECT COUNT(*) AS total, MIN(date) AS date_from, MAX(date) AS date_to,
        ROUND(AVG(CASE WHEN agua<3000 THEN agua END)) AS avg_agua,
        ROUND(AVG(CASE WHEN mood='muy_positivo' THEN 4 WHEN mood='positivo' THEN 3
                       WHEN mood='neutro' THEN 2 WHEN mood='negativo' THEN 1 ELSE 2.5 END)::numeric,2) AS avg_mood,
        ROUND(100.0*SUM(CASE WHEN conducta=0 THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_sin_picos,
        ROUND(100.0*SUM(CASE WHEN mood IN ('positivo','muy_positivo') THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_positivo,
        COUNT(DISTINCT mediator) AS n_mediators FROM reports""")
    s = dict(cur.fetchone())
    for k in ['date_from','date_to']:
        if s.get(k): s[k] = s[k].isoformat()
    cur.execute("""SELECT TO_CHAR(date,'YYYY-MM') AS month, COUNT(*) AS total,
        ROUND(AVG(CASE WHEN mood='muy_positivo' THEN 4 WHEN mood='positivo' THEN 3
                       WHEN mood='neutro' THEN 2 WHEN mood='negativo' THEN 1 ELSE 2.5 END)::numeric,2) AS avg_mood,
        ROUND(100.0*SUM(CASE WHEN conducta>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_picos,
        ROUND(AVG(CASE WHEN agua<3000 THEN agua END)) AS avg_agua
        FROM reports GROUP BY month ORDER BY month DESC LIMIT 48""")
    monthly = [dict(r) for r in cur.fetchall()]
    cur.execute("""SELECT mediator, COUNT(*) AS total,
        ROUND(100.0*SUM(CASE WHEN conducta>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_picos,
        ROUND(AVG(CASE WHEN mood='muy_positivo' THEN 4 WHEN mood='positivo' THEN 3
                       WHEN mood='neutro' THEN 2 WHEN mood='negativo' THEN 1 ELSE 2.5 END)::numeric,2) AS avg_mood,
        MIN(date) AS first_date, MAX(date) AS last_date
        FROM reports WHERE mediator NOT LIKE '%(familia)%' AND mediator != 'Carmen (dirección)'
        GROUP BY mediator ORDER BY total DESC""")
    by_med = []
    for r in cur.fetchall():
        d = dict(r)
        d['first_date'] = d['first_date'].isoformat() if d['first_date'] else None
        d['last_date']  = d['last_date'].isoformat()  if d['last_date']  else None
        by_med.append(d)
    cur.execute("SELECT mood, COUNT(*) AS n FROM reports GROUP BY mood ORDER BY n DESC")
    mood_dist = [dict(r) for r in cur.fetchall()]
    cur.execute("""SELECT uploaded_at,total_in_file,new_inserted,duplicates,date_from,date_to,uploaded_by
        FROM upload_log ORDER BY uploaded_at DESC LIMIT 10""")
    uploads = []
    for r in cur.fetchall():
        d = dict(r)
        for k in ['uploaded_at','date_from','date_to']:
            if d.get(k): d[k] = d[k].isoformat()
        uploads.append(d)
    # Anotaciones
    cur.execute("SELECT id,date,type,label,description,color FROM annotations ORDER BY date")
    annotations = []
    for r in cur.fetchall():
        d = dict(r)
        d['date'] = d['date'].isoformat() if d['date'] else None
        annotations.append(d)
    return jsonify({'summary': s, 'monthly': monthly, 'by_mediator': by_med,
                    'mood_dist': mood_dist, 'upload_log': uploads, 'annotations': annotations})

@app.route('/api/mediators')
@require_auth
def get_mediators():
    db = get_db(); cur = db.cursor()
    cur.execute("""SELECT DISTINCT mediator FROM reports
        WHERE mediator NOT LIKE '%(familia)%' AND mediator != 'Carmen (dirección)'
        ORDER BY mediator""")
    return jsonify({'mediators': [r['mediator'] for r in cur.fetchall()]})

@app.route('/api/upload-log')
@require_auth
def get_upload_log():
    db = get_db(); cur = db.cursor()
    cur.execute("SELECT * FROM upload_log ORDER BY uploaded_at DESC LIMIT 20")
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        for k in ['uploaded_at','date_from','date_to']:
            if d.get(k): d[k] = d[k].isoformat()
        rows.append(d)
    return jsonify({'logs': rows})

@app.route('/api/annotations', methods=['GET'])
@require_auth
def get_annotations():
    db = get_db(); cur = db.cursor()
    cur.execute("SELECT * FROM annotations ORDER BY date")
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        d['date'] = d['date'].isoformat() if d['date'] else None
        d['created_at'] = d['created_at'].isoformat() if d['created_at'] else None
        rows.append(d)
    return jsonify({'annotations': rows})

@app.route('/api/annotations', methods=['POST'])
@require_auth
def add_annotation():
    data = request.get_json()
    db = get_db(); cur = db.cursor()
    cur.execute("""INSERT INTO annotations (date, type, label, description, color)
        VALUES (%s,%s,%s,%s,%s) RETURNING id""",
        (data['date'], data.get('type','event'), data['label'],
         data.get('description',''), data.get('color','#E8833A')))
    new_id = cur.fetchone()['id']
    db.commit()
    return jsonify({'ok': True, 'id': new_id})

@app.route('/api/annotations/<int:ann_id>', methods=['DELETE'])
@require_auth
def delete_annotation(ann_id):
    db = get_db(); cur = db.cursor()
    cur.execute("DELETE FROM annotations WHERE id=%s", (ann_id,))
    db.commit()
    return jsonify({'ok': True})

@app.route('/api/seed', methods=['POST'])
def seed():
    if request.headers.get('X-Admin-Password') != ADMIN_PASSWORD:
        return jsonify({'error': 'No autorizado'}), 403
    data = json.loads(request.files['file'].read().decode('utf-8'))
    db = get_db(); cur = db.cursor()
    inserted = 0
    for r in data:
        med = normalize_mediator(r.get('mediator', ''))
        try:
            cur.execute("""INSERT INTO reports
                (date,mediator,turn,mood,conducta,estiramientos,agua,pis,
                 banyo,estado,comunicacion,actividades,comidas,medicacion,
                 notas,vocab,formato,body_preview)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (date,mediator,turn) DO NOTHING""",
                (r.get('date'), med, r.get('turn','sin especificar'),
                 r.get('mood','?'), r.get('conducta',0), r.get('estiramientos',0),
                 r.get('agua'), r.get('pis'), r.get('banyo',''), r.get('estado',''),
                 r.get('comunicacion',''), r.get('actividades',''), r.get('comidas',''),
                 r.get('medicacion',''), r.get('notas',''),
                 json.dumps(r.get('vocab',[]), ensure_ascii=False),
                 r.get('formato','v1'), r.get('body_preview','')[:300]))
            if cur.rowcount > 0: inserted += 1
        except: continue
    db.commit()
    return jsonify({'ok': True, 'inserted': inserted, 'total': len(data)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


# ── PAI (Plan de Atención Individualizada) ────────────────────────────────────
def init_pai_table():
    try:
        db = psycopg2.connect(DATABASE_URL)
        cur = db.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pai (
                id TEXT PRIMARY KEY,
                periodo_inicio DATE,
                periodo_fin DATE,
                trimestre TEXT DEFAULT '',
                estado TEXT DEFAULT 'borrador',
                profesional_responsable TEXT DEFAULT '',
                profesionales_participantes TEXT DEFAULT '',
                contexto_actual TEXT DEFAULT '',
                fortalezas TEXT DEFAULT '',
                necesidades TEXT DEFAULT '',
                objetivos JSONB DEFAULT '[]',
                areas_score JSONB DEFAULT '{}',
                logros TEXT DEFAULT '',
                dificultades TEXT DEFAULT '',
                propuesta_siguiente TEXT DEFAULT '',
                fecha_reunion_familia DATE,
                familia_presentes TEXT DEFAULT '',
                observaciones_familia TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        db.commit(); cur.close(); db.close()
    except Exception as e:
        print(f"init_pai error: {e}")

@app.route('/pai')
@app.route('/pai/')
def pai_frontend():
    return send_file('pai.html')

@app.route('/api/pai', methods=['GET'])
@require_auth
def get_pai():
    init_pai_table()
    db = get_db(); cur = db.cursor()
    cur.execute('SELECT * FROM pai ORDER BY periodo_inicio DESC NULLS LAST')
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        for k in ['periodo_inicio','periodo_fin','fecha_reunion_familia','created_at','updated_at']:
            if d.get(k): d[k] = d[k].isoformat() if hasattr(d[k],'isoformat') else d[k]
        for k in ['objetivos','areas_score']:
            if isinstance(d.get(k), str):
                try: d[k] = json.loads(d[k])
                except: d[k] = [] if k=='objetivos' else {}
        rows.append(d)
    return jsonify({'pais': rows})

@app.route('/api/pai', methods=['POST'])
@require_auth
def save_pai():
    init_pai_table()
    data = request.get_json()
    db = get_db(); cur = db.cursor()
    pai_id = data.get('id') or f"pai_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    cur.execute("""
        INSERT INTO pai (id,periodo_inicio,periodo_fin,trimestre,estado,
            profesional_responsable,profesionales_participantes,contexto_actual,
            fortalezas,necesidades,objetivos,areas_score,logros,dificultades,
            propuesta_siguiente,fecha_reunion_familia,familia_presentes,
            observaciones_familia,updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
        ON CONFLICT (id) DO UPDATE SET
            periodo_inicio=EXCLUDED.periodo_inicio,periodo_fin=EXCLUDED.periodo_fin,
            trimestre=EXCLUDED.trimestre,estado=EXCLUDED.estado,
            profesional_responsable=EXCLUDED.profesional_responsable,
            profesionales_participantes=EXCLUDED.profesionales_participantes,
            contexto_actual=EXCLUDED.contexto_actual,fortalezas=EXCLUDED.fortalezas,
            necesidades=EXCLUDED.necesidades,objetivos=EXCLUDED.objetivos,
            areas_score=EXCLUDED.areas_score,logros=EXCLUDED.logros,
            dificultades=EXCLUDED.dificultades,propuesta_siguiente=EXCLUDED.propuesta_siguiente,
            fecha_reunion_familia=EXCLUDED.fecha_reunion_familia,
            familia_presentes=EXCLUDED.familia_presentes,
            observaciones_familia=EXCLUDED.observaciones_familia,
            updated_at=NOW()
    """, (
        pai_id,
        data.get('periodo_inicio') or None, data.get('periodo_fin') or None,
        data.get('trimestre',''), data.get('estado','borrador'),
        data.get('profesional_responsable',''), data.get('profesionales_participantes',''),
        data.get('contexto_actual',''), data.get('fortalezas',''), data.get('necesidades',''),
        json.dumps(data.get('objetivos',[]), ensure_ascii=False),
        json.dumps(data.get('areas_score',{}), ensure_ascii=False),
        data.get('logros',''), data.get('dificultades',''), data.get('propuesta_siguiente',''),
        data.get('fecha_reunion_familia') or None,
        data.get('familia_presentes',''), data.get('observaciones_familia','')
    ))
    db.commit()
    return jsonify({'ok': True, 'id': pai_id})

@app.route('/api/pai/<pai_id>', methods=['DELETE'])
@require_auth
def delete_pai(pai_id):
    init_pai_table()
    db = get_db(); cur = db.cursor()
    cur.execute('DELETE FROM pai WHERE id=%s', (pai_id,))
    db.commit()
    return jsonify({'ok': True})
