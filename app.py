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
st.title("📈 Máquina B2B: Datos Reales + Nube (V11 Corrección)")

if "negocios" not in st.session_state:
    st.session_state.negocios =[]

# ================= CREDENCIALES =================
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

# ================= BASE DE DATOS EN LA NUBE SEGURA =================
def cargar_contactados_nube():
    if not JSONBIN_KEY or not JSONBIN_BIN_ID: return[]
    try:
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}?meta=false"
        headers = {'X-Master-Key': JSONBIN_KEY}
        req = requests.get(url, headers=headers)
        if req.status_code == 200:
            datos = req.json()
            if isinstance(datos, list): return datos
            elif isinstance(datos, dict) and 'record' in datos: return datos['record']
            else: return[]
        return[]
    except: return[]

def registrar_contactado_nube(nombre, email):
    if not JSONBIN_KEY or not JSONBIN_BIN_ID: return
    lista_actual = cargar_contactados_nube()
    if not isinstance(lista_actual, list): lista_actual =[]
    lista_actual.append({"nombre": nombre.lower(), "email": email})
    try:
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
        headers = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_KEY}
        requests.put(url, json=lista_actual, headers=headers)
    except: pass

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
        if respuesta.status_code != 200:
            st.error(f"❌ Error Serper: {respuesta.text}")
            return[]
            
        datos = respuesta.json()
        leads =[]
        datos_nube = cargar_contactados_nube()
        lista_negra = [c['nombre'].lower() for c in datos_nube if isinstance(c, dict) and 'nombre' in c]
        
        for lugar in datos.get('places',[]):
            nombre = lugar.get('title', 'Sin Nombre')
            web = lugar.get('website')
            telefono = lugar.get('phoneNumber')
            
            if nombre.lower() in lista_negra: continue
                
            if web or telefono:
                leads.append({'nombre': nombre, 'web': web, 'telefono': telefono if telefono else 'No disponible'})
        return leads[:10]
    except: return[]

# ================= EXTRAER EMAILS =================
def extraer_email_de_web(url_base):
    if not url_base: return None
    if not url_base.startswith("http"): url_base = "https://" + url_base
    headers = {'User-Agent': 'Mozilla/5.0'}
    for ruta in ["", "/contacto", "/aviso-legal"]:
        try:
            res = requests.get(urljoin(url_base, ruta), headers=headers, timeout=5)
            emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", res.text)
            emails =[e.lower() for e in emails if not e.lower().endswith(('sentry.io', 'wix.com', 'png', 'jpg'))]
            if emails: return emails[0]
        except: continue
    return None

# ================= AUDITORÍA LCP =================
def auditar_velocidad_avanzada(url):
    if not url: return None
    if not url.startswith("http"): url = "https://" + url
    try:
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile"
        res = requests.get(api_url, timeout=20).json() # Timeout ajustado
        lighthouse = res.get('lighthouseResult', {})
        score = int(lighthouse['categories']['performance']['score'] * 100)
        lcp = lighthouse['audits']['largest-contentful-paint']['displayValue']
        return {"score": score, "lcp": lcp}
    except: return None # Devuelve None si la web bloquea a Google o tarda mucho

# ================= IA (CORREGIDA) =================
def generar_email(nombre, web, datos_auditoria):
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # PLAN A: Tiene web y Google logró escanearla
    if web and datos_auditoria:
        score = datos_auditoria['score']
        lcp = datos_auditoria['lcp']
        prompt = f"""
        Escribe un email súper corto a '{nombre}'. Su web es '{web}'.
        
        INSTRUCCIONES CRÍTICAS:
        1. Escribe EXACTAMENTE esto en la línea 1: "Asunto: problema técnico en tu web" (SIN ASTERISCOS).
        2. Tono directo de negocios. CERO saludos tipo "Hola".
        3. El texto DEBE contener: "Tarda {lcp} en cargar en móviles" y "La nota de Google es {score}/100".
        4. Problema: Si tarda esos {lcp}, más del 50% de visitas pagadas de anuncios se van.
        5. Solución: Optimización, mantenimiento mensual y gestión de Ads.
        6. Cierre: Diles que has grabado un vídeo de 2 mins enseñando el error técnico y pregúntales si se lo pasas.
        """
    # PLAN B: Tiene web pero el escáner de Google falló (firewall/lentitud)
    elif web:
        prompt = f"""
        Escribe un email súper corto a '{nombre}'. Su web es '{web}'.
        
        INSTRUCCIONES CRÍTICAS:
        1. Escribe EXACTAMENTE esto en la línea 1: "Asunto: error de captación en tu web" (SIN ASTERISCOS).
        2. Tono directo de negocios. CERO saludos tipo "Hola" o "Espero que estés bien".
        3. Problema: Dile que has entrado a su web desde el móvil y has notado bloqueos de carga y diseño poco optimizado para conversiones. En 2026 una web así pierde la mitad de sus clientes potenciales.
        4. Solución: Desarrollo ultrarrápido, mantenimiento y Google Ads.
        5. Cierre: Has grabado un vídeo de 2 mins enseñando los fallos visuales que tiene la web. ¿Se lo envías?
        """
    # PLAN C: No tiene web
    else:
        prompt = f"""
        Escribe un email en frío a '{nombre}'. No tienen web.
        INSTRUCCIONES CRÍTICAS:
        1. Escribe EXACTAMENTE esto en la línea 1: "Asunto: clientes en internet" (SIN ASTERISCOS).
        2. Cero saludos. Ve al grano.
        3. Mensaje: He buscado vuestros servicios y no tenéis página web. En 2026, no estar posicionado es cederle todos vuestros clientes a la competencia.
        4. Solución: Diseño de web optimizada y captación con Google Ads.
        5. Cierre: He grabado un vídeo enseñando cómo lo aplico en vuestro sector. ¿Os lo envío?
        """
        
    try:
        respuesta = client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text
        # Limpieza de seguridad: Borramos los asteriscos de markdown que pone la IA
        return respuesta.replace('**', '')
    except Exception as e: return f"Error IA: {e}"

