import streamlit as st
import requests
import re
import json
import smtplib
from urllib.parse import urljoin
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai

# ================= CONFIGURACIÓN DE PÁGINA =================
st.set_page_config(page_title="Agencia Bot 2026", page_icon="📈", layout="wide")
st.title("📈 Máquina B2B: Datos Reales + Nube Permanente")

if "negocios" not in st.session_state:
    st.session_state.negocios =[]

# ================= CREDENCIALES (Añadido JSONBin para Nube) =================
with st.sidebar:
    st.header("⚙️ Tus Credenciales")
    SERPER_API_KEY = st.text_input("Serper API Key (Maps)", value=st.secrets.get("SERPER_API_KEY", ""), type="password")
    GEMINI_API_KEY = st.text_input("Gemini API Key (IA)", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    EMAIL_SENDER = st.text_input("Tu Correo (Gmail)", value=st.secrets.get("EMAIL_SENDER", ""))
    EMAIL_PASSWORD = st.text_input("Contraseña App Gmail", value=st.secrets.get("EMAIL_PASSWORD", ""), type="password")
    
    st.markdown("---")
    st.subheader("☁️ Base de Datos Permanente")
    JSONBIN_KEY = st.text_input("JSONBin Master Key", value=st.secrets.get("JSONBIN_KEY", ""), type="password")
    JSONBIN_BIN_ID = st.text_input("JSONBin Bin ID", value=st.secrets.get("JSONBIN_BIN_ID", ""))

# ================= BASE DE DATOS EN LA NUBE (ANTI-PÉRDIDA) =================
def cargar_contactados_nube():
    if not JSONBIN_KEY or not JSONBIN_BIN_ID:
        return[]
    try:
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}?meta=false"
        headers = {'X-Master-Key': JSONBIN_KEY}
        req = requests.get(url, headers=headers)
        if req.status_code == 200:
            return req.json() # Retorna la lista []
        return []
    except:
        return[]

def registrar_contactado_nube(nombre, email):
    if not JSONBIN_KEY or not JSONBIN_BIN_ID:
        st.error("No tienes configurado JSONBin. El dato no se guardará permanentemente.")
        return
    
    lista_actual = cargar_contactados_nube()
    lista_actual.append({"nombre": nombre.lower(), "email": email})
    
    try:
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
        headers = {
            'Content-Type': 'application/json',
            'X-Master-Key': JSONBIN_KEY
        }
        requests.put(url, json=lista_actual, headers=headers)
    except Exception as e:
        st.error(f"Error al guardar en la nube: {e}")

# ================= MOTOR DE BÚSQUEDA GOOGLE MAPS =================
def buscar_negocios(ciudad, tipo_negocio):
    if not SERPER_API_KEY:
        st.error("⚠️ Falta la API Key de Serper.")
        return[]

    url = "https://google.serper.dev/places"
    payload = json.dumps({"q": f"{tipo_negocio} en {ciudad}", "gl": "es", "hl": "es"})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}

    try:
        respuesta = requests.request("POST", url, headers=headers, data=payload, timeout=15)
        datos = respuesta.json()
        leads =[]
        
        # Leemos la NUBE para saber a quién NO debemos volver a mostrar
        lista_negra = [c['nombre'] for c in cargar_contactados_nube()]
        
        for lugar in datos.get('places',[]):
            nombre = lugar.get('title', 'Sin Nombre')
            web = lugar.get('website')
            telefono = lugar.get('phoneNumber')
            
            # FILTRO ANTI-DUPLICADOS (Desde la Nube)
            if nombre.lower() in lista_negra:
                continue
                
            if web or telefono:
                leads.append({
                    'nombre': nombre,
                    'web': web,
                    'telefono': telefono if telefono else 'No disponible'
                })
        return leads[:10]
    except Exception as e:
        return[]

# ================= EXTRAER EMAILS =================
def extraer_email_de_web(url_base):
    if not url_base: return None
    if not url_base.startswith("http"): url_base = "https://" + url_base
    headers = {'User-Agent': 'Mozilla/5.0'}
    rutas = ["", "/contacto", "/aviso-legal"]
    
    for ruta in rutas:
        try:
            res = requests.get(urljoin(url_base, ruta), headers=headers, timeout=5)
            emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", res.text)
            emails =[e.lower() for e in emails if not e.lower().endswith(('sentry.io', 'wix.com', 'png', 'jpg'))]
            if emails: return emails[0]
        except: continue
    return None

# ================= AUDITORÍA LCP (DATOS 100% REALES GOOGLE) =================
def auditar_velocidad_avanzada(url):
    """ Extrae el Largest Contentful Paint (LCP), la métrica de carga más estricta de Google """
    if not url: return None
    if not url.startswith("http"): url = "https://" + url
    try:
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile"
        res = requests.get(api_url, timeout=30).json()
        lighthouse = res.get('lighthouseResult', {})
        
        # Nota sobre 100
        score = int(lighthouse['categories']['performance']['score'] * 100)
        
        # Tiempo REAL en cargar el contenido más grande (LCP)
        lcp = lighthouse['audits']['largest-contentful-paint']['displayValue']
        
        return {"score": score, "lcp": lcp}
    except: return None

