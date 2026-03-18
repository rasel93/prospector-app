import streamlit as st
import requests
import re
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai

# ================= CONFIGURACIÓN =================
st.set_page_config(page_title="Bot Prospector 2026", page_icon="🚀", layout="wide")
st.title("🚀 Máquina de Ventas B2B (V9 - Edición 2026)")

if "negocios" not in st.session_state:
    st.session_state.negocios =[]

with st.sidebar:
    st.header("⚙️ Credenciales")
    SERPER_API_KEY = st.text_input("Serper API Key", value=st.secrets.get("SERPER_API_KEY", ""), type="password")
    GEMINI_API_KEY = st.text_input("Gemini API Key", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    EMAIL_SENDER = st.text_input("Tu Correo (Gmail)", value=st.secrets.get("EMAIL_SENDER", ""))
    EMAIL_PASSWORD = st.text_input("Contraseña de App", value=st.secrets.get("EMAIL_PASSWORD", ""), type="password")
    st.markdown("---")

# ================= MOTORES DE BÚSQUEDA Y AUDITORÍA =================
def buscar_negocios(ciudad, tipo_negocio):
    if not SERPER_API_KEY:
        st.error("⚠️ Falta tu Serper API Key.")
        return[]

    url = "https://google.serper.dev/places"
    payload = json.dumps({"q": f"{tipo_negocio} en {ciudad}", "gl": "es", "hl": "es"})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}

    try:
        respuesta = requests.request("POST", url, headers=headers, data=payload, timeout=15)
        datos = respuesta.json()
        leads =[]
        
        for lugar in datos.get('places',[]):
            web = lugar.get('website')
            telefono = lugar.get('phoneNumber')
            if web or telefono:
                leads.append({
                    'nombre': lugar.get('title', 'Sin Nombre'),
                    'web': web,
                    'telefono': telefono if telefono else 'No disponible',
                    'direccion': lugar.get('address', '')
                })
        return leads[:10]
    except Exception as e:
        return[]

def extraer_email_de_web(url):
    if not url: return None
    if not url.startswith("http"): url = "https://" + url
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=8)
        emails = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4}", response.text))
        emails =[e for e in emails if not e.lower().endswith(('sentry.io', 'wix.com', 'png', 'jpg', 'jpeg'))]
        return emails[0] if emails else None
    except: return None

def auditar_velocidad(url):
    if not url: return None
    if not url.startswith("http"): url = "https://" + url
    try:
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile"
        respuesta = requests.get(api_url, timeout=25).json()
        score = respuesta['lighthouseResult']['categories']['performance']['score'] * 100
        return int(score)
    except: return None

def generar_email(nombre, tiene_web, score=None):
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # 🧠 EL CEREBRO DE TUS VENTAS EN 2026 🧠
        if tiene_web and score is not None:
            if score < 60:
                contexto = f"He pasado un escáner a su web y la velocidad móvil es muy deficiente (un {score}/100 según Google). En 2026, si una web tarda más de 3 segundos en cargar, el cliente se va automáticamente a la competencia."
            else:
                contexto = f"Su web tiene un {score}/100 en Google. No es un desastre, pero en el mercado tan agresivo de 2026, se necesita una optimización perfecta para no tirar el dinero."
        elif tiene_web:
            contexto = "Tienen web, pero hoy en día la mayoría de negocios tienen webs obsoletas que no convierten visitas en llamadas."
        else:
            contexto = "No tienen página web. Es impensable operar en 2026 sin presencia digital; son invisibles frente a su competencia directa."

        oferta = """
        Ofrece una solución integral en 3 pasos:
        1. Renovar u optimizar su web para que sea ultrarrápida y actual.
        2. Mantenimiento técnico continuo para blindarla.
        3. Campañas de anuncios (Ads) para inyectarles clientes de forma inmediata.
        CIERRE: Ofréceles enviarles un vídeo-auditoría de 3 minutos sin compromiso para enseñarles los fallos exactos de su negocio.
        """

        prompt = f"""
        Eres un experto Copywriter de ventas. Escribe un cold email que destaque en una bandeja de entrada saturada. Dirigido al dueño de '{nombre}'.
        
        SITUACIÓN REAL: {contexto}
        TU OFERTA: {oferta}
        
        REGLAS ESTRICTAS PARA NO PARECER SPAM:
        1. Primera línea: "Asunto: " seguido de un título de 3 a 5 palabras, directo al grano (ej: Error en web, Problema con la captación en [Nombre]...).
        2. Longitud máxima: 4-5 líneas. La gente no lee emails largos.
        3. Tono: Súper natural, de tú a tú. Como un consultor escribiendo a un amigo. CERO saludos corporativos, CERO lenguaje poético.
        4. Haz énfasis en que el vídeo es 100% gratuito y lo grabas tú personalmente para su caso.
        """
        
        return client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text
    except Exception as e: return f"Error IA: {e}"

