#!/usr/bin/env python3
"""Script de carga inicial - se ejecuta una vez en Railway"""
import os, json, psycopg2

DB = os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_PRIVATE_URL')
if not DB:
    print("ERROR: No DATABASE_URL"); exit(1)

db = psycopg2.connect(DB)
cur = db.cursor()

# Ver cuántos hay
cur.execute("SELECT COUNT(*) FROM reports")
n = cur.fetchone()[0]
print(f"Registros actuales: {n}")

if n > 100:
    print("BD ya tiene datos, nada que hacer"); exit(0)

# Añadir seq si no existe — verificar primero
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='reports' AND column_name='seq'")
has_seq = cur.fetchone() is not None
print(f"Columna seq existe: {has_seq}")
if not has_seq:
    cur.execute("ALTER TABLE reports ADD COLUMN seq INTEGER DEFAULT 1")
    db.commit()
    print("✅ Columna seq añadida")

# Borrar constraints viejos
for constraint in ['reports_date_mediator_turn_key', 'reports_date_mediator_turn_seq_key']:
    try:
        cur.execute(f"ALTER TABLE reports DROP CONSTRAINT IF EXISTS {constraint}")
        db.commit()
    except: db.rollback()

# Crear índice único correcto
try:
    cur.execute("DROP INDEX IF EXISTS reports_unique_seq")
    cur.execute("CREATE UNIQUE INDEX reports_unique_seq ON reports(date,mediator,turn,seq)")
    db.commit()
    print("✅ Índice único creado")
except Exception as e:
    db.rollback()
    print(f"Índice: {e}")

# Cargar seed
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
        if errors <= 3: print(f"  ERROR: {e} | {r.get('date')} {r.get('mediator')}")
        db.rollback()

db.commit()
cur.close(); db.close()
print(f"✅ Insertados: {inserted}, Errores: {errors}")