# ================= IA RESTRINGIDA (SIN ROBOTIZAR) =================
def generar_email(nombre, web, datos_auditoria):
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    if datos_auditoria:
        score = datos_auditoria['score']
        lcp = datos_auditoria['lcp'] # Ej: "4.2 s"
        
        prompt = f"""
        Escribe un email súper corto a '{nombre}'. Su web es '{web}'.
        
        INSTRUCCIONES CRÍTICAS (No inventes ni adornes nada):
        1. Asunto obligatorio (Escribe "Asunto: " en la línea 1): "problema técnico en tu web"
        2. Tono: Directo y de negocios. PROHIBIDO decir "Hola" o "Espero que estés bien".
        3. El texto DEBE contener estos datos exactos y verídicos de Google Lighthouse:
           - Tarda {lcp} en cargar en móviles.
           - La nota de rendimiento es {score}/100.
        4. Plantea el problema: En 2026, si una web tarda esos {lcp}, más del 50% de las visitas pagadas de anuncios se van.
        5. Ofrece la solución de forma directa: Optimización web, mantenimiento mensual continuo y gestión de campañas de Google Ads rentables.
        6. Cierre (Llamada a la acción): Diles que has grabado un vídeo rápido de 2 minutos enseñando su error técnico en pantalla y pregúntales si se lo puedes enviar para que lo vean sin compromiso.
        """
    else:
        prompt = f"""
        Escribe un email en frío a '{nombre}'. No tienen web.
        INSTRUCCIONES CRÍTICAS:
        1. Asunto: "clientes en internet"
        2. Prohibidos los saludos ("Hola", "Qué tal"). Ve al grano en la primera línea.
        3. Mensaje: He buscado vuestros servicios y veo que no tenéis página web. En 2026, no estar posicionado significa cederle todos vuestros clientes a la competencia.
        4. Solución: Diseño de web optimizada y captación de clientes inmediatos con Google Ads.
        5. Cierre: He grabado un vídeo de 2 minutos enseñando cómo lo aplico en vuestro sector. ¿Os lo envío sin compromiso?
        """
        
    try:
        return client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text
    except Exception as e: return f"Error IA: {e}"

# ================= MOTOR DE ENVÍO Y BASE DE DATOS =================
def enviar_correo_y_registrar(destinatario, cuerpo, nombre_negocio):
    lineas = cuerpo.strip().split('\n')
    asunto = "Mejoras para tu negocio"
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
        
        # GUARDAR EN LA NUBE PARA SIEMPRE
        registrar_contactado_nube(nombre_negocio, destinatario)
        return True
    except: return False

# ================= INTERFAZ WEB =================
col1, col2 = st.columns(2)
with col1: ciudad_input = st.text_input("📍 Ciudad", "Madrid")
with col2: nicho_input = st.text_input("🏢 Nicho", "Clínica dental")

if st.button("🔍 Extraer Leads (Cruzar con Nube)", type="primary", use_container_width=True):
    if not JSONBIN_KEY or not JSONBIN_BIN_ID:
        st.warning("⚠️ Ojo: No has configurado JSONBin. La app funcionará pero no recordará a quién descartaste si se reinicia el servidor.")
        
    with st.spinner('Escaneando Google Maps y cruzando con tu base de datos en la nube...'):
        st.session_state.negocios = buscar_negocios(ciudad_input, nicho_input)
        if not st.session_state.negocios:
            st.info("Todos los negocios ya han sido contactados o no hay resultados.")

if st.session_state.negocios:
    st.markdown("---")
    for neg in st.session_state.negocios:
        with st.expander(f"🏢 {neg['nombre']}", expanded=False):
            st.write(f"**Web:** {neg['web'] or '❌ NO TIENE'}")
            st.write(f"**Teléfono:** {neg['telefono']}")
            
            tiene_web = bool(neg['web'])
            
            if f"email_{neg['nombre']}" not in st.session_state:
                st.session_state[f"email_{neg['nombre']}"] = extraer_email_de_web(neg['web']) if tiene_web else None
            
            email = st.session_state[f"email_{neg['nombre']}"]
            
            if email:
                st.success(f"📧 Email validado: **{email}**")
                
                if st.button(f"🚀 Extraer LCP de Google y Generar Informe", key=f"gen_{neg['nombre']}", type="primary"):
                    datos_auditoria = None
                    if tiene_web:
                        with st.spinner("Midiendo el 'Largest Contentful Paint' (segundos reales)..."):
                            datos_auditoria = auditar_velocidad_avanzada(neg['web'])
                            if datos_auditoria:
                                col_a, col_b = st.columns(2)
                                col_a.metric("Nota Google Mobile", f"{datos_auditoria['score']}/100")
                                col_b.metric("Carga Real (LCP)", f"{datos_auditoria['lcp']}")
                    
                    with st.spinner("La IA está inyectando los datos matemáticos en el mensaje..."):
                        st.session_state[f"msg_{neg['nombre']}"] = generar_email(neg['nombre'], neg['web'], datos_auditoria)
                
                if f"msg_{neg['nombre']}" in st.session_state:
                    st.text_area("Edita antes de enviar:", st.session_state[f"msg_{neg['nombre']}"], height=180, key=f"text_{neg['nombre']}")
                    
                    if st.button(f"📨 Enviar Email y Guardar en Nube", key=f"send_{neg['nombre']}"):
                        if enviar_correo_y_registrar(email, st.session_state[f"msg_{neg['nombre']}"], neg['nombre']):
                            st.balloons()
                            st.success("✅ ¡Enviado y registrado en la nube! No volverá a aparecer.")
                        else: 
                            st.error("❌ Error de envío con Gmail.")
            else: 
                st.warning(f"⚠️ No hay email en la web. Cold Calling: {neg['telefono']}")
                if st.button("🗑️ Descartar en la Nube", key=f"desc_{neg['nombre']}"):
                    registrar_contactado_nube(neg['nombre'], "Descartado")
                    st.success("Guardado en tu lista negra en la nube.")
