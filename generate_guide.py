#!/usr/bin/env python3
"""
generate_guide.py — Genera la guía PDF del dashboard V3 automáticamente.
Se ejecuta en cada deploy de Railway como release command.
La guía refleja siempre el estado actual del sistema.
"""
import os, sys

# Versión del sistema — incrementar manualmente cuando haya cambios mayores
VERSION = "3.1"
BUILD_DATE = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")[:7] or "local"

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
except ImportError:
    print("reportlab no disponible — instalando...")
    os.system("pip install reportlab --break-system-packages -q")
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

# ── ESTILOS ────────────────────────────────────────────────────────────────────
TEAL   = colors.HexColor('#2A7F7F')
TEAL2  = colors.HexColor('#1f6060')
PURPLE = colors.HexColor('#7c3aed')
ORANGE = colors.HexColor('#E8833A')
DARK   = colors.HexColor('#1a2332')
GRAY   = colors.HexColor('#6b7280')
GREEN  = colors.HexColor('#16a34a')
RED    = colors.HexColor('#dc2626')

def S(name, **kw): return ParagraphStyle(name, **kw)

T   = S('T',  fontSize=22, textColor=TEAL2,  fontName='Helvetica-Bold', spaceAfter=6,  alignment=TA_CENTER)
SUB = S('Su', fontSize=10, textColor=GRAY,   spaceAfter=4,  alignment=TA_CENTER)
VER = S('Ve', fontSize=9,  textColor=PURPLE, spaceAfter=20, alignment=TA_CENTER, fontName='Helvetica-Bold')
H1  = S('H1', fontSize=13, textColor=TEAL2,  fontName='Helvetica-Bold', spaceBefore=14, spaceAfter=5)
H2  = S('H2', fontSize=10, textColor=PURPLE, fontName='Helvetica-Bold', spaceBefore=8,  spaceAfter=3)
BD  = S('BD', fontSize=9,  textColor=DARK,   leading=15, spaceAfter=4, alignment=TA_JUSTIFY)
BUL = S('BU', fontSize=9,  textColor=DARK,   leading=14, leftIndent=14, spaceAfter=2)
COD = S('CO', fontSize=8,  textColor=colors.HexColor('#374151'), fontName='Courier',
        backColor=colors.HexColor('#f8fafc'), leading=13, leftIndent=8, spaceBefore=3, spaceAfter=3)
NOT = S('NO', fontSize=8.5, textColor=colors.HexColor('#92400e'), leading=13,
        backColor=colors.HexColor('#fef9c3'), leftIndent=8, spaceBefore=3, spaceAfter=3)
TIP = S('TI', fontSize=8.5, textColor=colors.HexColor('#1e40af'), leading=13,
        backColor=colors.HexColor('#eff6ff'), leftIndent=8, spaceBefore=3, spaceAfter=3)
OK  = S('OK', fontSize=8.5, textColor=colors.HexColor('#14532d'), leading=13,
        backColor=colors.HexColor('#f0fdf4'), leftIndent=8, spaceBefore=3, spaceAfter=3)

def h1(t):   return [Paragraph(t, H1), HRFlowable(width='100%', thickness=1.5, color=TEAL, spaceAfter=5)]
def h2(t):   return [Paragraph(t, H2)]
def p(t):    return [Paragraph(t, BD)]
def bul(t):  return [Paragraph('• ' + t, BUL)]
def cod(t):  return [Paragraph(t, COD)]
def note(t): return [Paragraph('⚠️  ' + t, NOT)]
def tip(t):  return [Paragraph('💡  ' + t, TIP)]
def ok(t):   return [Paragraph('✅  ' + t, OK)]
def sp(n=6): return [Spacer(1, n)]

def tbl(rows, widths=None, has_header=True):
    if not widths: widths = [5*cm, 11*cm]
    t = Table(rows, colWidths=widths, hAlign='LEFT')
    style = [
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
            ('FONTNAME',    (0,0), (-1,0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor('#f9fafb')]),
        ]
    t.setStyle(TableStyle(style))
    return t

