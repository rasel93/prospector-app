import streamlit as st
import requests
import re
import json
import smtplib
import time
from urllib.parse import urljoin
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai

# ================= CONFIGURACIÓN DE PÁGINA =================
st.set_page_config(page_title="Agencia Bot 2026", page_icon="⚡", layout="wide")
st.title("⚡ Máquina B2B: Google + Test de Servidor (V13)")

if "negocios" not in st.session_state:
    st.session_state.negocios =[]

# ================= CREDENCIALES =================
with st.sidebar:
    st.header("⚙️ Tus Credenciales")
    SERPER_API_KEY = st.text_input("Serper API Key", value=st.secrets.get("SERPER_API_KEY", ""), type="password")
    GEMINI_API_KEY = st.text_input("Gemini API Key", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    EMAIL_SENDER = st.text_input("Tu Correo", value=st.secrets.get("EMAIL_SENDER", ""))
    EMAIL_PASSWORD = st.text_input("Contraseña App", value=st.secrets.get("EMAIL_PASSWORD", ""), type="password")
    
    st.markdown("---")
    st.subheader("☁️ Nube Permanente (JSONBin)")
    JSONBIN_KEY = st.text_input("Master Key", value=st.secrets.get("JSONBIN_KEY", ""), type="password")
    JSONBIN_BIN_ID = st.text_input("Bin ID", value=st.secrets.get("JSONBIN_BIN_ID", ""))

# ================= BASE DE DATOS EN LA NUBE =================
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

# ================= BÚSQUEDA =================
def buscar_negocios(ciudad, tipo_negocio):
    if not SERPER_API_KEY:
        st.error("⚠️ Falta la API Key de Serper.")
        return[]
    url = "https://google.serper.dev/places"
    payload = json.dumps({"q": f"{tipo_negocio} en {ciudad}", "gl": "es", "hl": "es"})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        respuesta = requests.request("POST", url, headers=headers, data=payload, timeout=15)
        if respuesta.status_code != 200: return[]
        datos = respuesta.json()
        leads =[]
        datos_nube = cargar_contactados_nube()
        lista_negra = [c['nombre'].lower() for c in datos_nube if isinstance(c, dict) and 'nombre' in c]
        for lugar in datos.get('places',[]):
            nombre = lugar.get('title', 'Sin Nombre')
            web = lugar.get('website')
            telefono = lugar.get('phoneNumber')
            if nombre.lower() in lista_negra: continue
            if web or telefono: leads.append({'nombre': nombre, 'web': web, 'telefono': telefono if telefono else 'No disponible'})
        return leads[:10]
    except: return[]

# ================= EXTRAER EMAILS =================
def extraer_email_de_web(url_base):
    if not url_base: return None
    if not url_base.startswith("http"): url_base = "https://" + url_base
    headers = {'User-Agent': 'Mozilla/5.0'}
    for ruta in["", "/contacto", "/aviso-legal"]:
        try:
            res = requests.get(urljoin(url_base, ruta), headers=headers, timeout=6)
            emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", res.text)
            emails =[e.lower() for e in emails if not e.lower().endswith(('sentry.io', 'wix.com', 'png', 'jpg'))]
            if emails: return emails[0]
        except: continue
    return None

# ================= MOTOR 1: GOOGLE PAGESPEED =================
def auditar_google(url):
    if not url.startswith("http"): url = "https://" + url
    try:
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile"
        res = requests.get(api_url, timeout=35)
        if res.status_code != 200: return None
        lighthouse = res.json().get('lighthouseResult', {})
        score = int(lighthouse['categories']['performance']['score'] * 100)
        lcp = lighthouse['audits']['largest-contentful-paint']['displayValue']
        return {"motor": "google", "score": f"{score}/100", "metrica": lcp}
    except: return None

# ================= MOTOR 2: TEST DE SERVIDOR (ESTILO PINGDOM) =================
def auditar_servidor(url):
    if not url.startswith("http"): url = "https://" + url
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        inicio = time.time()
        res = requests.get(url, headers=headers, timeout=15)
        fin = time.time()
        
        tiempo_respuesta = round(fin - inicio, 2)
        peso_kb = round(len(res.content) / 1024, 2) # Calculamos el peso en KB
        
        return {"motor": "ping", "score": f"{peso_kb} KB", "metrica": f"{tiempo_respuesta} s"}
    except: return None

# ================= IA HÍBRIDA =================
def generar_email(nombre, web, datos_auditoria):
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    if web and datos_auditoria:
        if datos_auditoria['motor'] == "google":
            score = datos_auditoria['score']
            tiempo = datos_auditoria['metrica']
            prompt = f"""
            Escribe a '{nombre}'. Su web '{web}'.
            INSTRUCCIONES:
            1. Empieza EXACTAMENTE con: "Asunto: problema de carga en vuestra web"
            2. Cero saludos.
            3. Datos: "Google penaliza webs lentas. Vuestra página tarda {tiempo} en cargar en móviles y tiene una nota de {score} en el test de Google."
            4. Oferta: Optimización técnica, mantenimiento mensual y captación con Google Ads.
            5. Cierre: He grabado un vídeo de 2 mins enseñando los fallos técnicos. ¿Lo envío por aquí?
            """
        else: # Motor Ping
            peso = datos_auditoria['score']
            tiempo = datos_auditoria['metrica']
            prompt = f"""
            Escribe a '{nombre}'. Su web '{web}'.
            INSTRUCCIONES:
            1. Empieza EXACTAMENTE con: "Asunto: problema en el servidor web"
            2. Cero saludos.
            3. Datos reales: "Le he pasado un test de latencia al servidor de vuestra web y tarda {tiempo} en responder, descargando {peso} de código base. Esto es muy lento para los estándares de 2026 y está matando la conversión de clientes."
            4. Oferta: Migración/Optimización web, mantenimiento y llenarles la agenda con anuncios de Google Ads rentables.
            5. Cierre: He grabado un vídeo rápido de 2 minutos enseñando el problema técnico. ¿Os lo envío por aquí?
            """
    elif web:
        prompt = f"""
        Escribe a '{nombre}'. Su web '{web}'.
        INSTRUCCIONES:
        1. Empieza con: "Asunto: error de captación online"
        2. Cero saludos.
        3. Problema: He entrado a vuestra web y tiene bloqueos técnicos. En 2026 eso hace perder al 50% de los clientes.
        4. Oferta: Desarrollo, mantenimiento y Ads.
        5. Cierre: Vídeo de 2 mins enseñando los fallos. ¿Lo envío?
        """
    else:
        prompt = f"""
        Escribe a '{nombre}'. No tienen web.
        INSTRUCCIONES:
        1. Empieza con: "Asunto: clientes en internet"
        2. Cero saludos.
        3. Mensaje: He buscado vuestros servicios y no tenéis página web. En 2026, no estar posicionado es perder ventas aseguradas.
        4. Solución: Diseño de web optimizada y campañas de captación en Google Ads.
        5. Cierre: He grabado un vídeo enseñando mi método en vuestro sector. ¿Os lo envío?
        """
        
    try:
        respuesta = client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text
        return respuesta.replace('**', '')
    except Exception as e: return f"Error IA: {e}"

# ================= MOTOR DE ENVÍO =================
def enviar_correo_y_registrar(destinatario, cuerpo, nombre_negocio):
    cuerpo = cuerpo.replace('**', '')
    lineas = cuerpo.strip().split('\n')
    asunto = "Mejoras para tu negocio"
    cuerpo_final = cuerpo
    
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

if st.button("🔍 Extraer Leads Seguros", type="primary", use_container_width=True):
    with st.spinner('Buscando prospectos frescos...'):
        st.session_state.negocios = buscar_negocios(ciudad_input, nicho_input)
        if not st.session_state.negocios:
            st.info("Sin resultados o todos contactados.")

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
                
                if st.button(f"🚀 Lanzar Escáner Híbrido (Google/Ping)", key=f"gen_{neg['nombre']}", type="primary"):
                    datos_auditoria = None
                    if tiene_web:
                        with st.spinner("Probando Motor 1: Google PageSpeed..."):
                            datos_auditoria = auditar_google(neg['web'])
                        
                        if not datos_auditoria:
                            st.warning("⚠️ Google bloqueado o muy lento. Lanzando Motor 2: Test de Latencia (Estilo Pingdom)...")
                            with st.spinner("Midiendo respuesta del servidor..."):
                                datos_auditoria = auditar_servidor(neg['web'])
                        
                        if datos_auditoria:
                            col_a, col_b = st.columns(2)
                            if datos_auditoria['motor'] == "google":
                                col_a.metric("Nota Google Mobile", datos_auditoria['score'])
                                col_b.metric("Carga Real (LCP)", datos_auditoria['metrica'])
                            else:
                                col_a.metric("Peso Base (HTML)", datos_auditoria['score'])
                                col_b.metric("Respuesta Servidor (TTFB)", datos_auditoria['metrica'])
                                st.info("ℹ️ Datos extraídos directamente del servidor del cliente mediante PING de latencia.")
                    
                    with st.spinner("Redactando propuesta letal..."):
                        st.session_state[f"msg_{neg['nombre']}"] = generar_email(neg['nombre'], neg['web'], datos_auditoria)
                
                if f"msg_{neg['nombre']}" in st.session_state:
                    st.text_area("Edita antes de enviar:", st.session_state[f"msg_{neg['nombre']}"], height=200, key=f"text_{neg['nombre']}")
                    
                    if st.button(f"📨 Enviar Email y Guardar", key=f"send_{neg['nombre']}"):
                        if enviar_correo_y_registrar(email, st.session_state[f"msg_{neg['nombre']}"], neg['nombre']):
                            st.balloons()
                            st.success("✅ ¡Registrado en tu Nube y enviado!")
                        else: st.error("❌ Error SMTP.")
            else: 
                st.warning(f"⚠️ Sin email público. Llamar al {neg['telefono']}")
                if st.button("🗑️ Descartar Lead", key=f"desc_{neg['nombre']}"):
                    registrar_contactado_nube(neg['nombre'], "Descartado")
                    st.success("Guardado en la lista negra.")
