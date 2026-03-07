import os, json
from functools import wraps
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, g, send_file
from flask_cors import CORS
from dotenv import load_dotenv

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

from parser import parse_whatsapp

load_dotenv()
# ── Normalizador de actividades ────────────────────────────────────────────────
_ACTIVITY_MAP = {
    'tranvía': ['tranvia','tranvía','tranvía y mediadores','tranvia al centro','tranvía al centro','tranvia a casa','tranvía a casa'],
    'piscina': ['piscina','nadar','natación','piscina…'],
    'bicicleta': ['bici','bicicleta'],
    'paseo': ['paseo','paseo por el pinar','el pinar','pinar'],
    'cinta de correr': ['cinta de correr','cinta de correr…'],
    'desayuno': ['desayuno','desayuno)'],
    'almuerzo': ['almuerzo'],
    'comida': ['comida'],
    'merienda': ['merienda','merendamos'],
    'cena': ['cena','cena (signos habitación','cena ( signos babero'],
    'aseo/higiene': ['aseo','ducha','ropa','peinar','calcetines','babero','sucio'],
    'rutina residencia': ['rutina de residencia (ducha','rutina de residencia  (ducha','rutina de residencia'],
    'tapones (autonomía)': ['tapones','tapones autónomamente','tapones de forma autónoma','tapones autonomamente'],
    'autonomía': ['autonomía','autonomía: limpia mesa'],
    'comunicación': ['comunicación','conversación trasversal'],
    'braille': ['braille'],
    'anticipadores': ['anticipadores','anticipadores...)','anticipación'],
    'centro de recursos': ['centro de recursos','centro de recursos:'],
    'huerto': ['huerto'],
    'música': ['música'],
    'relajación/masaje': ['relajación','masaje abdominal','masaje'],
    'coche': ['coche de raúl','coche'],
    'vuelta a casa': ['vuelta a casa'],
    'compañeros': ['compañeros'],
    'deporte': ['deporte'],
}
_INV_ACT = {}
for _c, _vs in _ACTIVITY_MAP.items():
    for _v in _vs:
        _INV_ACT[_v.lower().strip()] = _c

def normalize_activity(line):
    line = line.strip().strip('-*\u2022\u00b7\u2060').strip().rstrip('.,').lower()
    if len(line) < 3 or len(line) > 70:
        return None
    return _INV_ACT.get(line, line.capitalize())


app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

DATABASE_URL   = os.environ.get('DATABASE_URL', '')
API_PASSWORD   = os.environ.get('API_PASSWORD', 'haptica2025')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'hapticaadmin2025')