def enviar_correo(destinatario, cuerpo):
    lineas = cuerpo.split('\n')
    asunto = "Oportunidad de crecimiento"
    cuerpo_final = cuerpo
    
    if lineas[0].lower().startswith("asunto:"):
        asunto = lineas[0].replace("Asunto:", "").replace("asunto:", "").strip()
        cuerpo_final = '\n'.join(lineas[1:]).strip()

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = destinatario
    msg['Subject'] = asunto
    msg.attach(MIMEText(cuerpo_final, 'plain'))
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except: return False

# ================= INTERFAZ =================
col1, col2 = st.columns(2)
with col1: ciudad_input = st.text_input("📍 Ciudad", "Madrid")
with col2: tipo_input = st.text_input("🏢 Nicho (Ej: Dentista, Abogado, Reformas)", "Abogado")

if st.button("🔍 Extraer Clientes y Auditar", type="primary"):
    with st.spinner('Extrayendo leads de alta calidad desde Google Maps...'):
        st.session_state.negocios = buscar_negocios(ciudad_input, tipo_input)
        if not st.session_state.negocios:
            st.warning("No se encontraron resultados.")

if st.session_state.negocios:
    st.markdown("---")
    for neg in st.session_state.negocios:
        with st.expander(f"🏢 {neg['nombre']}", expanded=False):
            st.write(f"**Web:** {neg['web'] or '❌ OPORTUNIDAD: No tiene web'}")
            st.write(f"**Teléfono:** {neg['telefono']}")
            
            tiene_web = bool(neg['web'])
            
            if f"email_{neg['nombre']}" not in st.session_state:
                st.session_state[f"email_{neg['nombre']}"] = extraer_email_de_web(neg['web']) if tiene_web else None
            
            email = st.session_state[f"email_{neg['nombre']}"]
            
            if email:
                st.success(f"📧 Email de contacto: {email}")
                
                if st.button(f"🚀 Analizar Web y Redactar Oferta (Edición 2026)", key=f"gen_{neg['nombre']}", type="primary"):
                    score = None
                    if tiene_web:
                        with st.spinner(f"Analizando métricas web en servidores de Google..."):
                            score = auditar_velocidad(neg['web'])
                            if score is not None:
                                if score < 50: st.error(f"¡Lentitud crítica!: {score}/100. Usa esto a tu favor.")
                                else: st.warning(f"Rendimiento: {score}/100. Ideal para vender Ads y Mantenimiento.")
                    
                    with st.spinner("La IA está redactando tu propuesta personalizada..."):
                        st.session_state[f"msg_{neg['nombre']}"] = generar_email(neg['nombre'], tiene_web, score)
                
                if f"msg_{neg['nombre']}" in st.session_state:
                    st.text_area("Borrador listo para enviar:", st.session_state[f"msg_{neg['nombre']}"], height=220, key=f"text_{neg['nombre']}")
                    if st.button(f"📨 Enviar Correo de Alto Impacto", key=f"send_{neg['nombre']}"):
                        if enviar_correo(email, st.session_state[f"msg_{neg['nombre']}"]):
                            st.balloons()
                            st.success("¡Oferta enviada y aterrizada en su bandeja de entrada!")
                        else: st.error("Error al enviar.")
            else: 
                if tiene_web:
                    st.warning("Sin email visible. ¡Súper oportunidad para hacer Cold Calling (Llamada) y preguntar por el dueño!")
                else:
                    st.warning("Oportunidad máxima: Negocio sin digitalizar. Llámalos ahora.")
