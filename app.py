import base64
import json
import io
import streamlit as st
from openai import OpenAI
from streamlit_mic_recorder import mic_recorder
from PIL import Image, ImageDraw
from streamlit_image_coordinates import streamlit_image_coordinates



# --- 4. CONTROLLO ACCESSO MULTI-UTENTE (IMPRENDO MORPHEUS) ---
def login():
    if "user_data" not in st.session_state:
        st.session_state.user_data = None

    if st.session_state.user_data:
        return st.session_state.user_data

    st.title("🔒 Imprendo")
    st.write("### Il tuo Assistente AI per la sicurezza nei cantieri")
    
    username = st.text_input(
        "Username (Nome)", 
        key="login_username", 
        autocomplete="username"
    ).lower().strip()
    
    password = st.text_input(
        "Password", 
        type="password", 
        key="login_password", 
        autocomplete="current-password"
    )
    
    if st.button("Accedi", use_container_width=True):
        if "utenti" in st.secrets and username in st.secrets["utenti"]:
            db_user = st.secrets["utenti"][username]
            if password == db_user["password"]:
                real_name = db_user.get("nome", username.capitalize())
                # CORREZIONE: Estraiamo anche il campo 'id' dal record dell'utente nei secrets
                st.session_state.user_data = {
                    "username": username, 
                    "email": db_user["email"], 
                    "nome": real_name,
                    "id": db_user.get("id", "") 
                }
                st.rerun()
            else:
                st.error(f"❌ **Password errata!** Prova a cliccare sul campo e riprova ad accedere.")
        else:
            st.error(f"❌ **Utente non trovato!** Prova a cliccare sul campo e riprova ad accedere.")
    return None




def disegna_punti_critici(image_bytes, lista_punti, abilita_marker=True):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Se i marker sono disabilitati salta la funzione
    if not abilita_marker:
        return img
    
    else:
        draw = ImageDraw.Draw(img)
        width, height = img.size
        #colori = ["red", "blue", "yellow", "cyan", "magenta", "lime", "orange", "purple"]
        colore = "red"
        
        for i, punto in enumerate(lista_punti):
            #colore = colori[i % len(colori)]
            coord = punto.get('coordinate', {'x': 50, 'y': 50})
            x_raw = coord.get('x')
            y_raw = coord.get('y')

            # --- FIX: Se x o y sono None, salta questo punto ---
            if x_raw is None or y_raw is None:
                continue

            size = 30
            
            # --- CORREZIONE: Normalizzazione dinamica ---
            x_raw = coord.get('x', 40)
            y_raw = coord.get('y', 50)
            x = (x_raw / 1000) * width if x_raw > 100 else (x_raw / 100) * width
            y = (y_raw / 1000) * height if y_raw > 100 else (y_raw / 100) * height
            
            # Disegna cerchio e testo
            draw.ellipse([x-size, y-size, x+size, y+size], outline=colore, width=3)
            draw.text((x, y), str(i + 1), fill=colore, font_size=40, anchor="mm")
            
        return img


def analizza_sicurezza_cantiere(audio_bytes, image_file):
    """
    Analizza una singola immagine e le note vocali.
    image_file: l'oggetto file di streamlit (quello che ha .name e .getvalue())
    """
    client = OpenAI(api_key=st.secrets["openai_key"])
    
    # 1. Trascrizione vocale
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.wav"
    transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
    
    # PROMPT ORIGINALE (Mantenuto identico)
    system_prompt = """
    Sei un Ispettore Tecnico della Sicurezza (D.Lgs 81/08).
    
    Tuo compito:
    1. Analizza l'immagine e le note vocali dell'ispettore.
    2. ELABORAZIONE DISCORSO: Trasforma la trascrizione vocale dell'ispettore in un "Verbale Tecnico Formale" sintetico, professionale e preciso (rimuovi intercalari, ripetizioni o linguaggio colloquiale).
    3. Identifica i punti critici dell'audio e mappali su coordinate in pixel (x,y).
    4. Identifica autonomamente ulteriori criticità (segnali come 'AI Integrativa').
    5. Determina l'oggetto delle analisi in circa 5 parole.
    6. Il "riassunto_generale" deve essere di 10 parole massimo.
    
    Restituisci JSON: 
    {
        "verbale_tecnico": "Il testo rielaborato e formale basato sulle note vocali",
        "riassunto_generale": "...",
        "punti_critici": [
            {
                "elemento": "...",
                "origine": "Ispettore" o "AI Integrativa",
                "commento": "...",
                "rischio": "...",
                "urgenza": "...",
                "coordinate": {"x": 50, "y": 50},
                "oggetto": "..."
            }
        ]
    }
    """

    
    # 2. Codifica immagine
    b64 = base64.b64encode(image_file.getvalue()).decode('utf-8')
    
    payload = [
        {"type": "text", "text": f"Note vocali ispettore: {transcript.text}"},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
    ]
    
    # 3. Chiamata API
    resp = client.chat.completions.create(
        model="gpt-4o", 
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": payload}], 
        response_format={"type": "json_object"}
    )
    
    dati = json.loads(resp.choices[0].message.content)
    
    # Usiamo il "verbale_tecnico" generato dall'AI come testo finale
    testo_formale = dati.get("verbale_tecnico", transcript.text) 
    
    report_completo = {
        "riassunto_generale": dati.get("riassunto_generale", ""),
        "analisi_per_immagine": [{
            "nome_file": image_file.name, 
            "punti_critici": dati.get("punti_critici", [])
        }]
    }
        
    return report_completo, testo_formale



