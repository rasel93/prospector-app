import streamlit as st
import requests
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai

# ================= CONFIGURACIÓN DE PÁGINA =================
st.set_page_config(page_title="Bot de Prospección", page_icon="🤖", layout="wide")
st.title("🚀 Mi Bot Prospector Automático")

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

# ================= FUNCIONES PRINCIPALES =================

def buscar_negocios(ciudad, tipo_negocio):
    # Lista de servidores espejo (Si uno bloquea la nube de Streamlit, usamos otro)
    servidores =[
        "https://overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://z.overpass-api.de/api/interpreter"
    ]
    
    query = f"""[out:json][timeout:25];
    area["name"="{ciudad}"]->.searchArea;
    nwr["amenity"="{tipo_negocio}"](area.searchArea);
    out center tags limit 10;
    """
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    
    for url in servidores:
        try:
            respuesta = requests.post(url, data={'data': query}, headers=headers, timeout=15)
            
            # Si responde bien, procesamos los datos
            if respuesta.status_code == 200:
                try:
                    datos = respuesta.json()
                    leads =[]
                    for elemento in datos.get('elements',[]):
                        tags = elemento.get('tags', {})
                        if 'name' in tags:
                            leads.append({
                                'nombre': tags.get('name', 'Sin nombre'),
                                'web': tags.get('website', None) or tags.get('contact:website', None),
                                'telefono': tags.get('phone', None) or tags.get('contact:phone', 'No disponible')
                            })
                    # Limpiar duplicados
                    leads_unicos = {lead['nombre']: lead for lead in leads}.values()
                    return list(leads_unicos)[:5]
                except:
                    continue # Falla el JSON, intentamos el siguiente servidor
        except Exception:
            continue # Falla la conexión, intentamos el siguiente servidor

    # Si todos los servidores fallan
    st.error("⚠️ Los servidores públicos han bloqueado temporalmente la búsqueda desde la nube. Inténtalo en unos minutos o usa otra ciudad.")
    return[]

def extraer_email_de_web(url):
    if not url: return None
    if not url.startswith("http"): url = "https://" + url
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        emails = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4}", response.text))
        emails =[e for e in emails if not e.lower().endswith(('sentry.io', 'wix.com', 'png', 'jpg'))]
        return emails[0] if emails else None
    except:
        return None

def generar_email(nombre, tiene_web):
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        if tiene_web:
            problema = "Tienen página web. Diles que hoy en día la velocidad móvil es clave y tú puedes mejorarla."
        else:
            problema = "No tienen página web. Diles que pierden visibilidad en Google frente a la competencia."

        prompt = f"Eres experto en ventas web. Escribe un email corto (máximo 4 líneas) para el negocio '{nombre}'. {problema} Propón una llamada de 5 minutos."
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
    tipo_input = st.selectbox("🏢 Tipo de Negocio", ["dentist", "restaurant", "hospital", "lawyer", "gym"])

if st.button("🔍 Buscar Clientes Potenciales", type="primary", use_container_width=True):
    with st.spinner('Buscando en la base de datos...'):
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
                st.success(f"📧 Email encontrado: {email}")
                if st.button(f"✨ Redactar Email", key=f"gen_{neg['nombre']}"):
                    st.session_state[f"msg_{neg['nombre']}"] = generar_email(neg['nombre'], tiene_web)

                if f"msg_{neg['nombre']}" in st.session_state:
                    st.text_area("Borrador:", st.session_state[f"msg_{neg['nombre']}"], height=150, key=f"text_{neg['nombre']}")
                    if st.button(f"📨 Enviar Correo a {neg['nombre']}", type="primary", key=f"send_{neg['nombre']}"):
                        if enviar_correo(email, f"Mejora digital para {neg['nombre']}", st.session_state[f"msg_{neg['nombre']}"]):
                            st.success("¡Correo enviado!")
                        else:
                            st.error("Error al enviar. Revisa la contraseña de aplicación de Gmail.")
            else:
                st.warning("Sin email público. Contactar por teléfono.")
