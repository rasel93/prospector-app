import streamlit as st
import requests
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai

# ================= CONFIGURACIÓN =================
st.set_page_config(page_title="Bot Prospector", page_icon="🤖", layout="wide")

# 🔴 ESTE ES EL TÍTULO NUEVO. SI NO VES "VERSIÓN 4" EN TU PANTALLA, STREAMLIT NO SE HA ACTUALIZADO 🔴
st.title("🚀 Mi Bot Prospector (Versión 4 - AntiBloqueo)")

if "negocios" not in st.session_state:
    st.session_state.negocios =[]

with st.sidebar:
    st.header("⚙️ Configuración")
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
    EMAIL_SENDER = st.secrets.get("EMAIL_SENDER", "")
    EMAIL_PASSWORD = st.secrets.get("EMAIL_PASSWORD", "")
    
    if GEMINI_API_KEY: st.success("✅ IA conectada")
    else: st.error("❌ Falta API Key")
        
    if EMAIL_SENDER and EMAIL_PASSWORD: st.success("✅ Correo conectado")
    else: st.error("❌ Faltan credenciales")

# ================= MOTOR DE BÚSQUEDA (NOMINATIM) =================
def buscar_negocios(ciudad, tipo_negocio):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': f"{tipo_negocio} {ciudad}",
        'format': 'json',
        'extratags': 1,
        'limit': 15
    }
    headers = {
        'User-Agent': 'MiAppProspeccion_B2B_v4 (tu_correo_real@gmail.com)' # Cambia este correo por el tuyo en el futuro
    }
    
    try:
        respuesta = requests.get(url, params=params, headers=headers, timeout=15)
        
        if respuesta.status_code != 200:
            st.error(f"El servidor oficial rechazó la conexión (Error {respuesta.status_code}).")
            return[]
            
        datos = respuesta.json()
        leads =[]
        
        for lugar in datos:
            nombre = lugar.get('name', '')
            if not nombre: continue
                
            tags = lugar.get('extratags', {})
            leads.append({
                'nombre': nombre,
                'web': tags.get('website') or tags.get('contact:website', None),
                'telefono': tags.get('phone') or tags.get('contact:phone', 'No disponible')
            })
            
        leads_unicos = {lead['nombre']: lead for lead in leads}.values()
        return list(leads_unicos)[:5]
        
    except Exception as e:
        st.error(f"Fallo de conexión: {e}")
        return[]

def extraer_email_de_web(url):
    if not url: return None
    if not url.startswith("http"): url = "https://" + url
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=6)
        emails = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4}", response.text))
        emails =[e for e in emails if not e.lower().endswith(('sentry.io', 'wix.com', 'png', 'jpg'))]
        return emails[0] if emails else None
    except: return None

def generar_email(nombre, tiene_web):
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        if tiene_web: problema = "Diles que su web actual se puede modernizar para cargar más rápido."
        else: problema = "Diles que al no tener página web pierden clientes frente a la competencia."
        prompt = f"Escribe un email persuasivo de 3 líneas para el negocio '{nombre}'. {problema} Propón llamada de 5 mins."
        return client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text
    except Exception as e: return f"Error IA: {e}"

def enviar_correo(destinatario, asunto, cuerpo):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = destinatario
    msg['Subject'] = asunto
    msg.attach(MIMEText(cuerpo, 'plain'))
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
with col1: ciudad_input = st.text_input("📍 Ciudad", "Valencia")
with col2: tipo_input = st.selectbox("🏢 Tipo de Negocio",["dentist", "restaurant", "hospital", "lawyer"])

if st.button("🔍 Buscar Clientes", type="primary"):
    with st.spinner('Buscando en servidor oficial...'):
        st.session_state.negocios = buscar_negocios(ciudad_input, tipo_input)
        if not st.session_state.negocios:
            st.warning("No se encontraron resultados.")

if st.session_state.negocios:
    st.markdown("---")
    for neg in st.session_state.negocios:
        with st.expander(f"🏢 {neg['nombre']}", expanded=True):
            st.write(f"**Web:** {neg['web'] or '❌ No tiene'}")
            st.write(f"**Teléfono:** {neg['telefono']}")
            
            tiene_web = bool(neg['web'])
            email = extraer_email_de_web(neg['web']) if tiene_web else None
                
            if email:
                st.success(f"📧 Email: {email}")
                if st.button(f"✨ Redactar", key=f"gen_{neg['nombre']}"):
                    st.session_state[f"msg_{neg['nombre']}"] = generar_email(neg['nombre'], tiene_web)
                if f"msg_{neg['nombre']}" in st.session_state:
                    st.text_area("Borrador:", st.session_state[f"msg_{neg['nombre']}"], height=100, key=f"text_{neg['nombre']}")
                    if st.button(f"📨 Enviar", type="primary", key=f"send_{neg['nombre']}"):
                        if enviar_correo(email, f"Mejora digital para {neg['nombre']}", st.session_state[f"msg_{neg['nombre']}"]):
                            st.success("¡Enviado!")
                        else: st.error("Error al enviar.")
            else: st.warning("Sin email público.")
