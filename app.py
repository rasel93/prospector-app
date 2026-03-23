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
st.set_page_config(page_title="Agencia Bot 2026", page_icon="💸", layout="wide")
st.title("💸 Máquina de Prospección B2B: Google Maps + Auditoría Deep (Final)")

# Inicializar estado para no perder datos al recargar
if "negocios" not in st.session_state:
    st.session_state.negocios =[]

with st.sidebar:
    st.header("⚙️ Tus Credenciales")
    SERPER_API_KEY = st.text_input("Serper API Key", value=st.secrets.get("SERPER_API_KEY", ""), type="password")
    GEMINI_API_KEY = st.text_input("Gemini API Key", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    EMAIL_SENDER = st.text_input("Tu Correo (Gmail)", value=st.secrets.get("EMAIL_SENDER", ""))
    EMAIL_PASSWORD = st.text_input("Contraseña de App Gmail", value=st.secrets.get("EMAIL_PASSWORD", ""), type="password")
    
    st.markdown("---")
    st.markdown("**¿Por qué funciona esto?**\nCombina datos técnicos reales (Google Lighthouse) con un Copywriting hiper-específico para romper la barrera del SPAM en 2026.")

# ================= 1. MOTOR GOOGLE MAPS =================
def buscar_negocios(ciudad, tipo_negocio):
    if not SERPER_API_KEY:
        st.error("⚠️ Pon tu Serper API Key en la barra lateral.")
        return[]

    url = "https://google.serper.dev/places"
    payload = json.dumps({
        "q": f"{tipo_negocio} en {ciudad}",
        "gl": "es", "hl": "es"
    })
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}

    try:
        respuesta = requests.request("POST", url, headers=headers, data=payload, timeout=15)
        datos = respuesta.json()
        leads =[]
        
        for lugar in datos.get('places',[]):
            web = lugar.get('website')
            telefono = lugar.get('phoneNumber')
            
            # Solo traemos negocios que existan de verdad y tengan algún contacto
            if web or telefono:
                leads.append({
                    'nombre': lugar.get('title', 'Sin Nombre'),
                    'web': web,
                    'telefono': telefono if telefono else 'No disponible',
                    'direccion': lugar.get('address', 'Dirección no disponible')
                })
        return leads[:10] # Top 10 mejores resultados de Google
    except Exception as e:
        st.error(f"Error con Google Maps: {e}")
        return[]

# ================= 2. SCRAPER PROFUNDO DE EMAILS =================
def extraer_email_de_web(url_base):
    if not url_base: return None
    if not url_base.startswith("http"): url_base = "https://" + url_base
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
    
    # Rutas comunes donde los negocios esconden el email
    rutas_a_probar =["", "/contacto", "/contact", "/aviso-legal"]
    emails_encontrados = set()
    
    for ruta in rutas_a_probar:
        url_actual = urljoin(url_base, ruta)
        try:
            response = requests.get(url_actual, headers=headers, timeout=5)
            # Regex avanzado para evitar capturar falsos positivos (imágenes, sentry, etc.)
            emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", response.text)
            for e in emails:
                e_lower = e.lower()
                if not e_lower.endswith(('sentry.io', 'wix.com', 'png', 'jpg', 'jpeg', 'webp', 'gif', 'css', 'js')):
                    emails_encontrados.add(e_lower)
            
            # Si encuentra un email válido, no hace falta buscar en más páginas
            if emails_encontrados:
                return list(emails_encontrados)[0]
        except:
            continue
            
    return None

# ================= 3. AUDITORÍA GOOGLE PAGESPEED =================
def auditar_velocidad_avanzada(url):
    if not url: return None
    if not url.startswith("http"): url = "https://" + url
    try:
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile"
        respuesta = requests.get(api_url, timeout=30).json()
        
        # Extraemos Nota General y el Tiempo Real de carga
        lighthouse = respuesta.get('lighthouseResult', {})
        score = lighthouse['categories']['performance']['score'] * 100
        speed_index = lighthouse['audits']['speed-index']['displayValue'] # Ej: "4.5 s"
        
        return {"score": int(score), "speed_index": speed_index}
    except:
        return None

# ================= 4. INTELIGENCIA ARTIFICIAL (COPYWRITING 2026) =================
def generar_email(nombre, ciudad, nicho, web, datos_auditoria):
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Construimos un contexto híper-específico para que la IA no invente nada
        if datos_auditoria:
            score = datos_auditoria['score']
            speed = datos_auditoria['speed_index']
            
            if score < 50:
                diagnostico = f"La web {web} saca un {score}/100 en el test de Google y tarda {speed} en cargar en móviles. Esto es crítico."
            else:
                diagnostico = f"La web {web} saca un {score}/100 y tarda {speed}. Es mejorable para maximizar la conversión de clientes."
            
            oferta = "Optimización técnica, Mantenimiento mensual para evitar caídas, y campañas de Ads para llenarles la agenda ahora que la web será rápida. Cierre: Grabar un vídeo de 2 mins gratis enseñando los fallos."
            
        elif web:
            diagnostico = f"Tienen la web {web}, pero en 2026 el diseño y la velocidad lo son todo para no perder clientes frente a la competencia."
            oferta = "Renovación/Mantenimiento web + Ads para captación. Cierre: Vídeo auditoría gratis."
        else:
            diagnostico = f"Buscando {nicho} en {ciudad}, me di cuenta de que NO tienen página web. Son invisibles digitalmente."
            oferta = "Creación de web corporativa + Ads en Google para captar la demanda local de inmediato."

        prompt = f"""
        Eres el mejor vendedor de servicios digitales B2B. Vas a escribir un 'Cold Email' al dueño de: {nombre} (que está en {ciudad}).
        
        DATOS REALES DEL CLIENTE (Úsalos para demostrar que has investigado):
        {diagnostico}
        
        LO QUE LE OFRECES:
        {oferta}
        
        REGLAS DE ORO (INCUMPLIRLAS ES FRACASAR):
        1. ASUNTO: Escribe un asunto en minúsculas, de 3-4 palabras, que parezca interno (Ej: problema con web, tu clínica en {ciudad}, error de carga). Empieza la respuesta con "Asunto: [tu asunto]".
        2. CERO FLUFF: Prohibido decir "Hola, espero que estés bien", "Me pongo en contacto", o "Mi nombre es". Ve directo al grano en la primera línea.
        3. LONGITUD: Máximo 4 líneas visuales de texto.
        4. TONO: Directo, empático y experto. Como un mensaje de WhatsApp a un colega de negocios.
        5. EL CIERRE: No le pidas que compre ni pidas una llamada larga. Ofrécele enviarle el vídeo de 2 minutos que ya "tienes pensado grabar" para enseñarle el problema visualmente.
        """
        
        respuesta = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return respuesta.text
    except Exception as e:
        return f"Error de IA: {e}"

