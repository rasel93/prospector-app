import streamlit as st
import requests
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai
from duckduckgo_search import DDGS

# ================= CONFIGURACIÓN DE PÁGINA =================
st.set_page_config(page_title="Bot Prospector 3.0", page_icon="🤖", layout="wide")
st.title("🚀 Mi Bot Prospector (Buscador Web)")

if "negocios" not in st.session_state:
    st.session_state.negocios =[]

# ================= BARRA LATERAL =================
with st.sidebar:
    st.header("⚙️ Configuración")
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
    EMAIL_SENDER = st.secrets.get("EMAIL_SENDER", "")
    EMAIL_PASSWORD = st.secrets.get("EMAIL_PASSWORD", "")
    
    if GEMINI_API_KEY:
        st.success("✅ API de IA conectada")
    else:
        st.error("❌ Falta GEMINI_API_KEY")
        
    if EMAIL_SENDER and EMAIL_PASSWORD:
        st.success("✅ Correo conectado")
    else:
        st.error("❌ Faltan credenciales de correo")

# ================= NUEVO MOTOR DE BÚSQUEDA (DuckDuckGo) =================

def buscar_negocios(ciudad, tipo_negocio):
    # Buscamos como lo haría un humano en Google/DuckDuckGo
    query = f"{tipo_negocio} en {ciudad} sitio web oficial"
    
    try:
        # Esto busca en internet en tiempo real y NO bloquea IPs de la nube
        resultados = DDGS().text(query, max_results=15)
        leads =[]
        
        # Filtramos para no meter redes sociales ni páginas amarillas
        directorios =['facebook.com', 'instagram.com', 'yelp.', 'tripadvisor.', 'paginasamarillas', 'doctoralia', 'topdoctors', 'linkedin.com', 'tiktok.com']
        
        for res in resultados:
            url = res.get('href', '')
            
            # Si es un directorio, lo ignoramos y pasamos al siguiente
            if any(d in url for d in directorios):
                continue
                
            # Limpiar el título para sacar el nombre de la empresa
            nombre_bruto = res.get('title', 'Negocio')
            nombre = nombre_bruto.split('|')[0].split('-')[0].strip()
            
            leads.append({
                'nombre': nombre,
                'web': url,
                'telefono': "Consultar en su web" # El buscador web no da el teléfono directo, pero sí la web
            })
            
            if len(leads) >= 5: # Limitamos a 5 resultados buenos
                break
                
        return leads
        
    except Exception as e:
        st.error(f"Error en el buscador: {e}")
        return[]

def extraer_email_de_web(url):
    if not url: return None
    if not url.startswith("http"): url = "https://" + url
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=6)
        # Extraer correos con expresiones regulares
        emails = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4}", response.text))
        emails =[e for e in emails if not e.lower().endswith(('sentry.io', 'wix.com', 'png', 'jpg', 'gif'))]
        return emails[0] if emails else None
    except:
        return None

def generar_email(nombre, web):
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""
        Eres un experto desarrollador web vendiendo tus servicios.
        Escribe un email corto (máximo 4 líneas) muy humano y directo para el dueño del negocio '{nombre}'.
        Dile que has visitado su web ({web}) y que crees que puedes mejorar su velocidad de carga y diseño móvil para que no pierdan clientes.
        Propón una llamada rápida de 5 minutos.
        """
        respuesta = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return respuesta.text
    except Exception as e:
        return f"Error de IA: {e}"

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
    except:
        return False

# ================= INTERFAZ PRINCIPAL =================

col1, col2 = st.columns(2)
with col1:
    ciudad_input = st.text_input("📍 Ciudad", "Valencia")
with col2:
    tipo_input = st.text_input("🏢 Tipo de Negocio", "Clínica dental") # Ahora puedes escribir lo que quieras en español

if st.button("🔍 Buscar en Internet", type="primary", use_container_width=True):
    with st.spinner('Rastreando páginas web en tiempo real...'):
        st.session_state.negocios = buscar_negocios(ciudad_input, tipo_input)
        if not st.session_state.negocios:
            st.warning("No se encontraron webs directas para esta búsqueda.")

if st.session_state.negocios:
    st.markdown("---")
    for neg in st.session_state.negocios:
        with st.expander(f"🏢 {neg['nombre']}", expanded=True):
            st.write(f"**Web encontrada:** [{neg['web']}]({neg['web']})")
            
            email = extraer_email_de_web(neg['web'])
                
            if email:
                st.success(f"📧 Email detectado: {email}")
                if st.button(f"✨ Redactar Propuesta", key=f"gen_{neg['nombre']}"):
                    st.session_state[f"msg_{neg['nombre']}"] = generar_email(neg['nombre'], neg['web'])

                if f"msg_{neg['nombre']}" in st.session_state:
                    st.text_area("Borrador (puedes editarlo):", st.session_state[f"msg_{neg['nombre']}"], height=150, key=f"text_{neg['nombre']}")
                    if st.button(f"📨 Enviar Correo a {neg['nombre']}", type="primary", key=f"send_{neg['nombre']}"):
                        if enviar_correo(email, f"Mejora para la web de {neg['nombre']}", st.session_state[f"msg_{neg['nombre']}"]):
                            st.balloons()
                            st.success("¡Enviado con éxito!")
                        else:
                            st.error("Error al enviar. Revisa la contraseña en los Secrets de Streamlit.")
            else:
                st.warning("No se encontró ningún email visible en la página principal de esta web.")
