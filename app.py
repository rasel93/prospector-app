import streamlit as st
import requests
import re
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai

# ================= SEGURIDAD MÁXIMA =================
# En la nube, estas variables se leerán de los "Secrets" encriptados.
# Si estás probando en local, puedes escribirlas aquí temporalmente o usar la interfaz de la web.
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
EMAIL_SENDER = st.secrets.get("EMAIL_SENDER", "")
EMAIL_PASSWORD = st.secrets.get("EMAIL_PASSWORD", "")

# Inicializar cliente de Gemini con la nueva librería
if GEMINI_API_KEY:
    client_ai = genai.Client(api_key=GEMINI_API_KEY)

# ================= FUNCIONES =================

def buscar_negocios(ciudad, tipo_negocio):
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    area[name="{ciudad}"]->.searchArea;
    node["amenity"="{tipo_negocio}"](area.searchArea);
    out tags limit 5;
    """
    # SOLUCIÓN AL ERROR JSON: Añadir User-Agent
    headers = {'User-Agent': 'BotProspeccionSeguro/1.0 (contacto@midominio.com)'}
    
    try:
        respuesta = requests.get(overpass_url, params={'data': query}, headers=headers, timeout=10)
        datos = respuesta.json()
        
        leads =[]
        for elemento in datos.get('elements',[]):
            tags = elemento.get('tags', {})
            if 'name' in tags:
                leads.append({
                    'nombre': tags.get('name'),
                    'web': tags.get('website', None),
                    'telefono': tags.get('phone', 'No disponible')
                })
        return leads
    except Exception as e:
        st.error(f"Error al buscar negocios: {e}")
        return[]

def extraer_email_de_web(url):
    if not url.startswith("http"):
        url = "http://" + url
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        emails = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4}", response.text))
        emails =[e for e in emails if not e.endswith(('sentry.io', 'wix.com', 'png', 'jpg'))]
        return emails[0] if emails else None
    except:
        return None

def analizar_velocidad(url):
    if not url: return None
    try:
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}"
        respuesta = requests.get(api_url).json()
        score = respuesta['lighthouseResult']['categories']['performance']['score'] * 100
        return int(score)
    except:
        return None

def generar_email(nombre, tiene_web, score):
    if tiene_web and score is not None:
        problema = f"He analizado su web y carga con una nota de {score}/100 según Google. Están perdiendo visitas."
    else:
        problema = "He visto que no tienen página web y pierden visibilidad en Google frente a la competencia."

    prompt = f"Eres experto en ventas B2B. Escribe un correo muy corto (3 líneas) para '{nombre}'. Contexto: {problema}. Propón una breve llamada de 5 minutos."
    
    # SOLUCIÓN AL ERROR DE GEMINI: Usar la nueva sintaxis
    respuesta = client_ai.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    return respuesta.text

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
    except Exception as e:
        return False

# ================= INTERFAZ WEB (STREAMLIT) =================

st.set_page_config(page_title="Máquina de Prospección", page_icon="🤖")
st.title("🚀 Mi Bot Prospector B2B")

with st.sidebar:
    st.header("⚙️ Configuración Segura")
    st.info("Si configuras los 'Secrets' en la nube, no necesitas rellenar esto.")
    if not GEMINI_API_KEY:
        GEMINI_API_KEY = st.text_input("Gemini API Key", type="password")
    if not EMAIL_SENDER:
        EMAIL_SENDER = st.text_input("Tu Correo Gmail")
    if not EMAIL_PASSWORD:
        EMAIL_PASSWORD = st.text_input("Contraseña de Aplicación", type="password")

col1, col2 = st.columns(2)
with col1:
    ciudad = st.text_input("Ciudad", "Valencia")
with col2:
    tipo = st.selectbox("Tipo de Negocio", ["dentist", "restaurant", "hospital", "cafe"])

if st.button("🔍 Buscar y Generar Campaña", type="primary"):
    if not GEMINI_API_KEY:
        st.error("⚠️ Faltan las credenciales en la configuración.")
    else:
        with st.spinner('Buscando clientes en la base de datos...'):
            negocios = buscar_negocios(ciudad, tipo)
            
            if not negocios:
                st.warning("No se encontraron negocios o la base de datos no respondió.")
            
            for neg in negocios:
                with st.expander(f"🏢 {neg['nombre']}", expanded=True):
                    st.write(f"**Web:** {neg['web'] or 'No tiene'}")
                    st.write(f"**Teléfono:** {neg['telefono']}")
                    
                    tiene_web = bool(neg['web'])
                    email = None
                    score = None
                    
                    if tiene_web:
                        email = extraer_email_de_web(neg['web'])
                        score = analizar_velocidad(neg['web'])
                        st.write(f"**Velocidad Web:** {f'{score}/100' if score else 'Desconocida'}")
                        
                    if email:
                        st.success(f"📧 Email encontrado: {email}")
                        mensaje = generar_email(neg['nombre'], tiene_web, score)
                        st.text_area("Borrador del correo:", mensaje, height=150)
                        
                        # Botón para enviar
                        if EMAIL_SENDER and EMAIL_PASSWORD:
                            if st.button(f"📨 Enviar Correo a {neg['nombre']}", key=email):
                                if enviar_correo(email, f"Mejora digital para {neg['nombre']}", mensaje):
                                    st.success("¡Enviado correctamente!")
                                else:
                                    st.error("Error al enviar. Revisa tus contraseñas.")
                    else:
                        st.warning("No se encontró email público. ¡Toca llamar por teléfono!")