def build_guide(output_path: str):
    story = []
    from datetime import datetime
    now = datetime.now().strftime('%B %Y')

    # ── PORTADA ────────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 2*cm),
        Paragraph('🤖', S('em', fontSize=40, alignment=TA_CENTER, spaceAfter=8)),
        Paragraph('Dashboard Jorge V3', T),
        Paragraph('Fundación HÁPTICA · Guía de usuario', SUB),
        Paragraph(f'Versión {VERSION} · Generada automáticamente · {now}', VER),
        HRFlowable(width='50%', thickness=2, color=PURPLE, hAlign='CENTER', spaceAfter=12),
        Paragraph('https://fundacion-haptica-informes.up.railway.app/dashboard',
                  S('url', fontSize=9, textColor=PURPLE, alignment=TA_CENTER, spaceAfter=6)),
        Paragraph('Contraseña: haptica2025',
                  S('pw', fontSize=9, textColor=GRAY, alignment=TA_CENTER)),
        Spacer(1, 1*cm),
    ]

    # ── 1. QUÉ ES LA V3 ───────────────────────────────────────────────────────
    story += h1('1. ¿Qué es la V3?')
    story += p('La V3 es la versión avanzada del dashboard de seguimiento de Jorge que añade inteligencia artificial. Usa <b>Gemini Flash 2.0</b> de Google para leer el texto libre de cada informe y extraer campos detallados y precisos.')
    story += sp(4)
    story += [tbl([
        ['', 'V1 (versión base)', 'V3 (este dashboard)'],
        ['Parser', 'Regex — reglas fijas', 'IA — Gemini Flash 2.0'],
        ['Conducta', 'Solo nº total de picos', '4 tipos: autoagresiones, agres. mediador, agres. terceros, aleteos'],
        ['Alimentación', 'Campo libre "comidas"', 'Desayuno / Almuerzo / Comida / Merienda / Cena separados'],
        ['Sueño', 'No disponible', 'Horas decimales (ej: 7.5h)'],
        ['Agua', 'A veces "1" en lugar de 1000ml', 'Siempre en mililitros'],
        ['Guía', 'Manual estática', 'Se regenera automáticamente en cada deploy'],
    ], widths=[3.2*cm, 5.9*cm, 6.9*cm])]
    story += sp()

    # ── 2. ACCESO ──────────────────────────────────────────────────────────────
    story += h1('2. Acceso')
    story += [tbl([
        ['URL', 'https://fundacion-haptica-informes.up.railway.app/dashboard'],
        ['Contraseña acceso', 'haptica2025'],
        ['Contraseña admin', 'hapticaadmin2025'],
        ['Repo GitHub', 'fundacionhaptica/haptica-jorge (rama v3)'],
    ], has_header=False)]
    story += sp()

    # ── 3. PESTAÑAS ────────────────────────────────────────────────────────────
    story += h1('3. Pestañas del dashboard')
    story += [tbl([
        ['Pestaña', 'Contenido'],
        ['📊 Resumen', 'KPIs, gráfico de evolución mensual del estado medio (0-5) con scroll, hidratación, conducta y tabla de mediadores activos.'],
        ['📋 Informes', 'Listado completo filtrable por año. Expandible con todos los campos del informe.'],
        ['💬 Vocabulario', 'Nube de palabras top-80 y ranking top-25. Actividades normalizadas.'],
        ['🔗 Correlaciones', 'Picos de conducta y ánimo por mediador, turno y medicación de rescate.'],
        ['📊 Conducta detallada', 'Datos V3 (IA): cobertura, gráfico de los 4 tipos de conducta, tabla mensual y alimentación por tomas.'],
        ['📥 Historial subidas', 'Log de importaciones: fecha, rango de datos, nuevos insertados y duplicados.'],
    ])]
    story += sp()

    # ── 4. ESTADO MEDIO ────────────────────────────────────────────────────────
    story += h1('4. Estado medio (0–5)')
    story += p('Score ponderado objetivo que combina múltiples variables. <b>No es la valoración subjetiva del mediador</b> sino un cálculo automático:')
    story += sp(4)
    story += [tbl([
        ['Componente', 'Peso', 'Criterio'],
        ['Ánimo del mediador', '45%', 'Muy positivo→1.0 · Positivo→0.75 · Neutro→0.5 · Negativo→0.0'],
        ['Ausencia de conducta', '35%', 'Sin picos→1.0 · 1 pico→0.4 · 2+ picos→0.0'],
        ['Sin medicación rescate', '20%', 'Sin rescate→1.0 · Con rescate→0.0'],
        ['Hidratación+baño', '10%*', '*Solo si hay datos. Si no, redistribuye entre los 3 anteriores.'],
    ], widths=[4.5*cm, 2*cm, 9.5*cm])]
    story += sp(4)
    story += p('<b>Penalizaciones:</b> −0.25 si 2+ picos de conducta · −0.10 si diazepam o lorazepam. Resultado acotado a [0, 5].')
    story += tip('El gráfico de evolución tiene scroll horizontal. Arrastra hacia la izquierda para ver meses anteriores. Se posiciona automáticamente en los datos más recientes.')
    story += sp()

    # ── 5. IMPORTAR DATOS ──────────────────────────────────────────────────────
    story += h1('5. Importar datos nuevos')
    story += p('Botón <b>📂 Actualizar datos</b> en la cabecera. Acepta archivos .txt exportados de WhatsApp.')
    for s in [
        'Abre el chat del grupo de mediadores en WhatsApp',
        'Toca ⋮ → "Más" → "Exportar chat" → "Sin archivos multimedia"',
        'Guarda el archivo .txt y súbelo desde el dashboard',
        'Los informes nuevos se insertan automáticamente. Los duplicados se ignoran.',
        'Si GEMINI_API_KEY está configurada, el parseo V3 se lanza en segundo plano para los nuevos.',
    ]:
        story += bul(s)
    story += sp(4)
    story += note('Si ves "Load failed" en móvil, el archivo puede ser muy grande. El dashboard lee el archivo localmente antes de enviarlo para evitar este error.')
    story += sp()

    # ── 6. PARSEO IA V3 ────────────────────────────────────────────────────────
    story += h1('6. Parseo IA con Gemini (V3)')
    story += p('Cada informe nuevo subido se parsea automáticamente con Gemini en segundo plano. El proceso completo para el histórico se lanza desde el panel de Entrenamiento IA.')
    story += h2('Campos nuevos en V3')
    story += [tbl([
        ['Campo', 'Descripción'],
        ['autoagresiones', 'Episodios donde Jorge se hace daño a sí mismo'],
        ['agresiones_mediador', 'Episodios de agresión al mediador'],
        ['agresiones_terceros', 'Agresiones a otras personas'],
        ['aleteos', 'Agitación sin agresión física (balanceo, gritos, aleteo de brazos)'],
        ['desayuno/almuerzo/comida/merienda/cena', 'Contenido de cada toma por separado'],
        ['sueno_horas', 'Horas de sueño como decimal (ej: 7.5)'],
        ['agua_ml', 'Agua siempre en mililitros'],
        ['vocabulario', 'Palabras o signos nuevos (texto libre)'],
    ], widths=[5.5*cm, 10.5*cm])]
    story += sp()

    # ── 7. ENTRENAMIENTO IA ────────────────────────────────────────────────────
    story += h1('7. Entrenamiento IA 🤖')
    story += p('Botón <b>🤖 Entrenamiento IA</b> en la cabecera. Panel con 4 pestañas:')
    story += sp(4)
    story += [tbl([
        ['Pestaña', 'Función'],
        ['✏️ Correcciones', 'Busca un informe, revisa lo que interpretó la IA, corrige los errores y guárdalos en BD. Cada corrección validada se usa automáticamente en los próximos parseos (few-shot learning).'],
        ['🏥 Docs médicos', 'Sube PDFs o imágenes de informes clínicos. Gemini los analiza y extrae diagnósticos, medicación, patrones de conducta y recomendaciones. Se usan para enriquecer los informes mensuales.'],
        ['📊 Informe mensual', 'Genera un análisis completo del mes seleccionado: resumen ejecutivo, conducta, bienestar físico, tendencias y predicción del próximo mes con nivel de riesgo y recomendaciones.'],
        ['📈 Estado IA', 'Estadísticas del sistema: correcciones totales, validadas, pendientes y cobertura del parseo V3.'],
    ])]
    story += sp(4)
    story += tip('Valida las correcciones (botón ✓ Validar) para que entren en el pool de few-shot. Los últimos 10 ejemplos validados se inyectan en cada parseo. Cuantos más ejemplos haya, más precisa es la IA.')
    story += sp()

    # ── 8. INFORME MENSUAL ─────────────────────────────────────────────────────
    story += h1('8. Informe mensual con predicción')
    story += p('En Entrenamiento IA → 📊 Informe mensual. Selecciona año y mes y pulsa <b>✨ Generar informe</b>.')
    story += p('El informe incluye: resumen ejecutivo, estado general con tendencia, análisis de conducta con patrón temporal, bienestar físico (hidratación, sueño, alimentación), y <b>predicción del próximo mes</b> con nivel de riesgo (bajo/medio/alto), factores relevantes y recomendaciones concretas para el equipo.')
    story += note('Si hay documentos médicos subidos, el informe los usa como contexto clínico adicional para enriquecer el análisis.')
    story += sp()

    # ── 9. DOCUMENTOS MÉDICOS ──────────────────────────────────────────────────
    story += h1('9. Documentos médicos')
    story += p('En Entrenamiento IA → 🏥 Docs médicos. Acepta PDFs e imágenes (JPG, PNG, WEBP).')
    story += p('Gemini extrae automáticamente: tipo de documento, fecha, especialidad, diagnósticos, medicación actual, observaciones de conducta, patrones relevantes y recomendaciones. Este contexto se usa en los informes mensuales para enriquecer el análisis y las predicciones.')
    story += sp()

    # ── 10. FILTROS ────────────────────────────────────────────────────────────
    story += h1('10. Filtros de la barra lateral')
    story += [tbl([
        ['Turno', 'Todos / Mañana / Tarde / Noche'],
        ['Mediador/a', 'Lista desplegable con todos los mediadores'],
        ['Estado de ánimo', 'Muy positivo / Positivo / Neutro / Negativo'],
        ['Conducta', 'Con picos / Sin picos'],
        ['Rango de fechas', 'Fecha inicio y fecha fin'],
    ], has_header=False)]
    story += sp()

    # ── 11. ANOTACIONES ────────────────────────────────────────────────────────
    story += h1('11. Anotaciones en el gráfico')
    story += p('Botón <b>📌 Anotaciones</b> en la cabecera. Añade marcadores verticales en el gráfico de evolución para señalar eventos relevantes.')
    story += [tbl([
        ['🟠 Naranja', 'Cambio de medicación, cambio de rutina'],
        ['🔴 Rojo', 'Hospitalización, período de alta dificultad'],
        ['🟢 Verde', 'Inicio de mejora sostenida, logro significativo'],
        ['🔵 Azul', 'Incorporación de mediador, información general'],
        ['🟣 Morado', 'Evento externo (COVID, vacaciones, cambio de centro)'],
    ], has_header=False)]
    story += sp()

    # ── 12. API ────────────────────────────────────────────────────────────────
    story += h1('12. Endpoints API principales')
    story += p('Todos requieren header <b>X-Password: haptica2025</b>. Los de admin requieren <b>X-Admin-Password: hapticaadmin2025</b>.')
    story += [tbl([
        ['Endpoint', 'Método', 'Descripción'],
        ['/api/stats', 'GET', 'KPIs + datos mensuales'],
        ['/api/reports', 'GET', 'Listado con filtros'],
        ['/api/upload-text', 'POST', 'Importar chat (JSON con texto)'],
        ['/api/upload', 'POST', 'Importar chat (multipart)'],
        ['/api/v3/conducta', 'GET', 'Evolución mensual 4 tipos de conducta'],
        ['/api/v3/alimentacion', 'GET', 'Informes con desglose por toma'],
        ['/api/v3/reparse-all', 'POST', 'Lanza reparseo masivo en background'],
        ['/api/v3/reparse-status', 'GET', 'Estado del reparseo (%)'],
        ['/api/training/corrections', 'GET/POST', 'Correcciones de entrenamiento'],
        ['/api/medical/upload', 'POST', 'Subir documento médico'],
        ['/api/medical/documents', 'GET', 'Listar documentos médicos'],
        ['/api/monthly-report', 'POST', 'Generar informe mensual con IA'],
        ['/api/admin/migrate-v3', 'POST', 'Crear tabla reports_v3'],
        ['/guia', 'GET', 'Descargar esta guía (regenerada en cada deploy)'],
    ], widths=[5*cm, 2.2*cm, 8.8*cm])]
    story += sp()

    # ── 13. STACK TÉCNICO ──────────────────────────────────────────────────────
    story += h1('13. Stack técnico')
    story += [tbl([
        ['Backend', 'Flask (Python) — app.py'],
        ['Frontend', 'HTML/JS con Chart.js — index.html (responsive PC y móvil)'],
        ['Parser V1', 'parser.py — regex'],
        ['Parser V3', 'parser_v3.py — Gemini Flash 2.0 con few-shot learning'],
        ['BD', 'PostgreSQL en Railway — tablas reports, reports_v3, training_corrections, medical_documents'],
        ['Deploy', 'Railway — auto-deploy en push a rama v3'],
        ['Guía', 'generate_guide.py — regenerada automáticamente en cada deploy'],
        ['Repo', 'fundacionhaptica/haptica-jorge (rama v3)'],
    ], has_header=False)]
    story += sp()

    # ── 14. PENDIENTES ─────────────────────────────────────────────────────────
    story += h1('14. Tareas pendientes')
    for s in [
        '⚠️  Ejecutar "💧 Corregir agua Raúl" vía /api/admin/fix-raul-agua (~126 registros con agua=1 → 1000ml)',
        '🤖  Lanzar reparseo masivo V3 desde admin_v3.html para poblar la pestaña Conducta detallada',
        '💤  Añadir gráfico de evolución de sueño (sueno_horas) en la pestaña Conducta detallada',
        '📊  Integrar datos V3 en el cálculo del Estado medio',
        '🏥  Subir guía de mediación V6 para enriquecer los informes mensuales con IA',
    ]:
        story += bul(s)

    # ── GENERAR PDF ────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title=f'Guía Dashboard Jorge V3 · Fundación HÁPTICA v{VERSION}',
        author='Fundación HÁPTICA',
    )
    doc.build(story)
    print(f"✓ Guía generada: {output_path} (v{VERSION}, build {BUILD_DATE})")
    return True


if __name__ == '__main__':
    output = sys.argv[1] if len(sys.argv) > 1 else 'static/guia_dashboard.pdf'
    try:
        build_guide(output)
    except Exception as e:
        print(f"✗ Error generando guía: {e}")
        # No salir con error — no debe bloquear el deploy
        sys.exit(0)
