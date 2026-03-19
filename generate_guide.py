#!/usr/bin/env python3
"""
generate_guide.py — Genera la guía PDF del dashboard V3.
Se ejecuta en cada deploy de Railway como release command.
Usa fuente DejaVuSans para soporte Unicode completo de símbolos.
"""
import os, sys

VERSION = "3.1"
BUILD_DATE = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")[:7] or "local"

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    os.system("pip install reportlab --break-system-packages -q")
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

# ── FUENTES con soporte Unicode ───────────────────────────────────────────────
DEJAVU_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans.ttf',
    '/Library/Fonts/DejaVuSans.ttf',
]
DEJAVU_BOLD_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
]

def _reg_font(name, paths):
    for p in paths:
        if os.path.exists(p):
            pdfmetrics.registerFont(TTFont(name, p))
            return True
    return False

USE_DEJAVU = _reg_font('DejaVu', DEJAVU_PATHS) and _reg_font('DejaVuB', DEJAVU_BOLD_PATHS)
FONT_NORMAL = 'DejaVu' if USE_DEJAVU else 'Helvetica'
FONT_BOLD   = 'DejaVuB' if USE_DEJAVU else 'Helvetica-Bold'

# Símbolos Unicode que DejaVu renderiza correctamente
# (sustituyen emojis que no se renderizan bien)
I = {
    'robot':    '[ IA ]',
    'chart':    '►',
    'list':     '◆',
    'chat':     '»',
    'link':     '↔',
    'inbox':    '▼',
    'pencil':   '✎',
    'hospital': '+',
    'report':   '▣',
    'stats':    '≡',
    'warning':  '⚠',
    'info':     'i',
    'ok':       '✓',
    'error':    '✗',
    'bullet':   '•',
    'arrow':    '→',
    'up':       '↑',
    'down':     '↓',
    'star':     '★',
    'orange':   '[C]',   # Cambio
    'red':      '[!]',   # Alerta
    'green':    '[+]',   # Mejora
    'blue':     '[i]',   # Info
    'purple':   '[E]',   # Externo
}

# ── COLORES ───────────────────────────────────────────────────────────────────
TEAL   = colors.HexColor('#2A7F7F')
TEAL2  = colors.HexColor('#1f6060')
PURPLE = colors.HexColor('#7c3aed')
DARK   = colors.HexColor('#1a2332')
GRAY   = colors.HexColor('#6b7280')
GREEN  = colors.HexColor('#16a34a')
RED    = colors.HexColor('#dc2626')
AMBER  = colors.HexColor('#92400e')

# ── ESTILOS ───────────────────────────────────────────────────────────────────
def S(name, **kw):
    kw.setdefault('fontName', FONT_NORMAL)
    return ParagraphStyle(name, **kw)

T_ST = S('T',  fontSize=22, textColor=TEAL2,  fontName=FONT_BOLD,   spaceAfter=6,  alignment=TA_CENTER)
SUB  = S('Su', fontSize=10, textColor=GRAY,   spaceAfter=4,  alignment=TA_CENTER)
VER  = S('Ve', fontSize=9,  textColor=PURPLE, spaceAfter=20, alignment=TA_CENTER, fontName=FONT_BOLD)
H1   = S('H1', fontSize=13, textColor=TEAL2,  fontName=FONT_BOLD,   spaceBefore=14, spaceAfter=5)
H2   = S('H2', fontSize=10, textColor=PURPLE, fontName=FONT_BOLD,   spaceBefore=8,  spaceAfter=3)
BD   = S('BD', fontSize=9,  textColor=DARK,   leading=15, spaceAfter=4, alignment=TA_JUSTIFY)
BUL  = S('BU', fontSize=9,  textColor=DARK,   leading=14, leftIndent=14, spaceAfter=2)
COD  = S('CO', fontSize=8,  textColor=colors.HexColor('#374151'), fontName='Courier',
         backColor=colors.HexColor('#f8fafc'), leading=13, leftIndent=8, spaceBefore=3, spaceAfter=3)
NOT  = S('NO', fontSize=8.5, textColor=AMBER,  leading=13,
         backColor=colors.HexColor('#fef9c3'), leftIndent=8, spaceBefore=3, spaceAfter=3)
