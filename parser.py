"""
Parser de WhatsApp para informes de Jorge.
Acepta formato [D/M/YY, HH:MM:SS] y [DD/MM/YYYY, HH:MM:SS]
"""
import re
from datetime import datetime

# ── REGEX UNIVERSAL ────────────────────────────────────────────────────────────
MSG_RE = re.compile(
    r'\[(\d{1,2})\/(\d{1,2})\/(\d{2,4}),\s*\d{1,2}:\d{2}(?::\d{2})?\]\s*([^:]+):\s*([\s\S]*?)(?=\[\d{1,2}\/\d{1,2}\/\d{2,4},|$)'
)

MEDIATORS = {
    'raquel','eva','irene','ainhoa','franklin','adri','blanca','carmen',
    'elena','sophie','javier','luna','alba','karol','amalia','dulce','paula',
    'raúl','raul','ari','jeach','belen','belén','gregorioalexander','gregory',
    'eli','angela','ángela','mediadora','mediador','juanjo','nerea','sara',
    'marta','andres','andrés','pablo','jorge mediador','mapi'
}

MOOD_MAP = {
    'muy positivo':'muy_positivo','muy_positivo':'muy_positivo','muyp':'muy_positivo',
    'positivo':'positivo','pos':'positivo',
    'neutro':'neutro','neutral':'neutro',
    'negativo':'negativo','neg':'negativo',
    'muy negativo':'negativo',
}

def is_mediator(name: str) -> bool:
    n = name.lower().strip().lstrip('~').strip()
    return any(m in n for m in MEDIATORS)

def normalize_year(y: str) -> str:
    return ('20' + y) if len(y) == 2 else y

def extract_int(text: str, *patterns) -> int | None:
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            try:
                return int(m.group(1))
            except (ValueError, IndexError):
                pass
    return None

def extract_mood(body: str) -> str:
    patterns = [
        r'#\s*ESTADO\s*DE\s*[AÁ]NIMO[:\s]*([^\n#]+)',
        r'estado\s*de\s*[aá]nimo[:\s]*([^\n]+)',
        r'#\s*[AÁ]NIMO[:\s]*([^\n#]+)',
    ]
    for p in patterns:
        m = re.search(p, body, re.I)
        if m:
            val = m.group(1).strip().lower()
            for k, v in MOOD_MAP.items():
                if k in val:
                    return v
            # Fallback numérico
            nm = re.search(r'(\d+)', val)
            if nm:
                n = int(nm.group(1))
                if n >= 8: return 'muy_positivo'
                if n >= 6: return 'positivo'
                if n >= 4: return 'neutro'
                return 'negativo'
    # Heurística v1
    bl = body.lower()
    if any(w in bl for w in ['muy positivo','muy contento','excelente','genial','fantástico']): return 'muy_positivo'
    if any(w in bl for w in ['positivo','contento','bien','alegre','tranquilo']): return 'positivo'
    if any(w in bl for w in ['negativo','agitado','triste','llorando','enfadado','agresivo']): return 'negativo'
    if any(w in bl for w in ['neutro','normal','regular']): return 'neutro'
    return '?'

def extract_turn(body: str, sender: str) -> str:
    bl = body.lower()
    patterns = [
        r'#?\s*turno[:\s]*([^\n]+)',
        r'(mañana|tarde|noche)\)',
        r'\((mañana|tarde|noche)\)',
    ]
    for p in patterns:
        m = re.search(p, bl, re.I)
        if m:
            t = m.group(1).strip().lower()
            if 'ma' in t: return 'mañana'
            if 'tar' in t: return 'tarde'
            if 'noch' in t: return 'noche'
    return 'sin especificar'

def extract_conducta(body: str) -> int:
    m = extract_int(body,
        r'#\s*PICOS[^:\n]*:\s*\*?\s*Nr\.?\s*Veces[:\s]*(\d+)',
        r'picos[^:\n]*:\s*(\d+)',
        r'autoagresi[oó]n[^:\n]*:\s*(\d+)',
    )
    if m is not None: return m
    bl = body.lower()
    if re.search(r'autoagresi[oó]n[:\s]*s[ií]', bl): return 1
    if re.search(r'autoagresi[oó]n[:\s]*no', bl): return 0
    return 0

