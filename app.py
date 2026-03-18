import streamlit as st
import requests
import re
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai

# ================= CONFIGURACIÓN =================
st.set_page_config(page_title="Bot Prospector PRO", page_icon="🔥", layout="wide")
st.title("🔥 Mi Bot Prospector (V6 - Motor Google Maps)")

if "negocios" not in st.session_state:
    st.session_state.negocios =[]

with st.sidebar:
    st.header("⚙️ Credenciales")
    SERPER_API_KEY = st.text_input("Serper API Key (Para Google Maps)", value=st.secrets.get("SERPER_API_KEY", ""), type="password")
    GEMINI_API_KEY = st.text_input("Gemini API Key (Para IA)", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    EMAIL_SENDER = st.text_input("Tu Correo (Gmail)", value=st.secrets.get("EMAIL_SENDER", ""))
    EMAIL_PASSWORD = st.text_input("Contraseña de App Gmail", value=st.secrets.get("EMAIL_PASSWORD", ""), type="password")
    
    st.markdown("---")
    if SERPER_API_KEY: st.success("✅ Base de Datos conectada")
    else: st.error("❌ Falta Serper API Key")
    
    if GEMINI_API_KEY: st.success("✅ IA conectada")
    else: st.error("❌ Falta Gemini API Key")

# ================= MOTOR DE BÚSQUEDA (GOOGLE MAPS vía SERPER) =================
def buscar_negocios(ciudad, tipo_negocio):
    if not SERPER_API_KEY:
        st.error("⚠️ Necesitas poner tu Serper API Key a la izquierda para conectar con Google Maps.")
        return[]

    url = "https://google.serper.dev/places"
    payload = json.dumps({
      "q": f"{tipo_negocio} en {ciudad}",
      "gl": "es", # País (España)
      "hl": "es"  # Idioma (Español)
    })
    headers = {
      'X-API-KEY': SERPER_API_KEY,
      'Content-Type': 'application/json'
    }

    try:
        respuesta = requests.request("POST", url, headers=headers, data=payload, timeout=15)
        
        if respuesta.status_code != 200:
            st.error(f"Error de la API: {respuesta.text}")
            return[]
            
        datos = respuesta.json()
        places = datos.get('places', [])
        leads =[]
        
        for lugar in places:
            # 🔴 Filtro Inteligente: Solo queremos negocios de Google que tengan web o teléfono
            web = lugar.get('website')
            telefono = lugar.get('phoneNumber')
            
            if web or telefono:
                leads.append({
                    'nombre': lugar.get('title', 'Sin Nombre'),
                    'web': web,
                    'telefono': telefono if telefono else 'No disponible',
                    'direccion': lugar.get('address', '')
                })
        
        return leads[:10] # Mostramos los 10 mejores
        
    except Exception as e:
        st.error(f"Fallo de conexión: {e}")
        return[]

def extraer_email_de_web(url):
    if not url: return None
    if not url.startswith("http"): url = "https://" + url
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=8)
        # Búsqueda agresiva de emails en el código fuente de la web
        emails = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4}", response.text))
        emails =[e for e in emails if not e.lower().endswith(('sentry.io', 'wix.com', 'png', 'jpg', 'gif', 'jpeg'))]
        return emails[0] if emails else None
    except: return None

def generar_email(nombre, tiene_web):
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        if tiene_web: 
            problema = "Tienen página web pero coméntales que la velocidad y adaptabilidad móvil hoy lo son todo. Ofrece una auditoría gratuita."
        else: 
            problema = "He visto en Google Maps que no tienen sitio web. Diles que están perdiendo muchos clientes potenciales que buscan en Google."
        
        prompt = f"Eres un experto en ventas B2B. Escribe un correo muy directo, amigable y natural (máximo 4 líneas) para el dueño del negocio '{nombre}'. {problema} Tu objetivo es agendar una llamada de 5 minutos. No uses despedidas formales anticuadas."
        
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
with col1: ciudad_input = st.text_input("📍 Ciudad", "Madrid")
with col2: tipo_input = st.text_input("🏢 Nicho (Ej: Dentista, Abogado, Reformas)", "Dentista")

if st.button("🔍 Extraer Clientes de Google Maps", type="primary"):
    with st.spinner('Conectando con Google Maps...'):
        st.session_state.negocios = buscar_negocios(ciudad_input, tipo_input)
        if not st.session_state.negocios:
            st.warning("No se encontraron resultados.")

if st.session_state.negocios:
    st.markdown("---")
    st.subheader(f"✅ Se han encontrado {len(st.session_state.negocios)} prospectos de alta calidad")
    
    for neg in st.session_state.negocios:
        with st.expander(f"🏢 {neg['nombre']} - 📍 {neg['direccion'][:30]}...", expanded=False):
            st.write(f"**Web:** {neg['web'] or '❌ No tiene (Oportunidad)'}")
            st.write(f"**Teléfono:** {neg['telefono']}")
            
            tiene_web = bool(neg['web'])
            email = None
            
            if tiene_web:
                with st.spinner(f"Escaneando web de {neg['nombre']} en busca de emails..."):
                    email = extraer_email_de_web(neg['web'])
                
            if email:
                st.success(f"📧 Email detectado: {email}")
                if st.button(f"✨ Redactar Mensaje", key=f"gen_{neg['nombre']}"):
                    st.session_state[f"msg_{neg['nombre']}"] = generar_email(neg['nombre'], tiene_web)
                
                if f"msg_{neg['nombre']}" in st.session_state:
                    st.text_area("Borrador:", st.session_state[f"msg_{neg['nombre']}"], height=120, key=f"text_{neg['nombre']}")
                    if st.button(f"📨 Enviar Correo Oficial", type="primary", key=f"send_{neg['nombre']}"):
                        if enviar_correo(email, f"Digitalización de {neg['nombre']}", st.session_state[f"msg_{neg['nombre']}"]):
                            st.balloons()
                            st.success("¡Enviado con éxito!")
                        else: st.error("Fallo al enviar el correo.")
            else: 
                if tiene_web:
                    st.warning("Su web no tiene el email visible. ¡Ideal para llamar y preguntar por la persona encargada!")
                else:
                    st.warning("No tienen web ni email. Toca llamada comercial (Cold Calling).")