TIP  = S('TI', fontSize=8.5, textColor=colors.HexColor('#1e40af'), leading=13,
         backColor=colors.HexColor('#eff6ff'), leftIndent=8, spaceBefore=3, spaceAfter=3)
OK_S = S('OK', fontSize=8.5, textColor=colors.HexColor('#14532d'), leading=13,
         backColor=colors.HexColor('#f0fdf4'), leftIndent=8, spaceBefore=3, spaceAfter=3)

def h1(t):   return [Paragraph(t, H1), HRFlowable(width='100%', thickness=1.5, color=TEAL, spaceAfter=5)]
def h2(t):   return [Paragraph(t, H2)]
def p(t):    return [Paragraph(t, BD)]
def bul(t):  return [Paragraph(I['bullet'] + ' ' + t, BUL)]
def note(t): return [Paragraph(I['warning'] + '  ' + t, NOT)]
def tip(t):  return [Paragraph(I['info'] + '  ' + t, TIP)]
def ok(t):   return [Paragraph(I['ok'] + '  ' + t, OK_S)]
def sp(n=6): return [Spacer(1, n)]

def tbl(rows, widths=None, has_header=True):
    if not widths: widths = [5*cm, 11*cm]
    t = Table(rows, colWidths=widths, hAlign='LEFT')
    style = [
        ('FONTNAME',     (0,0), (-1,-1), FONT_NORMAL),
        ('FONTSIZE',     (0,0), (-1,-1), 8.5),
        ('VALIGN',       (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING',   (0,0), (-1,-1), 5),
        ('BOTTOMPADDING',(0,0), (-1,-1), 5),
        ('LEFTPADDING',  (0,0), (-1,-1), 7),
        ('GRID',         (0,0), (-1,-1), 0.4, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS',(0,0),(-1,-1), [colors.white, colors.HexColor('#f9fafb')]),
    ]
    if has_header and rows:
        style += [
            ('BACKGROUND',  (0,0), (-1,0), TEAL2),
            ('TEXTCOLOR',   (0,0), (-1,0), colors.white),
            ('FONTNAME',    (0,0), (-1,0), FONT_BOLD),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor('#f9fafb')]),
        ]
    t.setStyle(TableStyle(style))
    return t

# ── CONTENIDO ─────────────────────────────────────────────────────────────────
def build_guide(output_path: str):
    from datetime import datetime
    now = datetime.now().strftime('%B %Y')
    story = []

    # PORTADA
    story += [
        Spacer(1, 2*cm),
        Paragraph('Dashboard Jorge V3', T_ST),
        Paragraph('Fundacion HAPTICA  |  Guia de usuario', SUB),
        Paragraph(f'Version {VERSION}  |  Generada automaticamente  |  {now}', VER),
        HRFlowable(width='50%', thickness=2, color=PURPLE, hAlign='CENTER', spaceAfter=12),
        Paragraph('https://fundacion-haptica-informes.up.railway.app/dashboard',
                  S('url', fontSize=9, textColor=PURPLE, alignment=TA_CENTER, spaceAfter=6)),
        Paragraph('Contrasena de acceso: haptica2025',
                  S('pw', fontSize=9, textColor=GRAY, alignment=TA_CENTER)),
        Spacer(1, 1*cm),
    ]

    # 1. QUE ES V3
    story += h1('1. Que es la V3')
    story += p('La V3 es la version avanzada del dashboard de seguimiento de Jorge que anade inteligencia artificial. Usa <b>Gemini Flash 2.0</b> de Google para leer el texto libre de cada informe y extraer campos detallados y precisos.')
    story += sp(4)
    story += [tbl([
        ['', 'V1 (version base)', 'V3 (este dashboard)'],
        ['Parser', 'Regex (reglas fijas)', 'IA con Gemini Flash 2.0'],
        ['Conducta', 'Solo numero total de picos', '4 tipos: autoagresiones, agres. mediador, agres. terceros, aleteos'],
        ['Alimentacion', 'Campo libre "comidas"', 'Desayuno / Almuerzo / Comida / Merienda / Cena separados'],
        ['Sueno', 'No disponible', 'Horas decimales (ej: 7.5h)'],
        ['Agua', 'A veces "1" en lugar de 1000ml', 'Siempre en mililitros'],
        ['Guia', 'Estatica', 'Se regenera automaticamente en cada deploy'],
    ], widths=[3.2*cm, 5.9*cm, 6.9*cm])]
    story += sp()

    # 2. ACCESO
    story += h1('2. Acceso')
    story += [tbl([
        ['URL', 'https://fundacion-haptica-informes.up.railway.app/dashboard'],
        ['Contrasena acceso', 'haptica2025'],
        ['Contrasena admin', 'hapticaadmin2025'],
        ['Repo GitHub', 'fundacionhaptica/haptica-jorge (rama v3)'],
    ], has_header=False)]
    story += sp()

    # 3. PESTANAS
    story += h1('3. Pestanas del dashboard')
    story += [tbl([
        ['Pestana', 'Contenido'],
        ['Resumen', 'KPIs, grafico de evolucion mensual del estado medio (0-5) con scroll horizontal, hidratacion, conducta y tabla de mediadores activos.'],
        ['Informes', 'Listado completo filtrable por anyo. Expandible con todos los campos del informe.'],
        ['Vocabulario', 'Nube de palabras top-80 y ranking top-25. Actividades normalizadas.'],
        ['Correlaciones', 'Picos de conducta y animo por mediador, turno y medicacion de rescate.'],
        ['Conducta detallada', 'Datos V3 (IA): cobertura del reparseo, grafico de los 4 tipos de conducta, tabla mensual y alimentacion por tomas.'],
        ['Historial subidas', 'Log de importaciones: fecha, rango de datos, nuevos insertados y duplicados.'],
    ])]
    story += sp()

    # 4. ESTADO MEDIO
    story += h1('4. Estado medio (0-5)')
    story += p('Score ponderado objetivo que combina multiples variables. <b>No es la valoracion subjetiva del mediador</b> sino un calculo automatico:')
    story += sp(4)
    story += [tbl([
        ['Componente', 'Peso', 'Criterio'],
        ['Animo del mediador', '45%', 'Muy positivo=1.0  |  Positivo=0.75  |  Neutro=0.5  |  Negativo=0.0'],
        ['Ausencia de conducta', '35%', 'Sin picos=1.0  |  1 pico=0.4  |  2+ picos=0.0'],
        ['Sin medicacion rescate', '20%', 'Sin rescate=1.0  |  Con rescate=0.0'],
        ['Hidratacion+bano', '10%*', '*Solo si hay datos. Si no, redistribuye entre los 3 anteriores.'],
    ], widths=[4.5*cm, 2*cm, 9.5*cm])]
    story += sp(4)
    story += p('<b>Penalizaciones:</b> -0.25 si 2+ picos de conducta  |  -0.10 si diazepam o lorazepam. Resultado acotado a [0, 5].')
    story += tip('El grafico de evolucion tiene scroll horizontal. Arrastra hacia la izquierda para ver meses anteriores. Se posiciona automaticamente en los datos mas recientes.')
    story += sp()

    # 5. IMPORTAR DATOS
    story += h1('5. Importar datos nuevos')
    story += p('Boton <b>Actualizar datos</b> en la cabecera. Acepta archivos .txt exportados de WhatsApp.')
    for s in [
        'Abre el chat del grupo de mediadores en WhatsApp',
        'Toca el menu (tres puntos) -> "Mas" -> "Exportar chat" -> "Sin archivos multimedia"',
        'Guarda el archivo .txt y subelo desde el dashboard',
        'Los informes nuevos se insertan automaticamente. Los duplicados se ignoran.',
        'Si GEMINI_API_KEY esta configurada, el parseo V3 se lanza en segundo plano para los nuevos.',
    ]:
        story += bul(s)
    story += sp(4)
    story += note('El dashboard lee el archivo localmente antes de enviarlo, lo que evita errores de conexion en movil con archivos grandes.')
    story += sp()

    # 6. PARSEO IA
    story += h1('6. Parseo IA con Gemini (V3)')
    story += p('Cada informe nuevo subido se parsea automaticamente con Gemini en segundo plano. El reparseo completo del historico se lanza desde el panel de Entrenamiento IA.')
    story += h2('Campos nuevos en V3')
    story += [tbl([
        ['Campo', 'Descripcion'],
        ['autoagresiones', 'Episodios donde Jorge se hace dano a si mismo'],
        ['agresiones_mediador', 'Episodios de agresion al mediador'],
        ['agresiones_terceros', 'Agresiones a otras personas'],
        ['aleteos', 'Agitacion sin agresion fisica (balanceo, gritos, aleteo de brazos)'],
        ['desayuno / almuerzo / comida / merienda / cena', 'Contenido de cada toma por separado'],
        ['sueno_horas', 'Horas de sueno como decimal (ej: 7.5)'],
        ['agua_ml', 'Agua siempre en mililitros'],
        ['vocabulario', 'Palabras o signos nuevos (texto libre)'],
    ], widths=[5.5*cm, 10.5*cm])]
    story += sp()

    # 7. ENTRENAMIENTO IA
    story += h1('7. Entrenamiento IA')
    story += p('Boton <b>Entrenamiento IA</b> en la cabecera. Panel con 4 secciones:')
    story += sp(4)
    story += [tbl([
        ['Seccion', 'Funcion'],
        ['Correcciones', 'Busca un informe, revisa lo que interpreto la IA, corrige los errores y guardalos en BD. Cada correccion validada se usa automaticamente en los proximos parseos (few-shot learning).'],
        ['Docs medicos', 'Sube PDFs o imagenes de informes clinicos. Gemini extrae diagnosticos, medicacion, patrones de conducta y recomendaciones. Se usan en los informes mensuales.'],
        ['Informe mensual', 'Genera un analisis completo del mes: resumen ejecutivo, conducta, bienestar fisico, tendencias y prediccion del proximo mes con nivel de riesgo y recomendaciones.'],
        ['Estado IA', 'Estadisticas: correcciones totales, validadas, pendientes y cobertura del parseo V3.'],
    ])]
    story += sp(4)
    story += tip('Valida las correcciones (boton Validar) para que entren en el pool de few-shot. Los ultimos 10 ejemplos validados se inyectan en cada parseo.')
    story += sp()

    # 8. INFORME MENSUAL
    story += h1('8. Informe mensual con prediccion')
    story += p('En Entrenamiento IA -> Informe mensual. Selecciona anyo y mes y pulsa <b>Generar informe</b>.')
    story += p('El informe incluye: resumen ejecutivo, estado general con tendencia, analisis de conducta con patron temporal, bienestar fisico (hidratacion, sueno, alimentacion), y <b>prediccion del proximo mes</b> con nivel de riesgo (bajo/medio/alto), factores relevantes y recomendaciones concretas para el equipo.')
    story += note('Si hay documentos medicos subidos o una guia de mediacion cargada, el informe los usa como contexto clinico adicional.')
    story += sp()

    # 9. DOCUMENTOS MEDICOS
    story += h1('9. Documentos medicos')
    story += p('En Entrenamiento IA -> Docs medicos. Acepta PDFs e imagenes (JPG, PNG, WEBP).')
    story += p('Gemini extrae: tipo de documento, fecha, especialidad, diagnosticos, medicacion actual, observaciones de conducta, patrones relevantes y recomendaciones. Este contexto enriquece los informes mensuales y las predicciones.')
    story += sp()

    # 10. FILTROS
    story += h1('10. Filtros de la barra lateral')
    story += [tbl([
        ['Turno', 'Todos / Manana / Tarde / Noche'],
        ['Mediador/a', 'Lista desplegable con todos los mediadores'],
        ['Estado de animo', 'Muy positivo / Positivo / Neutro / Negativo'],
        ['Conducta', 'Con picos / Sin picos'],
        ['Rango de fechas', 'Fecha inicio y fecha fin'],
    ], has_header=False)]
    story += sp()

    # 11. ANOTACIONES
    story += h1('11. Anotaciones en el grafico')
    story += p('Boton <b>Anotaciones</b> en la cabecera. Anade marcadores verticales en el grafico de evolucion.')
    story += [tbl([
        ['Naranja (C)', 'Cambio de medicacion, cambio de rutina'],
        ['Rojo (!)', 'Hospitalizacion, periodo de alta dificultad'],
        ['Verde (+)', 'Inicio de mejora sostenida, logro significativo'],
        ['Azul (i)', 'Incorporacion de mediador, informacion general'],
        ['Morado (E)', 'Evento externo (COVID, vacaciones, cambio de centro)'],
    ], has_header=False)]
    story += sp()

    # 12. API
    story += h1('12. Endpoints API principales')
    story += p('Todos requieren header <b>X-Password: haptica2025</b>. Los de admin requieren <b>X-Admin-Password: hapticaadmin2025</b>.')
    story += [tbl([
        ['Endpoint', 'Metodo', 'Descripcion'],
        ['/api/stats', 'GET', 'KPIs + datos mensuales'],
        ['/api/reports', 'GET', 'Listado con filtros'],
        ['/api/upload-text', 'POST', 'Importar chat (JSON con texto, recomendado movil)'],
        ['/api/upload', 'POST', 'Importar chat (multipart)'],
        ['/api/v3/conducta', 'GET', 'Evolucion mensual 4 tipos de conducta'],
        ['/api/v3/alimentacion', 'GET', 'Informes con desglose por toma'],
        ['/api/v3/reparse-all', 'POST', 'Lanza reparseo masivo en background'],
        ['/api/v3/reparse-status', 'GET', 'Estado del reparseo (%)'],
        ['/api/training/corrections', 'GET/POST', 'Correcciones de entrenamiento'],
        ['/api/medical/upload', 'POST', 'Subir documento medico'],
        ['/api/medical/documents', 'GET', 'Listar documentos medicos'],
        ['/api/monthly-report', 'POST', 'Generar informe mensual con IA'],
        ['/api/admin/migrate-v3', 'POST', 'Crear tabla reports_v3'],
        ['/guia', 'GET', 'Descargar esta guia (regenerada en cada deploy)'],
    ], widths=[5*cm, 2.2*cm, 8.8*cm])]
    story += sp()

    # 13. STACK
    story += h1('13. Stack tecnico')
    story += [tbl([
        ['Backend', 'Flask (Python) — app.py'],
        ['Frontend', 'HTML/JS con Chart.js — index.html (responsive PC y movil)'],
        ['Parser V1', 'parser.py — regex'],
        ['Parser V3', 'parser_v3.py — Gemini Flash 2.0 con few-shot learning'],
        ['Base de datos', 'PostgreSQL en Railway — reports, reports_v3, training_corrections, medical_documents'],
        ['Deploy', 'Railway — auto-deploy en push a rama v3'],
        ['Guia', 'generate_guide.py — regenerada automaticamente en cada deploy'],
        ['Repo', 'fundacionhaptica/haptica-jorge (rama v3)'],
    ], has_header=False)]
    story += sp()

    # 14. PENDIENTES
    story += h1('14. Tareas pendientes')
    for s in [
        I['warning'] + '  Ejecutar correccion agua Raul via /api/admin/fix-raul-agua (~126 registros agua=1 a 1000ml)',
        I['robot'] + '  Lanzar reparseo masivo V3 desde admin_v3.html para poblar la pestana Conducta detallada',
        '-  Anadir grafico de evolucion de sueno (sueno_horas) en la pestana Conducta detallada',
        '-  Integrar datos V3 en el calculo del Estado medio',
        '-  Subir guia de mediacion V6 para enriquecer los informes mensuales con IA',
    ]:
        story += [Paragraph(s, BUL)]

    # GENERAR PDF
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title=f'Guia Dashboard Jorge V3 - Fundacion HAPTICA v{VERSION}',
        author='Fundacion HAPTICA',
    )
    doc.build(story)
    print(f"Guia generada: {output_path} (v{VERSION}, build {BUILD_DATE})")
    return True


if __name__ == '__main__':
    output = sys.argv[1] if len(sys.argv) > 1 else 'static/guia_dashboard.pdf'
    try:
        build_guide(output)
    except Exception as e:
        print(f"Error generando guia: {e}")
        import traceback; traceback.print_exc()
        sys.exit(0)  # No bloquear el deploy