def extract_agua(body: str) -> int | None:
    # ml primero (más específico)
    m = re.search(r'agua[=:\s]*(\d+)\s*ml', body, re.I)
    if m: return int(m.group(1))
    m = re.search(r'(\d+)\s*ml\s*(?:de\s*)?agua', body, re.I)
    if m: return int(m.group(1))
    m = re.search(r'#\s*AGUA[=:\s]*\*?\s*(\d+)', body, re.I)
    if m: return int(m.group(1))
    # Litros: acepta = o : como separador (Raúl escribe "Agua=1l")
    m = re.search(r'agua[=:\s]*(\d+(?:[.,]\d+)?)\s*l(?:itros?)?\b', body, re.I)
    if m: return round(float(m.group(1).replace(',','.')) * 1000)
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*l(?:itros?)?\s*(?:de\s*)?agua', body, re.I)
    if m: return round(float(m.group(1).replace(',','.')) * 1000)
    return None

def extract_pis(body: str) -> int | None:
    return extract_int(body,
        r'#\s*PIS[^:\n]*\*?\s*Nr\.?\s*Veces[:\s]*(\d+)',
        r'pis[:\s]*(\d+)\s*vez',
        r'(\d+)\s*veces[^\n]*pis',
    )

def extract_section(body: str, *headers) -> str:
    for h in headers:
        m = re.search(rf'#\s*{h}[:\s]*\n?([\s\S]*?)(?=#\s*[A-ZÁÉÍÓÚ]|\Z)', body, re.I)
        if m:
            return m.group(1).strip()
    return ''

def extract_vocab(body: str) -> list[str]:
    m = re.search(r'(?:vocabulario|vocab)[:\s]*\n?([\s\S]*?)(?=#\s*[A-ZÁÉÍÓÚ]|\Z)', body, re.I)
    if not m: return []
    raw = m.group(1)
    words = re.findall(r'[-•*]\s*(.+)', raw)
    if not words:
        words = [w.strip() for w in re.split(r'[,;/\n]+', raw) if w.strip() and len(w.strip()) > 1]
    return [w.strip().strip('.-•*').strip() for w in words if w.strip()][:30]

def extract_meds(body: str) -> str:
    m = re.search(r'#\s*MEDICACI[OÓ]N[:\s]*\n?([\s\S]*?)(?=#\s*[A-ZÁÉÍÓÚ]|\Z)', body, re.I)
    return m.group(1).strip() if m else ''

def detect_format(body: str) -> str:
    has_hash = bool(re.search(r'#\s*[A-ZÁÉÍÓÚ]+', body))
    has_hashtag_estado = bool(re.search(r'#\s*ESTADO', body, re.I))
    return 'v2' if (has_hash and has_hashtag_estado) else 'v1'

def parse_report(date_str: str, sender: str, body: str) -> dict:
    """Convierte un mensaje en un dict estructurado."""
    fmt = detect_format(body)
    turn = extract_turn(body, sender)
    return {
        'date':       date_str,           # YYYY-MM-DD
        'mediator':   sender.strip(),
        'turn':       turn,
        'mood':       extract_mood(body),
        'conducta':   extract_conducta(body),
        'estiramientos': extract_int(body,
            r'#\s*ESTIRAMIENTOS[^:\n]*\*?\s*Nr\.?\s*Veces[:\s]*(\d+)',
            r'estiramientos[:\s]*(\d+)') or 0,
        'agua':       extract_agua(body),
        'pis':        extract_pis(body),
        'banyo':      extract_section(body, 'BA[ÑN]O'),
        'estado':     extract_section(body, 'ESTADO', 'OBSERVACIONES'),
        'comunicacion': extract_section(body, 'COMUNICACI[OÓ]N'),
        'actividades': extract_section(body, 'ACTIVIDADES', 'ACTIVIDAD'),
        'comidas':    extract_section(body, 'COMIDAS?', 'ALIMENTACI[OÓ]N'),
        'medicacion': extract_meds(body),
        'notas':      extract_section(body, 'NOTAS?', 'OBSERVACIONES'),
        'vocab':      extract_vocab(body),
        'formato':    fmt,
        'body_preview': body[:300],
    }

def parse_whatsapp(text: str) -> list[dict]:
    """Parsea un export de WhatsApp completo y devuelve lista de informes."""
    reports = []
    for m in MSG_RE.finditer(text):
        dd, mm, yy = m.group(1), m.group(2), m.group(3)
        sender = m.group(4).lstrip('\u200e').replace('~', '').strip()
        body = m.group(5).strip()

        if not is_mediator(sender): continue
        if len(body) < 80: continue
        if any(x in body.lower() for x in ['omitido', 'omitida', 'image omitted', 'video omitted']): continue

        yyyy = normalize_year(yy)
        date_str = f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"

        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            continue

        reports.append(parse_report(date_str, sender, body))

    return reports
