#!/usr/bin/env python3
import os, json, psycopg2

DB = os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_PRIVATE_URL')
if not DB:
    print("ERROR: No DATABASE_URL"); exit(1)

db = psycopg2.connect(DB)
cur = db.cursor()

cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='reports'")
table_exists = cur.fetchone()[0] > 0

if table_exists:
    cur.execute("SELECT COUNT(*) FROM reports")
    n = cur.fetchone()[0]
    print(f"Registros actuales: {n}")
    if n > 100:
        print("BD ya tiene datos, saliendo"); exit(0)

print("Recreando tabla reports con seq...")
cur.execute("DROP TABLE IF EXISTS reports CASCADE")
cur.execute("""CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    mediator TEXT NOT NULL,
    turn TEXT DEFAULT 'sin especificar',
    seq INTEGER DEFAULT 1,
    mood TEXT DEFAULT '?',
    conducta INTEGER DEFAULT 0,
    estiramientos INTEGER DEFAULT 0,
    agua INTEGER, pis INTEGER,
    banyo TEXT DEFAULT '', estado TEXT DEFAULT '',
    comunicacion TEXT DEFAULT '', actividades TEXT DEFAULT '',
    comidas TEXT DEFAULT '', medicacion TEXT DEFAULT '',
    notas TEXT DEFAULT '', vocab JSONB DEFAULT '[]',
    formato TEXT DEFAULT 'v1', body_preview TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, mediator, turn, seq)
)""")
cur.execute("CREATE INDEX idx_reports_date ON reports(date)")
cur.execute("CREATE INDEX idx_reports_mediator ON reports(mediator)")
db.commit()
print("✅ Tabla creada")

with open('seed.json', encoding='utf-8') as f:
    data = json.load(f)

print(f"Insertando {len(data)} registros...")
inserted = errors = 0
for r in data:
    try:
        cur.execute("""INSERT INTO reports
            (date,mediator,turn,seq,mood,conducta,estiramientos,agua,pis,
             banyo,estado,comunicacion,actividades,comidas,medicacion,
             notas,vocab,formato,body_preview)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (date,mediator,turn,seq) DO NOTHING""",
            (r.get('date'), r.get('mediator',''), r.get('turn','sin especificar'),
             r.get('seq',1), r.get('mood','?'), r.get('conducta',0),
             r.get('estiramientos',0), r.get('agua'), r.get('pis'),
             r.get('banyo',''), r.get('estado',''), r.get('comunicacion',''),
             r.get('actividades',''), r.get('comidas',''), r.get('medicacion',''),
             r.get('notas',''), json.dumps(r.get('vocab',[]), ensure_ascii=False),
             r.get('formato','v1'), r.get('body_preview','')[:300]))
        if cur.rowcount > 0: inserted += 1
    except Exception as e:
        errors += 1
        if errors <= 5: print(f"  ERROR fila {errors}: {e}")
        db.rollback()

db.commit()
cur.close(); db.close()
print(f"✅ Resultado: {inserted} insertados, {errors} errores de {len(data)} total")
