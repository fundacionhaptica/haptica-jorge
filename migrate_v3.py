"""
migrate_v3.py — Crea la tabla reports_v3 en Railway
Ejecutar una sola vez: python migrate_v3.py
No toca la tabla reports original.
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS reports_v3 (
    -- Identificadores (espejo de reports)
    id              SERIAL PRIMARY KEY,
    source_id       INTEGER REFERENCES reports(id) ON DELETE SET NULL,
    date            DATE NOT NULL,
    mediator        TEXT,
    turn            TEXT,
    seq             INTEGER DEFAULT 1,

    -- Baño e hidratación
    pis             INTEGER,
    caca            INTEGER,
    agua_ml         INTEGER,
    sueno_horas     NUMERIC(4,2),

    -- Conducta desglosada (nuevo en v3)
    estiramientos       INTEGER,
    autoagresiones      INTEGER,
    agresiones_mediador INTEGER,
    agresiones_terceros INTEGER,
    aleteos             INTEGER,

    -- Baño: consistencia deposición
    caca_consistencia TEXT,

    -- Medicación y estado
    medicacion      TEXT,
    estado          TEXT,
    receptividad    TEXT,

    -- Alimentación desglosada por toma (nuevo en v3)
    desayuno        TEXT,
    almuerzo        TEXT,
    comida          TEXT,
    merienda        TEXT,
    cena            TEXT,

    -- Actividad y vocabulario
    actividad       TEXT,
    vocabulario     TEXT,
    observaciones   TEXT,

    -- Metadatos del parseo
    parse_model     TEXT DEFAULT 'gemini-2.0-flash',
    parse_error     TEXT,
    body_preview    TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),

    UNIQUE (date, mediator, turn, seq)
);

CREATE INDEX IF NOT EXISTS idx_v3_date     ON reports_v3(date);
CREATE INDEX IF NOT EXISTS idx_v3_mediator ON reports_v3(mediator);
CREATE INDEX IF NOT EXISTS idx_v3_turn     ON reports_v3(turn);
"""

DROP_TABLE = "DROP TABLE IF EXISTS reports_v3 CASCADE;"


def migrate(drop_first=False):
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL no configurada")

    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    if drop_first:
        print("⚠️  Eliminando tabla reports_v3 existente...")
        cur.execute(DROP_TABLE)

    print("Creando tabla reports_v3...")
    cur.execute(CREATE_TABLE)
    print("✓ Tabla reports_v3 creada (o ya existía)")

    # Añadir columnas nuevas si no existen (para tablas ya creadas)
    new_cols = [
        ("caca_consistencia", "TEXT"),
        ("receptividad", "TEXT"),
    ]
    for col, coltype in new_cols:
        try:
            cur.execute(f"ALTER TABLE reports_v3 ADD COLUMN IF NOT EXISTS {col} {coltype}")
            print(f"✓ Columna {col} añadida (o ya existía)")
        except Exception as e:
            print(f"⚠ {col}: {e}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    import sys
    drop = "--drop" in sys.argv
    if drop:
        confirm = input("¿Seguro que quieres eliminar y recrear reports_v3? (escribe 'si'): ")
        if confirm.strip().lower() != "si":
            print("Cancelado.")
            sys.exit(0)
    migrate(drop_first=drop)
    print("Migración completada.")
