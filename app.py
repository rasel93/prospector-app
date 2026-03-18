import streamlit as st
import requests
import re
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai

# ================= CONFIGURACIÓN =================
st.set_page_config(page_title="Bot Prospector Agencia", page_icon="📈", layout="wide")
st.title("📈 Máquina de Ventas: Web + Mantenimiento + Ads (V8)")

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
    """ Se conecta a Google PageSpeed Insights para auditar la web en versión MÓVIL """
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
        
        # 🧠 EL CEREBRO DE TUS VENTAS 🧠
        if tiene_web and score is not None:
            if score < 60:
                contexto = f"He auditado su web y carga muy lento en móviles (tiene un {score}/100 en Google). La gente se cansa de esperar y se va a la competencia."
            else:
                contexto = f"Su web saca un {score}/100 en Google. Está bien, pero se puede optimizar muchísimo más para que convierta visitas en clientes reales."
        elif tiene_web:
            contexto = "Tienen web, pero hoy en día si no está optimizada y no recibe tráfico constante, es como tener una tienda en un callejón sin salida."
        else:
            contexto = "No tienen página web. Son completamente invisibles en Google cuando alguien en la ciudad busca sus servicios."

        oferta = """
        Dile que te dedicas a 3 cosas para negocios como el suyo:
        1. Optimizar su web (o crearla) para que sea una máquina rápida de ventas.
        2. Darles mantenimiento técnico mensual para que se despreocupen de caídas o hackeos.
        3. Si quieren escalar en serio, lanzarles campañas de anuncios (Ads) para llenarles el teléfono de clientes esta misma semana.
        Cierre: Ofréceles grabarles un vídeo-auditoría de 3 minutos gratis enseñando cómo hacerlo en su caso.
        """

        prompt = f"""
        Eres un experto Copywriter B2B. Escribe un correo en frío hiper-persuasivo para el dueño de '{nombre}'.
        
        SITUACIÓN DEL CLIENTE: {contexto}
        TU OBJETIVO Y OFERTA: {oferta}
        
        REGLAS ESTRICTAS:
        1. Comienza la primera línea obligatoriamente con "Asunto: " y crea un asunto corto de 3 a 5 palabras que genere mucha curiosidad (Ej: Tu nota de Google, Idea para [Nombre]...).
        2. El correo debe ser corto (máximo 5 líneas). 
        3. Tono conversacional, como de tú a tú. NADA de "Estimado señor", "Cordial saludo" o lenguaje robótico.
        4. Haz que la oferta suene imposible de rechazar porque el riesgo lo asumes tú al ofrecer el vídeo gratis inicial.
        """
        
        return client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text
    except Exception as e: return f"Error IA: {e}"

def enviar_correo(destinatario, cuerpo):
    lineas = cuerpo.split('\n')
    asunto = "Mejora urgente para tu negocio"
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
    with st.spinner('Extrayendo base de datos de Google Maps...'):
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
                
                # BOTÓN PARA GENERAR EL TEXTO MAESTRO
                if st.button(f"🚀 Analizar Web y Redactar Oferta", key=f"gen_{neg['nombre']}", type="primary"):
                    score = None
                    if tiene_web:
                        with st.spinner(f"Analizando velocidad móvil en servidores de Google..."):
                            score = auditar_velocidad(neg['web'])
                            if score is not None:
                                if score < 50: st.error(f"¡Lentitud extrema!: {score}/100. Presiona con la pérdida de clientes.")
                                else: st.warning(f"Rendimiento: {score}/100. Se puede mejorar el diseño y hacer Ads.")
                    
                    with st.spinner("La IA está redactando la oferta de Optimización + Mantenimiento + Ads..."):
                        st.session_state[f"msg_{neg['nombre']}"] = generar_email(neg['nombre'], tiene_web, score)
                
                if f"msg_{neg['nombre']}" in st.session_state:
                    st.text_area("Borrador listo para enviar:", st.session_state[f"msg_{neg['nombre']}"], height=220, key=f"text_{neg['nombre']}")
                    if st.button(f"📨 Enviar Oferta", key=f"send_{neg['nombre']}"):
                        if enviar_correo(email, st.session_state[f"msg_{neg['nombre']}"]):
                            st.balloons()
                            st.success("¡Oferta enviada con éxito!")
                        else: st.error("Error al enviar.")
            else: 
                if tiene_web:
                    st.warning("No tienen email visible. ¡Llámales para ofrecerles el vídeo gratis por WhatsApp!")
                else:
                    st.warning("Oportunidad máxima: Sin web. Tienes que llamarles para ofrecerles el paquete completo.")