# ================= MOTOR DE ENVÍO =================
def enviar_correo_y_registrar(destinatario, cuerpo, nombre_negocio):
    # Asegurarnos de limpiar negritas por si acaso
    cuerpo = cuerpo.replace('**', '')
    lineas = cuerpo.strip().split('\n')
    asunto = "Mejoras para tu negocio"
    cuerpo_final = cuerpo
    
    # Busca la línea del Asunto aunque haya saltos de línea al principio
    for i, linea in enumerate(lineas):
        if linea.lower().startswith("asunto:"):
            asunto = linea.replace("Asunto:", "").replace("asunto:", "").strip()
            cuerpo_final = '\n'.join(lineas[i+1:]).strip()
            break

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
        
        registrar_contactado_nube(nombre_negocio, destinatario)
        return True
    except: return False

# ================= INTERFAZ WEB =================
col1, col2 = st.columns(2)
with col1: ciudad_input = st.text_input("📍 Ciudad", "Madrid")
with col2: nicho_input = st.text_input("🏢 Nicho", "Clínica dental")

if st.button("🔍 Extraer Leads (Cruzar con Nube)", type="primary", use_container_width=True):
    with st.spinner('Escaneando Google Maps y cruzando con tu Nube...'):
        st.session_state.negocios = buscar_negocios(ciudad_input, nicho_input)
        if not st.session_state.negocios:
            st.info("Todos los negocios ya han sido contactados o la búsqueda no dio resultados.")

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
                        with st.spinner("Midiendo el 'LCP' (Si la web bloquea a Google, activará el Plan B)..."):
                            datos_auditoria = auditar_velocidad_avanzada(neg['web'])
                            
                            if datos_auditoria:
                                col_a, col_b = st.columns(2)
                                col_a.metric("Nota Google Mobile", f"{datos_auditoria['score']}/100")
                                col_b.metric("Carga Real (LCP)", f"{datos_auditoria['lcp']}")
                            else:
                                st.warning("⚠️ La web bloqueó el escáner de Google (Firewall/Lentitud). Activando Plan B...")
                    
                    with st.spinner("Redactando el email..."):
                        st.session_state[f"msg_{neg['nombre']}"] = generar_email(neg['nombre'], neg['web'], datos_auditoria)
                
                if f"msg_{neg['nombre']}" in st.session_state:
                    st.text_area("Edita antes de enviar:", st.session_state[f"msg_{neg['nombre']}"], height=200, key=f"text_{neg['nombre']}")
                    
                    if st.button(f"📨 Enviar Email y Guardar en Nube", key=f"send_{neg['nombre']}"):
                        if enviar_correo_y_registrar(email, st.session_state[f"msg_{neg['nombre']}"], neg['nombre']):
                            st.balloons()
                            st.success("✅ ¡Enviado y registrado en la nube! No volverá a aparecer.")
                        else: 
                            st.error("❌ Error de envío con Gmail.")
            else: 
                st.warning(f"⚠️ No hay email en la web. Ideal para llamar al {neg['telefono']}")
                if st.button("🗑️ Descartar Lead en la Nube", key=f"desc_{neg['nombre']}"):
                    registrar_contactado_nube(neg['nombre'], "Descartado")
                    st.success("Guardado en tu lista negra. Ya no aparecerá al buscar.")