def integra_sicurezza_cantiere(audio_bytes, image_file, verbale_attuale):
    """
    Integra un verbale esistente con nuove note vocali.
    image_file: l'oggetto file (o MockFile) con .name e .getvalue()
    verbale_attuale: stringa contenente il verbale già editato dall'utente
    """
    client = OpenAI(api_key=st.secrets["openai_key"])
    
    # 1. Trascrizione della nuova integrazione
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.wav"
    transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
    
    # 2. Prompt per l'integrazione
    system_prompt = f"""
    Sei un Ispettore Tecnico della Sicurezza (D.Lgs 81/08).
    
    Hai un verbale attuale:
    "{verbale_attuale}"
    
    L'ispettore ha aggiunto nuove note vocali:
    "{transcript.text}"
    
    Tuo compito:
    1. Integra le nuove informazioni nel verbale tecnico formale esistente, mantenendo lo stile professionale.
    2. Aggiorna la lista dei punti critici includendo quelli nuovi e mantenendo quelli vecchi validi.
    3. Se le nuove note rendono obsoleti alcuni punti vecchi, correggili o rimuovili.
    4. Il "riassunto_generale" deve rimanere di 10 parole massimo.
    5. Il JSON deve contenere TUTTI i punti critici aggiornati e completi.
    
    Restituisci JSON con la stessa struttura precedente: 
    {{
        "verbale_tecnico": "Il verbale aggiornato e completo",
        "riassunto_generale": "...",
        "punti_critici": [
            {{
                "elemento": "...",
                "origine": "...",
                "commento": "...",
                "rischio": "...",
                "urgenza": "...",
                "coordinate": {{"x": 50, "y": 50}},
                "oggetto": "..."
            }}
        ]
    }}
    """
    
    # 3. Codifica immagine
    b64 = base64.b64encode(image_file.getvalue()).decode('utf-8')
    
    payload = [
        {"type": "text", "text": "Aggiorna il verbale in base alle note integrative."},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
    ]
    
    # 4. Chiamata API
    resp = client.chat.completions.create(
        model="gpt-4o", 
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": payload}], 
        response_format={"type": "json_object"}
    )
    
    dati = json.loads(resp.choices[0].message.content)
    
    # Ritorno del report aggiornato
    report_completo = {
        "riassunto_generale": dati.get("riassunto_generale", ""),
        "analisi_per_immagine": [{
            "nome_file": image_file.name, 
            "punti_critici": dati.get("punti_critici", [])
        }]
    }
    
    return report_completo, dati.get("verbale_tecnico", verbale_attuale)



utente_connesso = login()