# ================= 5. MOTOR DE ENVÍO =================
def enviar_correo(destinatario, cuerpo):
    lineas = cuerpo.split('\n')
    asunto = "Auditoría de tu negocio"
    cuerpo_final = cuerpo
    
    # Extraer el asunto generado por la IA
    for i, linea in enumerate(lineas):
        if linea.lower().startswith("asunto:"):
            asunto = linea[lineas.index(linea)].replace("Asunto:", "").replace("asunto:", "").strip()
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
        return True
    except: return False

# ================= INTERFAZ WEB PRINCIPAL =================
col1, col2 = st.columns(2)
with col1: ciudad_input = st.text_input("📍 Ciudad objetivo", "Madrid")
with col2: nicho_input = st.text_input("🏢 Nicho (Ej: Clínica dental, Arquitecto)", "Clínica dental")

if st.button("🔍 Extraer Leads PRO de Google Maps", type="primary", use_container_width=True):
    with st.spinner('Escaneando Google Maps...'):
        st.session_state.negocios = buscar_negocios(ciudad_input, nicho_input)
        if not st.session_state.negocios:
            st.warning("No se encontraron resultados. Verifica la API Key de Serper.")

if st.session_state.negocios:
    st.markdown("---")
    st.subheader("🎯 Prospectos Encontrados")
    
    for neg in st.session_state.negocios:
        with st.expander(f"🏢 {neg['nombre']} - 📍 {neg['direccion'][:35]}...", expanded=False):
            st.write(f"**Web:** {neg['web'] or '❌ NO TIENE (Cliente ideal para creación web)'}")
            st.write(f"**Teléfono:** {neg['telefono']}")
            
            tiene_web = bool(neg['web'])
            
            # Buscar email con el Scraper Profundo
            if f"email_{neg['nombre']}" not in st.session_state:
                email_encontrado = None
                if tiene_web:
                    with st.spinner("Buscando email en la web y subpáginas..."):
                        email_encontrado = extraer_email_de_web(neg['web'])
                st.session_state[f"email_{neg['nombre']}"] = email_encontrado
            
            email = st.session_state[f"email_{neg['nombre']}"]
            
            if email:
                st.success(f"📧 Email validado: **{email}**")
                
                # BOTÓN: AUDITORÍA + IA
                if st.button(f"🚀 Auditar Técnicamente y Escribir Propuesta", key=f"gen_{neg['nombre']}", type="primary"):
                    datos_auditoria = None
                    if tiene_web:
                        with st.spinner("Conectando con Google Lighthouse (Midiendo velocidad real)..."):
                            datos_auditoria = auditar_velocidad_avanzada(neg['web'])
                            
                            if datos_auditoria:
                                col_a, col_b = st.columns(2)
                                col_a.metric("Nota Google (Móvil)", f"{datos_auditoria['score']}/100")
                                col_b.metric("Tiempo de Carga Real", f"{datos_auditoria['speed_index']}")
                    
                    with st.spinner("Redactando el cold email basado en los fallos técnicos..."):
                        mensaje = generar_email(neg['nombre'], ciudad_input, nicho_input, neg['web'], datos_auditoria)
                        st.session_state[f"msg_{neg['nombre']}"] = mensaje
                
                # MOSTRAR EMAIL Y ENVIAR
                if f"msg_{neg['nombre']}" in st.session_state:
                    st.text_area("Copia o edita el mensaje antes de enviar:", st.session_state[f"msg_{neg['nombre']}"], height=250, key=f"text_{neg['nombre']}")
                    
                    if st.button(f"📨 Enviar Correo a {neg['nombre']}", key=f"send_{neg['nombre']}"):
                        if enviar_correo(email, st.session_state[f"msg_{neg['nombre']}"]):
                            st.balloons()
                            st.success("✅ ¡Disparo completado! Email en su bandeja de entrada.")
                        else: 
                            st.error("❌ Error de SMTP. Revisa tu contraseña de Aplicación de Gmail.")
            else: 
                if tiene_web:
                    st.warning("⚠️ No se encontró email público (ni en la home ni en /contacto). Sugerencia: Llámales al " + neg['telefono'])
                else:
                    st.info("💡 Este negocio necesita una web urgente. Haz Cold Calling al " + neg['telefono'])