# Normalización de nombres de mediadores
NAME_MAP = {
    # ── FAMILIA ──
    'Maria Jesus Morales':                       'María Jesús (familia)',
    'AA Mamá':                                   'María Jesús (familia)',
    'Angel España Morales':                      'Ángel (familia)',
    'Susana España':                             'Susana (familia)',
    'Maria España':                              'María (familia)',
    # ── MEDIADORES ──
    'Mediador Raúl Blasco':                      'Raúl Blasco',
    'Javier Cuidador':                           'Javier',
    'Jonathan Cuidador':                         'Jonathan',
    'Mediadora Eva Miguel Mediadora Eva Miguel':  'Eva Miguel',
    'Mediadora Eva Miguel':                      'Eva Miguel',
    'Mapi Martinez Clerigué':                    'Mapi Martínez',
    'Mapi Martinez':                             'Mapi Martínez',
    'Mediador Eli':                              'Eli',
    'Ari Mediadora':                             'Ari',
    'Greg Mediador':                             'Gregory',
    'gregorioalexander':                         'Gregory',
    'Elena  Mediadora':                          'Elena',
    'Elena Mediadora':                           'Elena',
    'Ainhoa Mediadora':                          'Ainhoa',
    'Belen Auqui Mediador':                      'Belén Auqui',
    'Belen':                                     'Belén Auqui',
    'Belén':                                     'Belén Auqui',
    'Irene Irene Buera':                         'Irene Buera',
    'Laura Sobrino':                             'Laura',
    'Mediadora Rebeca Burillo':                  'Rebeca',
    'Mediadora  Maria':                          'María',
    'Mediadora Maria':                           'María',
    'Leyre Mediadora':                           'Leyre',
    'Carmen Asensio Gerente':                    'Carmen (dirección)',
    'Carmen Asensio':                            'Carmen (dirección)',
    'Amalia Mediadora':                          'Amalia',
    'Delia Mediadora':                           'Delia',
    'Mediadora Sofi':                            'Sophie',
    'Sophie Guerra':                             'Sophie',
    'Fran Cuidador':                             'Franklin',
    'Franklin Mojica':                           'Franklin',
    'Karol Mediadora':                           'Karol',
    'Carla Mediadora':                           'Carla',
    'Alicia Mediadora':                          'Alicia',
    'Veronica Mediadora':                        'Verónica',
    'Dulce Mediadora':                           'Dulce Alef',
    'Alba Mediadora':                            'Alba',
    'Luna Mediadora':                            'Luna',
    'Irene Mediadora':                           'Irene',
    'Paula Monge':                               'Paula',
    'Vanessa ✨':                                'Vanessa',
    'Blanca Yunquera':                           'Blanca',
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
                seq INTEGER DEFAULT 1,
                mood TEXT DEFAULT '?', conducta INTEGER DEFAULT 0,
                estiramientos INTEGER DEFAULT 0, agua INTEGER, pis INTEGER,
                banyo TEXT DEFAULT '', estado TEXT DEFAULT '',
                comunicacion TEXT DEFAULT '', actividades TEXT DEFAULT '',
                comidas TEXT DEFAULT '', medicacion TEXT DEFAULT '',
                notas TEXT DEFAULT '', vocab JSONB DEFAULT '[]',
                formato TEXT DEFAULT 'v1', body_preview TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            ALTER TABLE reports ADD COLUMN IF NOT EXISTS banyo TEXT DEFAULT '';
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
        db.commit()
        # Migración: añadir seq si no existe
        try:
            cur.execute("ALTER TABLE reports ADD COLUMN IF NOT EXISTS seq INTEGER DEFAULT 1")
            db.commit()
        except: db.rollback()
        try:
            cur.execute("ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_date_mediator_turn_key")
            db.commit()
        except: db.rollback()
        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS reports_unique_seq ON reports(date,mediator,turn,seq)")
            db.commit()
        except: db.rollback()
        cur.close(); db.close()
        print("DB lista")
        import threading
        threading.Thread(target=auto_seed, daemon=True).start()
        threading.Thread(target=normalize_existing_mediators, daemon=True).start()
    except Exception as e:
        print(f"init_db error: {e}")

def auto_seed():
    """Carga seed.json si la BD está vacía. Se ejecuta en thread background."""
    seed_file = os.path.join(os.path.dirname(__file__), 'seed.json')
    if not os.path.exists(seed_file):
        print("auto_seed: seed.json no encontrado"); return
    try:
        import subprocess
        result = subprocess.run(['python3', 'load_data.py'], 
            capture_output=True, text=True, timeout=300)
        print("load_data stdout:", result.stdout[-500:] if result.stdout else '')
        if result.stderr: print("load_data stderr:", result.stderr[-200:])
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

# ── Estado medio (escala 0–5) ──────────────────────────────────────────────
# Fórmula ponderada:
#   Ánimo mediador       40%  (muy_positivo=1.0, positivo=0.75, neutro=0.5, negativo=0.0)
#   Ausencia conducta    30%  (sin picos=1.0, 1 pico=0.4, 2+ picos=0.0)
#   Sin med. rescate     20%  (sin rescate=1.0, con rescate=0.0)
#   Hidratación+baño     10%  (solo si hay datos; si no, se redistribuye entre los demás)
# Penalizaciones extra:
#   · 2+ picos conducta (agresión/autolesión): −0.25 adicional
#   · Tranquilizantes (diazepam/lorazepam): −0.10 adicional
# Resultado final: score_ponderado × 5, acotado a [0, 5]
_RESCUE = ['nolotil','paracetamol','ibuprofeno','diazepam','lorazepam',
           'buscapina','algidol','spasmoctyl','fortasec']
_TRANQ  = ['diazepam','lorazepam']

def calc_estado_medio(mood, conducta, medicacion, agua=None, banyo=None):
    mood_s = {'muy_positivo':1.0,'positivo':0.75,'neutro':0.5,'negativo':0.0}.get(mood or '', 0.5)
    cond   = int(conducta or 0)
    cond_s = 1.0 if cond == 0 else (0.4 if cond == 1 else 0.0)
    med    = (medicacion or '').lower()
    med_s  = 0.0 if any(m in med for m in _RESCUE) else 1.0
    agua_v = int(agua) if agua else 0
    banyo_v = (banyo or '').strip()
    if agua_v > 0 or banyo_v:
        agua_s  = 1.0 if agua_v >= 1000 else (0.6 if agua_v >= 500 else 0.3)
        banyo_s = 1.0 if len(banyo_v) > 2 else 0.4
        hid_s   = (agua_s + banyo_s) / 2
        base = mood_s*0.40 + cond_s*0.30 + med_s*0.20 + hid_s*0.10
    else:
        base = mood_s*0.45 + cond_s*0.35 + med_s*0.20
    if cond >= 2:        base -= 0.25
    if any(t in med for t in _TRANQ): base -= 0.10
    return round(max(0.0, min(5.0, base * 5)), 1)


@app.route('/')
def health():
    return jsonify({'status': 'ok', 'service': 'HAPTICA Jorge API', 'version': '2.0'})

@app.route('/dashboard')
@app.route('/dashboard/')
def frontend():
    from flask import make_response
    resp = make_response(send_file('index.html'))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp

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
    cur.execute("SELECT date::text, mediator, LEFT(body_preview,200) FROM reports")
    existing = set((row[0], row[1], row[2]) for row in cur.fetchall())

    to_insert = []
    duplicates = 0
    for r in reports:
        med = normalize_mediator(r['mediator'])
        key = (r['date'], med, r['body_preview'][:200])
        if key in existing:
            duplicates += 1
        else:
            to_insert.append((
                r['date'], med, r['turn'], r['mood'], r['conducta'],
                r['estiramientos'], r['agua'], r['pis'], r['banyo'], r['estado'],
                r['comunicacion'], r['actividades'], r['comidas'], r['medicacion'],
                r['notas'], json.dumps(r['vocab'], ensure_ascii=False),
                r['formato'], r['body_preview'][:300]
            ))

    inserted = 0
    SQL = "INSERT INTO reports (date,mediator,turn,mood,conducta,estiramientos,agua,pis,banyo,estado,comunicacion,actividades,comidas,medicacion,notas,vocab,formato,body_preview) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    if to_insert:
        try:
            cur.executemany(SQL, to_insert)
            inserted = len(to_insert)
            db.commit()
        except Exception as e:
            db.rollback()
            print("executemany error:", str(e)[:200])
            for row in to_insert:
                try:
                    cur.execute("SAVEPOINT s1")
                    cur.execute(SQL, row)
                    cur.execute("RELEASE SAVEPOINT s1")
                    inserted += 1
                except:
                    cur.execute("ROLLBACK TO SAVEPOINT s1")
                    cur.execute("RELEASE SAVEPOINT s1")
            db.commit()

    dates = sorted(r['date'] for r in reports)
    try:
        cur.execute("INSERT INTO upload_log (total_in_file,new_inserted,duplicates,date_from,date_to) VALUES (%s,%s,%s,%s,%s)",
                    (len(reports), inserted, duplicates, dates[0], dates[-1]))
        db.commit()
    except: pass
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
        ROUND(AVG(
            LEAST(5.0, GREATEST(0.0, (
              (CASE WHEN mood='muy_positivo' THEN 1.0 WHEN mood='positivo' THEN 0.75
                    WHEN mood='neutro' THEN 0.5 WHEN mood='negativo' THEN 0.0 ELSE 0.5 END)*0.45
              +(CASE WHEN conducta=0 THEN 1.0 WHEN conducta=1 THEN 0.4 ELSE 0.0 END)*0.35
              +(CASE WHEN LOWER(COALESCE(medicacion,'')) SIMILAR TO
                '%(nolotil|paracetamol|ibuprofeno|diazepam|lorazepam|buscapina|algidol|spasmoctyl|fortasec)%'
                THEN 0.0 ELSE 1.0 END)*0.20
              -(CASE WHEN conducta>=2 THEN 0.25 ELSE 0.0 END)
              -(CASE WHEN LOWER(COALESCE(medicacion,'')) SIMILAR TO '%(diazepam|lorazepam)%'
                THEN 0.10 ELSE 0.0 END)
            )*5.0))
        )::numeric,2) AS avg_estado,
        ROUND(100.0*SUM(CASE WHEN conducta>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_picos,
        ROUND(AVG(CASE WHEN agua<3000 THEN agua END)) AS avg_agua
        FROM reports GROUP BY month ORDER BY month ASC LIMIT 120""")
    monthly = [dict(r) for r in cur.fetchall()]
    cur.execute("""SELECT mediator, COUNT(*) AS total,
        ROUND(100.0*SUM(CASE WHEN conducta>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_picos,
        ROUND(AVG(CASE WHEN mood='muy_positivo' THEN 4 WHEN mood='positivo' THEN 3
                       WHEN mood='neutro' THEN 2 WHEN mood='negativo' THEN 1 ELSE 2.5 END)::numeric,2) AS avg_mood,
        MIN(date) AS first_date, MAX(date) AS last_date
        FROM reports
        GROUP BY mediator ORDER BY total DESC""")
    by_med = []
    for r in cur.fetchall():
        d = dict(r)
        d['first_date'] = d['first_date'].isoformat() if d['first_date'] else None
        d['last_date']  = d['last_date'].isoformat()  if d['last_date']  else None
        by_med.append(d)
    cur.execute("SELECT mood, COUNT(*) AS n FROM reports GROUP BY mood ORDER BY n DESC")
    mood_dist = [dict(r) for r in cur.fetchall()]
    uploads = []
    try:
        cur.execute("""SELECT uploaded_at,total_in_file,new_inserted,duplicates,date_from,date_to,uploaded_by
            FROM upload_log ORDER BY uploaded_at DESC LIMIT 10""")
        for r in cur.fetchall():
            d = dict(r)
            for k in ['uploaded_at','date_from','date_to']:
                if d.get(k): d[k] = d[k].isoformat()
            uploads.append(d)
    except: pass
    annotations = []
    try:
        cur.execute("SELECT id,date,type,label,description,color FROM annotations ORDER BY date")
        for r in cur.fetchall():
            d = dict(r)
            d['date'] = d['date'].isoformat() if d['date'] else None
            annotations.append(d)
    except: pass
    return jsonify({'summary': s, 'monthly': monthly, 'by_mediator': by_med,
                    'mood_dist': mood_dist, 'upload_log': uploads, 'annotations': annotations})

@app.route('/api/mediators')
@require_auth
def get_mediators():
    db = get_db(); cur = db.cursor()
    cur.execute("""SELECT DISTINCT mediator FROM reports
        
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
    admin_pwd = request.headers.get('X-Admin-Password','')
    if admin_pwd != ADMIN_PASSWORD and admin_pwd != API_PASSWORD:
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
                ON CONFLICT (date,mediator,turn,seq) DO NOTHING""",
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


@app.route('/api/admin/normalize', methods=['POST'])
def admin_normalize():
    admin_pwd = request.headers.get('X-Admin-Password','')
    if admin_pwd != ADMIN_PASSWORD and admin_pwd != API_PASSWORD:
        return jsonify({'error': 'No autorizado'}), 403
    MERGE = {
        'María Jesús (familia)':  ['Maria Jesus Morales'],
        'Delia':                  ['Delia Mediadora'],
        'Ari':                    ['Ari Mediadora'],
        'Rebeca':                 ['Mediadora Rebeca Burillo'],
        'Alicia':                 ['Alicia Mediadora'],
        'Eva Miguel':             ['Mediadora Eva Miguel Mediadora Eva Miguel'],
        'Ainhoa':                 ['Ainhoa Mediadora'],
        'María':                  ['Mediadora  Maria', 'Mediadora Maria'],
        'Leyre':                  ['Leyre Mediadora'],
        'Irene Buera':            ['Irene Irene Buera'],
        'Javier':                 ['Javier Cuidador'],
        'Eli':                    ['Mediador Eli'],
        'Raúl Blasco':            ['Mediador Raúl Blasco'],
        'Belén Auqui':            ['Belen Auqui Mediador', 'Belen', 'Belén'],
        'Carmen (dirección)':     ['Carmen Asensio Gerente', 'Carmen Asensio'],
        'María (familia)':        ['Maria España'],
        'Carla':                  ['Carla Mediadora'],
        'Verónica':               ['Veronica Mediadora'],
        'Gregory':                ['Greg Mediador', 'gregorioalexander'],
        'Luna':                   ['Luna Mediadora'],
        'Alba':                   ['Alba Mediadora'],
        'Sophie':                 ['Sophie Guerra', 'Mediadora Sofi'],
        'Elena':                  ['Elena Mediadora'],
        'Amalia':                 ['Amalia Mediadora'],
        'Mapi Martínez':          ['Mapi Martinez Clerigué', 'Mapi Martinez'],
    }
    db = get_db(); cur = db.cursor()
    total = 0
    results = {}
    for canonical, variants in MERGE.items():
        count = 0
        for v in variants:
            cur.execute("UPDATE reports SET mediator=%s WHERE mediator=%s", (canonical, v))
            count += cur.rowcount
        if count: results[canonical] = count
        total += count
    db.commit()
    return jsonify({'ok': True, 'total_updated': total, 'by_mediator': results})


@app.route('/api/admin/reload-seed', methods=['POST'])
def admin_reload_seed():
    admin_pwd = request.headers.get('X-Admin-Password','')
    if admin_pwd != ADMIN_PASSWORD and admin_pwd != API_PASSWORD:
        return jsonify({'error': 'No autorizado'}), 403
    seed_file = os.path.join(os.path.dirname(__file__), 'seed.json')
    if not os.path.exists(seed_file):
        return jsonify({'error': 'seed.json no encontrado'}), 404
    try:
        with open(seed_file, encoding='utf-8') as f:
            data = json.load(f)
        if not data:
            return jsonify({'error': 'seed.json vacío'}), 400
        db = psycopg2.connect(DATABASE_URL)
        cur = db.cursor()
        # Preparar todos los registros ANTES de borrar nada
        rows = []
        for r in data:
            rows.append((
                r.get('date'), r.get('mediator',''),
                r.get('turn','sin especificar'), int(r.get('seq') or 1),
                r.get('mood','?'), int(r.get('conducta') or 0),
                int(r.get('estiramientos') or 0),
                int(r.get('agua')) if r.get('agua') else None,
                int(r.get('pis')) if r.get('pis') else None,
                r.get('estado',''), r.get('comunicacion',''),
                r.get('actividades',''), r.get('comidas',''),
                r.get('medicacion',''), r.get('notas',''),
                json.dumps(r.get('vocab') or [], ensure_ascii=False),
                r.get('formato','v1'), (r.get('body_preview') or '')[:300],
                r.get('banyo','')
            ))
        # Ahora sí: borrar e insertar en lotes de 500
        cur.execute('DELETE FROM reports')
        SQL = """INSERT INTO reports
            (date,mediator,turn,seq,mood,conducta,estiramientos,agua,pis,estado,comunicacion,
             actividades,comidas,medicacion,notas,vocab,formato,body_preview,banyo)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (date,mediator,turn,seq) DO NOTHING"""
        BATCH = 500
        inserted = 0
        for i in range(0, len(rows), BATCH):
            batch = rows[i:i+BATCH]
            psycopg2.extras.execute_batch(cur, SQL, batch, page_size=BATCH)
            inserted += len(batch)
            db.commit()
        cur.close(); db.close()
        return jsonify({'ok': True, 'total': len(data), 'inserted': inserted})
    except Exception as e:
        try: db.rollback()
        except: pass
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/truncate', methods=['POST'])
def admin_truncate():
    admin_pwd = request.headers.get('X-Admin-Password','')
    if admin_pwd != ADMIN_PASSWORD and admin_pwd != API_PASSWORD:
        return jsonify({'error': 'No autorizado'}), 403
    try:
        db = get_db(); cur = db.cursor()
        cur.execute('TRUNCATE TABLE reports RESTART IDENTITY CASCADE')
        db.commit()
        cur.close()
        return jsonify({'ok': True, 'msg': 'Tabla reports vaciada'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vocab-stats')
@require_auth
def vocab_stats():
    db = get_db(); cur = db.cursor()
    year = request.args.get('year', '')
    mediator = request.args.get('mediator', '')
    where_parts = ["vocab IS NOT NULL", "vocab != '[]'"]
    params = []
    if year:
        where_parts += ["date >= %s", "date < %s"]
        params += [year+"-01-01", str(int(year)+1)+"-01-01"]
    if mediator:
        where_parts.append("mediator = %s")
        params.append(mediator)
    where = "WHERE " + " AND ".join(where_parts)
    cur.execute("SELECT vocab, actividades FROM reports " + where, params)
    from collections import Counter
    vocab_count = Counter()
    act_count = Counter()
    SEP = chr(10)
    for row in cur.fetchall():
        try:
            v = json.loads(row['vocab']) if row['vocab'] else []
            for w in v:
                w = (w or '').strip().lower()
                if len(w) > 1:
                    vocab_count[w] += 1
        except: pass
        act = (row['actividades'] or '').replace(',', SEP).replace(';', SEP)
        for line in act.split(SEP):
            norm = normalize_activity(line)
            if norm:
                act_count[norm] += 1
    return jsonify({
        'vocab': [{'word': w, 'count': c} for w, c in vocab_count.most_common(80)],
        'actividades': [{'act': a, 'count': c} for a, c in act_count.most_common(30)]
    })

@app.route('/api/correlations')
@require_auth
def get_correlations():
    db = get_db(); cur = db.cursor()
    # Por mediador
    cur.execute("""SELECT mediator,
        COUNT(*) AS total,
        ROUND(100.0*SUM(CASE WHEN conducta>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_picos,
        ROUND(AVG(CASE WHEN mood='muy_positivo' THEN 4 WHEN mood='positivo' THEN 3
                       WHEN mood='neutro' THEN 2 WHEN mood='negativo' THEN 1 ELSE NULL END)::numeric,2) AS avg_mood
        FROM reports GROUP BY mediator HAVING COUNT(*)>=5 ORDER BY total DESC""")
    by_med = [dict(r) for r in cur.fetchall()]
    # Por turno
    cur.execute("""SELECT turn,
        COUNT(*) AS total,
        ROUND(100.0*SUM(CASE WHEN conducta>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_picos,
        ROUND(AVG(CASE WHEN mood='muy_positivo' THEN 4 WHEN mood='positivo' THEN 3
                       WHEN mood='neutro' THEN 2 WHEN mood='negativo' THEN 1 ELSE NULL END)::numeric,2) AS avg_mood
        FROM reports WHERE turn != 'sin especificar' GROUP BY turn ORDER BY turn""")
    by_turn = [dict(r) for r in cur.fetchall()]
    # Con/sin medicación de rescate
    cur.execute("""SELECT
        CASE WHEN LOWER(COALESCE(medicacion,'')) SIMILAR TO
            '%(nolotil|paracetamol|ibuprofeno|diazepam|lorazepam|buscapina|algidol|spasmoctyl|fortasec)%'
            THEN 'Con med. rescate' ELSE 'Sin med. rescate' END AS med_type,
        COUNT(*) AS total,
        ROUND(100.0*SUM(CASE WHEN conducta>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_picos,
        ROUND(AVG(CASE WHEN mood='muy_positivo' THEN 4 WHEN mood='positivo' THEN 3
                       WHEN mood='neutro' THEN 2 WHEN mood='negativo' THEN 1 ELSE NULL END)::numeric,2) AS avg_mood
        FROM reports GROUP BY med_type""")
    by_med_type = [dict(r) for r in cur.fetchall()]
    return jsonify({'by_mediator': by_med, 'by_turn': by_turn, 'by_medication': by_med_type})


@app.route('/api/mediators-summary')
@require_auth
def mediators_summary():
    db = get_db(); cur = db.cursor()
    cur.execute("""
        SELECT mediator,
            COUNT(*) AS total,
            ROUND(AVG(CASE WHEN mood='muy_positivo' THEN 4 WHEN mood='positivo' THEN 3
                           WHEN mood='neutro' THEN 2 WHEN mood='negativo' THEN 1 ELSE NULL END)::numeric,2) AS avg_mood_med,
            ROUND(AVG(
                LEAST(5.0, GREATEST(0.0, (
                  (CASE WHEN mood='muy_positivo' THEN 1.0 WHEN mood='positivo' THEN 0.75
                        WHEN mood='neutro' THEN 0.5 WHEN mood='negativo' THEN 0.0 ELSE 0.5 END)*0.45
                  +(CASE WHEN conducta=0 THEN 1.0 WHEN conducta=1 THEN 0.4 ELSE 0.0 END)*0.35
                  +(CASE WHEN LOWER(COALESCE(medicacion,'')) SIMILAR TO
                    '%(nolotil|paracetamol|ibuprofeno|diazepam|lorazepam|buscapina|algidol|spasmoctyl|fortasec)%'
                    THEN 0.0 ELSE 1.0 END)*0.20
                  -(CASE WHEN conducta>=2 THEN 0.25 ELSE 0.0 END)
                  -(CASE WHEN LOWER(COALESCE(medicacion,'')) SIMILAR TO '%(diazepam|lorazepam)%'
                    THEN 0.10 ELSE 0.0 END)
                )*5.0))
            )::numeric,2) AS avg_estado,
            MIN(date) AS first_date,
            MAX(date) AS last_date
        FROM reports
        WHERE date >= CURRENT_DATE - INTERVAL '6 months'
        GROUP BY mediator
        HAVING COUNT(*) >= 3
        ORDER BY last_date DESC, total DESC
    """)
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        d['first_date'] = d['first_date'].isoformat() if d['first_date'] else None
        d['last_date'] = d['last_date'].isoformat() if d['last_date'] else None
        rows.append(d)
    return jsonify({'mediators': rows})


@app.route('/api/admin/fix-raul-agua', methods=['POST'])
def fix_raul_agua():
    pwd = request.headers.get('X-Admin-Password','')
    if pwd != os.environ.get('ADMIN_PASSWORD','haptica_admin_2025'):
        return jsonify({'error':'No autorizado'}), 401
    db = get_db(); cur = db.cursor()
    cur.execute("""UPDATE reports SET agua=1000
        WHERE agua=1 AND LOWER(mediator) LIKE '%raul%'
        OR agua=1 AND mediator='Raúl Blasco'""")
    updated = cur.rowcount
    db.commit()
    return jsonify({'ok': True, 'updated': updated})


@app.route('/api/admin/schema')
def get_schema():
    pwd = request.headers.get('X-Admin-Password','') or request.args.get('pwd','')
    if pwd != ADMIN_PASSWORD and pwd != API_PASSWORD:
        return jsonify({'error':'No autorizado'}), 401
    try:
        db = psycopg2.connect(DATABASE_URL)
        cur = db.cursor()
        cur.execute("""SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name='reports' 
            ORDER BY ordinal_position""")
        cols = [{'name': r[0], 'type': r[1]} for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM reports")
        count = cur.fetchone()[0]
        db.close()
        return jsonify({'columns': cols, 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/migrate', methods=['GET', 'POST'])
def run_migration():
    pwd = request.headers.get('X-Admin-Password','') or request.args.get('pwd','')
    if pwd != ADMIN_PASSWORD and pwd != API_PASSWORD:
        return jsonify({'error':'No autorizado'}), 401
    try:
        db = psycopg2.connect(DATABASE_URL)
        cur = db.cursor()
        # Añadir columna seq si no existe
        cur.execute("ALTER TABLE reports ADD COLUMN IF NOT EXISTS seq INTEGER DEFAULT 1")
        db.commit()
        # Eliminar índice antiguo sin seq
        try:
            cur.execute("DROP INDEX IF EXISTS reports_date_mediator_turn_key")
            db.commit()
        except: db.rollback()
        try:
            cur.execute("ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_date_mediator_turn_key")
            db.commit()
        except: db.rollback()
        # Crear índice correcto con seq
        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS reports_unique_seq ON reports(date,mediator,turn,seq)")
            db.commit()
        except: db.rollback()
        # Verificar estado
        cur.execute("SELECT indexname FROM pg_indexes WHERE tablename='reports'")
        indexes = [r[0] for r in cur.fetchall()]
        db.close()
        return jsonify({'ok': True, 'indexes': indexes})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/guia')
def descargar_guia():
    import os
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    return send_from_directory(static_dir, 'guia_dashboard.pdf',
                               as_attachment=False,
                               download_name='Guia_Dashboard_Jorge_HAPTICA.pdf')


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
