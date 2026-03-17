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

# Inicializar la memoria de Streamlit para no perder los datos al hacer clic en botones
if "negocios" not in st.session_state:
    st.session_state.negocios =[]

# ================= BARRA LATERAL (CREDENCIALES) =================
with st.sidebar:
    st.header("⚙️ Configuración")
    st.info("Rellena esto para que la IA y los correos funcionen.")
    
    # Intenta leer de secrets (nube), si no, usa los campos de texto
    GEMINI_API_KEY = st.text_input("Gemini API Key", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    EMAIL_SENDER = st.text_input("Tu Correo (Gmail)", value=st.secrets.get("EMAIL_SENDER", ""))
    EMAIL_PASSWORD = st.text_input("Contraseña de Aplicación", value=st.secrets.get("EMAIL_PASSWORD", ""), type="password")

# ================= FUNCIONES PRINCIPALES =================

def buscar_negocios(ciudad, tipo_negocio):
    url = "https://overpass-api.de/api/interpreter"
    
    # Consulta robusta buscando nodos, vías y relaciones (nwr)
    query = f"""
    [out:json][timeout:25];
    area["name"="{ciudad}"]->.searchArea;
    nwr["amenity"="{tipo_negocio}"](area.searchArea);
    out center tags limit 10;
    """
    
    # Simulamos ser un navegador real y pedimos explícitamente formato JSON
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0',
        'Accept': 'application/json'
    }
    
    try:
        # Petición POST pura (es la que menos falla en Overpass)
        respuesta = requests.post(url, data={'data': query}, headers=headers, timeout=25)
        
        # Si la base de datos da un error interno, lo mostramos claro
        if respuesta.status_code != 200:
            st.error(f"Error del servidor Overpass (Código {respuesta.status_code}): {respuesta.text[:200]}")
            return []
            
        datos = respuesta.json()
        leads =[]
        
        for elemento in datos.get('elements',[]):
            tags = elemento.get('tags', {})
            if 'name' in tags:
                # Filtrar y limpiar los datos
                leads.append({
                    'nombre': tags.get('name', 'Sin nombre'),
                    'web': tags.get('website', None) or tags.get('contact:website', None),
                    'telefono': tags.get('phone', None) or tags.get('contact:phone', 'No disponible')
                })
                
        # Eliminar negocios duplicados por nombre
        leads_unicos = {lead['nombre']: lead for lead in leads}.values()
        return list(leads_unicos)[:5]  # Devolvemos máximo 5 para probar sin saturar
        
    except requests.exceptions.JSONDecodeError:
        st.error("La base de datos bloqueó la petición (Devolvió HTML en lugar de datos). Intenta usar otra ciudad o espera unos minutos.")
        return[]
    except Exception as e:
        st.error(f"Error técnico de conexión: {e}")
        return[]

def extraer_email_de_web(url):
    if not url: return None
    if not url.startswith("http"): url = "https://" + url
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=7)
        emails = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4}", response.text))
        emails =[e for e in emails if not e.lower().endswith(('sentry.io', 'wix.com', 'png', 'jpg', 'gif'))]
        return emails[0] if emails else None
    except:
        return None

def generar_email(nombre, tiene_web):
    if not GEMINI_API_KEY:
        return "⚠️ Necesitas poner tu API Key de Gemini en la barra lateral para generar el texto."
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        if tiene_web:
            problema = "Tienen página web, pero diles que hoy en día la velocidad y el diseño móvil son clave para no perder clientes, y tú puedes auditarla/mejorarla."
        else:
            problema = "No tienen página web. Diles que están perdiendo visibilidad en Google frente a su competencia y tú puedes crearles una atractiva."

        prompt = f"Eres experto en ventas de desarrollo web. Escribe un email corto, directo y muy educado (máximo 4 líneas) para el negocio '{nombre}'. {problema} Propón una breve llamada de 5 minutos. No uses saludos corporativos aburridos."
        
        respuesta = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return respuesta.text
    except Exception as e:
        return f"Error al generar con IA: {e}"

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
        st.error(f"Error enviando correo: {e}")
        return False

# ================= INTERFAZ PRINCIPAL =================

col1, col2 = st.columns(2)
with col1:
    ciudad_input = st.text_input("📍 Ciudad", "Valencia")
with col2:
    tipo_input = st.selectbox("🏢 Tipo de Negocio", ["dentist", "restaurant", "hospital", "lawyer", "gym"])

if st.button("🔍 Buscar Clientes Potenciales", type="primary", use_container_width=True):
    with st.spinner('Buscando en la base de datos (esto puede tardar unos segundos)...'):
        # Guardamos el resultado en la "memoria" (session_state)
        st.session_state.negocios = buscar_negocios(ciudad_input, tipo_input)
        if not st.session_state.negocios:
            st.warning("No se encontraron resultados o la base de datos tardó mucho en responder.")

# Mostrar los negocios que están en memoria
if st.session_state.negocios:
    st.markdown("---")
    st.subheader("📋 Resultados de la Búsqueda")
    
    for neg in st.session_state.negocios:
        with st.expander(f"🏢 {neg['nombre']}", expanded=True):
            st.write(f"**Web:** {neg['web'] or '❌ No tiene'}")
            st.write(f"**Teléfono:** {neg['telefono']}")
            
            tiene_web = bool(neg['web'])
            email = None
            
            if tiene_web:
                email = extraer_email_de_web(neg['web'])
                
            if email:
                st.success(f"📧 Email de contacto encontrado: {email}")
                
                # Botón para generar mensaje con IA
                if st.button(f"✨ Redactar Email con IA para {neg['nombre']}", key=f"gen_{neg['nombre']}"):
                    if not GEMINI_API_KEY:
                        st.error("Pon tu Gemini API Key a la izquierda primero.")
                    else:
                        mensaje = generar_email(neg['nombre'], tiene_web)
                        # Guardamos el mensaje específico para este negocio
                        st.session_state[f"msg_{neg['nombre']}"] = mensaje

                # Si ya hemos generado el mensaje, lo mostramos y damos opción a enviarlo
                if f"msg_{neg['nombre']}" in st.session_state:
                    st.text_area("Borrador listo para enviar:", st.session_state[f"msg_{neg['nombre']}"], height=150, key=f"text_{neg['nombre']}")
                    
                    if st.button(f"📨 Enviar Correo Oficialmente", type="primary", key=f"send_{neg['nombre']}"):
                        if not EMAIL_SENDER or not EMAIL_PASSWORD:
                            st.error("⚠️ Faltan tus credenciales de Gmail en la barra izquierda.")
                        else:
                            with st.spinner("Enviando..."):
                                exito = enviar_correo(email, f"Digitalización de {neg['nombre']}", st.session_state[f"msg_{neg['nombre']}"])
                                if exito:
                                    st.balloons()
                                    st.success(f"¡Correo enviado a {email} con éxito!")
            else:
                st.warning("No se encontró email. Toca contactar por teléfono o redes sociales.")