# --- 3. CONTENUTO PRINCIPALE ---
if utente_connesso:
    if st.sidebar.button("Logout"):
        st.session_state.user_data = None
        st.rerun()

    status_placeholder = st.empty()

    st.sidebar.header("⚙️ Impostazioni")
    mostra_marker = st.sidebar.toggle("Mostra Marker sulla foto", value=True)

    # Inizializzazione variabili di stato
    if "storico_report" not in st.session_state: st.session_state.storico_report = []
    if "edits" not in st.session_state: st.session_state.edits = {}

    tab1, tab2 = st.tabs(["🚀 Caricamento e Registrazioni", "📋 Report"])

    # --- TAB 1: ACQUISIZIONE E ANALISI ---
    with tab1:
        st.subheader("📸 Carica e descrivi")
        file = st.file_uploader("Carica una foto", type=["jpg", "png", "jpeg"], key="uploader_live")
        
            
        audio = mic_recorder(
            start_prompt="⏺️ AVVIA REGISTRAZIONE", 
            stop_prompt="⏹️ ANALIZZA", 
            key='recorder_live'
        )

        # Visualizzazione immagine di guida
        if file is not None:
            st.image(file, caption="Immagine di riferimento per il sopralluogo", use_container_width=True)

        if audio and file:
            audio_hash = hash(str(audio['bytes']))
            
            # Evita esecuzioni multiple
            if st.session_state.get("last_audio_hash") != audio_hash:
                with st.spinner("Analisi in corso..."):
                    # Esecuzione Analisi
                    report, testo = analizza_sicurezza_cantiere(audio['bytes'], file)
                    
                    # Aggiornamento storico
                    if "storico_report" not in st.session_state: 
                        st.session_state.storico_report = []
                    
                    st.session_state.storico_report.append({
                        "nome_file": file.name, 
                        "report": report, 
                        "trascrizione": testo, 
                        "bytes": file.getvalue(), 
                        "version": 1
                    })
                    
                    st.session_state.last_audio_hash = audio_hash
                    st.success("✅ Nuova analisi aggiunta!")
                    st.rerun()

    # --- TAB 2: VISUALIZZAZIONE E GESTIONE (REWORK/INTEGRAZIONE) ---
    with tab2:
        if st.session_state.storico_report:
            for idx, data in enumerate(st.session_state.storico_report):
                nome_file = data["nome_file"]
                report = data["report"]
                ver = data.get("version", 1) 
                punti_totali = [p for img_data in report.get("analisi_per_immagine", []) for p in img_data['punti_critici']]
                titolo = report.get("riassunto_generale", f"Analisi {nome_file}")
                
                with st.expander(f"🔍 {titolo.upper()} ({nome_file})", expanded=True):
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        
                        # 2. IMMAGINE INTERATTIVA
                        # 1. Prepariamo l'immagine
                        img_display = disegna_punti_critici(data["bytes"], punti_totali, abilita_marker=mostra_marker)
                        
                        # 2. Rendiamo l'immagine cliccabile (al posto di st.image)
                        # Nota: dobbiamo passare l'immagine PIL (img_display)
                        click_data = streamlit_image_coordinates(
                            img_display, 
                            key=f"img_click_{idx}"
                        )

                        # 3. Logica per aggiungere il punto se l'utente clicca
                        if click_data is not None:
                            if st.button("📍 Fissa punto qui", key=f"fix_{idx}_{ver}"):
                                w, h = img_display.size
                                x_norm = (click_data['x'] / w) * 1000
                                y_norm = (click_data['y'] / h) * 1000
                                
                                # CERCHIAMO IL PRIMO PUNTO CON COORDINATE NONE
                                punto_vuoto_trovato = False
                                for p in report['analisi_per_immagine'][0]['punti_critici']:
                                    if p.get('coordinate', {}).get('x') is None:
                                        p['coordinate'] = {'x': x_norm, 'y': y_norm}
                                        punto_vuoto_trovato = True
                                        break
                                
                                # SE NON CI SONO PUNTI VUOTI, NE AGGIUNGIAMO UNO NUOVO
                                if not punto_vuoto_trovato:
                                    report['analisi_per_immagine'][0]['punti_critici'].append({
                                        "elemento": "Punto Manuale",
                                        "commento": "Aggiunto manualmente",
                                        "coordinate": {"x": x_norm, "y": y_norm},
                                        "oggetto": "Nota manuale"
                                    })
                                
                                st.session_state.storico_report[idx]['report'] = report
                                st.rerun()

                        
                        # 1. PULSANTI DI SISTEMA (Spostati in alto per evitare conflitti)
                        c1, c2, c3, c4 = st.columns(4)

                        if c1.button("🗑️ Elimina", key=f"del_{idx}"):
                            del st.session_state.storico_report[idx]
                            st.rerun()

                        if c2.button("🔄 Rifai", key=f"redo_{idx}"):
                            st.session_state.active_recorder = {"idx": idx, "mode": "rework"}
                            st.rerun()

                        if c3.button("➕ Integra", key=f"int_{idx}"):
                            st.session_state.active_recorder = {"idx": idx, "mode": "integration"}
                            st.rerun()
                        
                        # NUOVO PULSANTE: Svuota solo le coordinate (i testi restano!)

                        if c4.button("🧹 Svuota Marker", key=f"clear_markers_{idx}"):
                            for img_data in report.get("analisi_per_immagine", []):
                                for p in img_data['punti_critici']:
                                    p['coordinate'] = {'x': None, 'y': None} # Rende i cerchi invisibili
                            st.session_state.storico_report[idx]['report'] = report
                            st.rerun()

                        # --- REGISTRATORE CONTESTUALE ---
                        if st.session_state.get("active_recorder") and st.session_state.active_recorder["idx"] == idx:
                            st.info(f"🎤 Registra per {st.session_state.active_recorder['mode'].upper()}...")
                            audio_attivo = mic_recorder(start_prompt="⏺️ AVVIA", stop_prompt="⏹️ ANALIZZA", key=f"rec_{idx}")
                            
                            if audio_attivo:
                                with st.spinner("Analisi in corso..."):
                                    class MockFile:
                                        def __init__(self, name, data): self.name = name; self._data = data
                                        def getvalue(self): return self._data
                                    
                                    file_mock = MockFile(data["nome_file"], data["bytes"])
                                    mode = st.session_state.active_recorder["mode"]
                                    
                                    if mode == "rework":
                                        report, testo = analizza_sicurezza_cantiere(audio_attivo['bytes'], file_mock)
                                    else:
                                        verbale_attuale = st.session_state.edits.get(f"edit_testo_{idx}", data["trascrizione"])
                                        report, testo = integra_sicurezza_cantiere(audio_attivo['bytes'], file_mock, verbale_attuale)
                                    
                                    new_v = st.session_state.get("version_counter", 0) + 1
                                    st.session_state.version_counter = new_v
                                    st.session_state.storico_report[idx].update({"report": report, "trascrizione": testo, "version": new_v})
                                    
                                    # Reset Edits
                                    for k in [k for k in st.session_state.edits.keys() if f"_{idx}" in k]: del st.session_state.edits[k]
                                    st.session_state.edits[f"edit_testo_{idx}"] = testo
                                    
                                    del st.session_state.active_recorder
                                    st.rerun()
                    
                    with col2:
                        st.markdown("#### Analisi")
                        
                        key_testo = f"edit_testo_{idx}"
                        
                        # Se è la prima volta, inizializza con la trascrizione dell'AI
                        if key_testo not in st.session_state.edits:
                            st.session_state.edits[key_testo] = data["trascrizione"]
                        
                        # Aggiornamento forzato se il verbale dell'AI è cambiato dopo un rework
                        if st.session_state.edits[key_testo] != data["trascrizione"]:
                             st.session_state.edits[key_testo] = data["trascrizione"]
                        
                        # LA CHIAVE DINAMICA _v{ver} FORZA IL RENDER DEL NUOVO TESTO
                        st.session_state.edits[key_testo] = st.text_area(
                            "Modifica il verbale:", 
                            value=st.session_state.edits[key_testo], 
                            height=230,
                            key=f"widget_{key_testo}_v{ver}" 
                        )
                        
                        st.markdown("#### ⚠️ Punti critici rilevati")
                        for i, p in enumerate(punti_totali, start=1):
                            # Creiamo una riga per il punto critico
                            c_punto1, c_punto2 = st.columns([0.9, 0.1])
                            
                            with c_punto1:
                                key_punto = f"edit_punto_{idx}_{i}"
                                if key_punto not in st.session_state.edits:
                                    st.session_state.edits[key_punto] = p['commento']
                                
                                st.session_state.edits[key_punto] = st.text_area(
                                    f"{i}. {p['elemento']} ({p['oggetto']})",
                                    value=st.session_state.edits[key_punto],
                                    height=130,
                                    key=f"widget_{key_punto}_v{ver}"
                                )
                            
                            with c_punto2:
                                # Bottone per eliminare il singolo punto
                                if st.button("❌", key=f"del_punto_{idx}_{i}"):
                                    # Rimuoviamo il punto dalla struttura dati del report
                                    # Dobbiamo cercarlo nel report originale
                                    for img_data in report.get("analisi_per_immagine", []):
                                        if p in img_data['punti_critici']:
                                            img_data['punti_critici'].remove(p)
                                            # Aggiorniamo lo storico con il report modificato
                                            st.session_state.storico_report[idx]['report'] = report
                                            st.rerun()
        else:
            st.info("Esegui un'analisi per vedere i risultati qui.")


