
import base64
import time
import uuid 
import os
import streamlit as st
from PIL import Image
from streamlit_mic_recorder import mic_recorder
from streamlit_image_coordinates import streamlit_image_coordinates


# LIBRARIES 
from Lib_Outlook import invia_report_via_email_graph
from Lib_Image import get_img_bytes_optimized, disegna_punti_critici
from Lib_AI import elabora_anagrafica_ai, elabora_campo_tecnico_ai, analizza_sicurezza_cantiere
from Lib_Utility import login, resetta_tutto_il_sistema, inizializza_stato, salva_stato_completo
from Lib_Word import genera_report_finale
from Lib_Style import set_global_styles, set_bg_color



def recupera_stato_completo():
    st.session_state.debug_log = "Avvio recupero dati..."
    import json
    from streamlit_local_storage import LocalStorage
    try:
        # 1. Usiamo l'istanza globale (NIENTE NUOVE ISTANZE per non crashare)
        master = st.session_state.ls_master
        
        # 2. Leggiamo direttamente la chiave e i dati
        chiave_reale = master.getItem("chiave_valida")
        dati = master.getItem("imprendo_dati")
        
        if not dati:
            st.session_state.debug_log = "RECUPERO FALLITO: Nessun dato trovato nel LocalStorage."
            return False
            
        # 3. Ripristino Dati Base
        st.session_state.anagrafica = dati.get("anagrafica", {})
        st.session_state.edits = dati.get("edits", {})
        
        # 4. FORZATURA REFRESH WIDGET (FONDAMENTALE)
        # Cambiamo la versione per distruggere i vecchi widget e farli rinascere con i dati nuovi
        if "anagrafica_version" in st.session_state:
            st.session_state.anagrafica_version += 1
        else:
            st.session_state.anagrafica_version = 1
            
        st.session_state.widget_version = {k: 0 for k in st.session_state.anagrafica.keys()}
        
        # 5. Ripristino Storico con controllo path
        storico_recuperato = []
        immagini_perse = 0
        
        for item in dati.get("storico_report", []):
            item_copy = item.copy()
            
            # Controllo di sicurezza su disco
            path = item_copy.get("img_path")
            if path and not os.path.exists(path):
                # Se il file temporaneo è stato cancellato dal server
                item_copy["img_path"] = None 
                immagini_perse += 1
            
            storico_recuperato.append(item_copy)
            
        st.session_state.storico_report = storico_recuperato
        
        # 6. LOG DI CONFERMA TOTALE
        st.session_state.debug_log = (
            f"RECUPERO OK: {time.strftime('%H:%M:%S')}\n"
            f"CHIAVE LETTA: {chiave_reale}\n\n"
            f"--- ANAGRAFICA RIPRISTINATA ---\n"
            f"{json.dumps(st.session_state.anagrafica, indent=2)}\n\n"
            f"--- STORICO REPORT ---\n"
            f"Report caricati: {len(st.session_state.storico_report)}\n"
            f"Immagini assenti dal disco: {immagini_perse}\n\n"
            f"--- EDITS ---\n"
            f"Voci ripristinate: {len(st.session_state.edits)}\n"
        )
        
        return True
        
    except Exception as e:
        st.session_state.debug_log = f"!!! ERRORE CRITICO RECUPERO !!!\n{str(e)}"
        st.error(f"Errore durante il caricamento: {e}")
        return False



@st.fragment
def form_anagrafiche():

    with st.expander("👤 Anagrafiche", expanded=True):
            with st.container():

                # 1. Pulsante di registrazione unico
                audio_data = mic_recorder(key="rec_anagrafica_totale", start_prompt="🎤", stop_prompt="⏹️")
                
                if audio_data:
                    audio_hash = hash(str(audio_data['bytes']))
                    if st.session_state.get("last_anagrafica_hash") != audio_hash:
                        with st.spinner("L'AI sta estraendo i dati..."):
                            set_bg_color("#D0AD00")

                            dati = elabora_anagrafica_ai(audio_data['bytes'])
                            
                            # Aggiornamento dati
                            st.session_state.anagrafica["mandataria"]   = str(dati.get("mandataria", "")).replace(", ", "\n")
                            st.session_state.anagrafica["mandante"]     = str(dati.get("mandante", "")).replace(", ", "\n")
                            st.session_state.anagrafica.update({
                                "committente": dati.get("committente", ""),
                                "indirizzo": dati.get("indirizzo", ""),
                                "città": dati.get("città", ""),
                                "provincia": dati.get("provincia", "")
                            })

                            st.session_state.anagrafica_version += 1
                            
                            st.session_state.last_anagrafica_hash = audio_hash
                            set_bg_color("#b3ff99")

                
                # Lista definita fuori dal loop
                campi = [
                    ("mandataria", "Mandataria/e", "area"),
                    ("mandante", "Mandante/i", "area"),
                    ("committente", "Ragione Sociale Committente", "input"),
                    ("indirizzo", "Indirizzo", "input"),
                    ("città", "Città", "input"),
                    ("provincia", "Provincia", "input")
                ]

                salt = st.session_state.get("anagrafica_version", 0)
                
                for campo_id, label, tipo in campi:
                    
                        key_widget = f"widget_{campo_id}_{salt}"
                        
                        # ASSEGNAZIONE DIRETTA NEL WIDGET
                        if tipo == "area":
                            st.session_state.anagrafica[campo_id] = st.text_area(
                                label, 
                                value=st.session_state.anagrafica.get(campo_id, ""),
                                key=key_widget
                            )
                        else:
                            st.session_state.anagrafica[campo_id] = st.text_input(
                                label, 
                                value=st.session_state.anagrafica.get(campo_id, ""),
                                key=key_widget
                            )


@st.fragment
def widget_campo_tecnico(campo_id, label, key_rec, key_hash):
    # Inizializza la versione specifica per questo campo se non esiste
    if campo_id not in st.session_state.widget_version:
        st.session_state.widget_version[campo_id] = 0

    # 1. Registratore
    audio_data = mic_recorder(
        key=f"recorder_{campo_id}", 
        start_prompt=f"🎤 {label}", 
        stop_prompt="🛑 FERMA REGISTRAZIONE E AVVIA ANALISI"
    )
    
    # 2. Elaborazione AI
    if audio_data and isinstance(audio_data, dict) and 'bytes' in audio_data:
        current_hash = hash(str(audio_data['bytes']))
        if st.session_state.get(key_hash) != current_hash:
            with st.spinner("Elaborazione AI..."):
                risultato = elabora_campo_tecnico_ai(audio_data['bytes'], campo_id)
                st.session_state.anagrafica[campo_id] = risultato
                st.session_state[key_hash] = current_hash
                
                # --- TRUCCO: INCREMENTA LA VERSIONE ---
                st.session_state.widget_version[campo_id] += 1
                # Non serve rerun, il frammento si aggiorna da solo alla fine del blocco

    # 3. Widget con chiave "versionata"
    # Quando la versione cambia, Streamlit crea un NUOVO widget che legge il nuovo valore
    ver = st.session_state.widget_version[campo_id]
    
    st.text_area(
        label, 
        value=st.session_state.anagrafica.get(campo_id, ""),
        key=f"field_{campo_id}_{ver}", # La key cambia ogni volta che l'AI finisce
        on_change=lambda: st.session_state.anagrafica.update({campo_id: st.session_state[f"field_{campo_id}_{ver}"]})
    )


@st.fragment
def form_allegati():
    with st.expander("📎 Allegati", expanded=True):
        uploaded_files = st.file_uploader(
            "Carica allegati", 
            accept_multiple_files=True, 
            key="file_uploader_allegati"
        )
        
        # Inizializziamo una lista per gli allegati ottimizzati
        st.session_state.allegati_ottimizzati = []
        
        if uploaded_files:
            for f in uploaded_files:
                # Verifica se è un'immagine
                if f.type.startswith('image'):
                    # APPLICHIAMO LA TUA FUNZIONE
                    img = Image.open(f).convert("RGB")
                    bytes_ottimizzati = get_img_bytes_optimized(img, max_width=1200)
                    
                    # SALVATAGGIO SU DISCO (alleggerisce la RAM)
                    temp_id = str(uuid.uuid4())
                    temp_path = f"/tmp/allegato_{temp_id}.jpg"
                    with open(temp_path, "wb") as f_out:
                        f_out.write(bytes_ottimizzati)
                    
                    # Salviamo il riferimento al file
                    st.session_state.allegati_ottimizzati.append({
                        "name": f.name,
                        "path": temp_path, 
                        "type": f.type
                    })
                    st.success(f"✅ '{f.name}' pronto a essere inserito nel report finale.")
                else:
                    st.warning(f"⚠️ '{f.name}' non è formato di file inseribile nel report Word. Aggiungerò il nome all'elenco allegati ma il file dovrà essere allegato manualmente.")


@st.fragment
def widget_punto_critico(idx, idx_p, p, report):
    """Frammento per gestire il singolo punto critico."""
    id_univoco = p.get('id', f"x{p.get('coordinate',{}).get('x')}_y{p.get('coordinate',{}).get('y')}_{idx_p}")
    key_punto = f"edit_punto_{idx}_{id_univoco}"
    
    # Inizializzazione nello stato
    if key_punto not in st.session_state.edits:
        st.session_state.edits[key_punto] = p.get('commento', '')
    
    c1, c2 = st.columns([0.9, 0.1])
    
    with c1:
        # Quando l'utente scrive, si aggiorna solo lo stato
        st.session_state.edits[key_punto] = st.text_area(
            f"{idx_p + 1}. {p.get('elemento', 'Punto')} ({p.get('oggetto', 'Nota')})",
            value=st.session_state.edits[key_punto],
            height=130,
            key=f"area_{key_punto}"
        )
    
    with c2:
        if st.button("❌", key=f"del_punto_{idx}_{id_univoco}"):
            # Rimozione dal report
            for img_data in report.get("analisi_per_immagine", []):
                if p in img_data['punti_critici']:
                    img_data['punti_critici'].remove(p)
                    st.session_state.storico_report[idx]['report'] = report
                    st.rerun() # Il rerun qui ricarica SOLO questo frammento!


@st.fragment
def widget_analisi_immagine(idx, data):
    """Frammento per gestire la modifica del verbale di analisi."""
    key_testo = f"edit_testo_{idx}"
    
    # Inizializzazione se non presente
    if key_testo not in st.session_state.edits:
        st.session_state.edits[key_testo] = data["trascrizione"]

    # Widget di testo
    valore_attuale = st.session_state.edits[key_testo]
    st.session_state.edits[key_testo] = st.text_area(
        "Modifica il verbale:", 
        value=valore_attuale, 
        height=230,
        key=f"text_area_{key_testo}"
    )




@st.fragment
def render_expander_report(id_univoco, data, mostra_marker):
    # Recuperiamo l'indice reale basandoci sull'ID univoco
    idx = next((i for i, r in enumerate(st.session_state.storico_report) if r["id"] == id_univoco), None)
    
    if idx is None: 
        return 

    nome_file       = data["nome_file"]
    report          = data["report"]
    punti_totali    = [p for img_data in report.get("analisi_per_immagine", []) for p in img_data['punti_critici']]
    titolo          = report.get("riassunto_generale", f"Analisi {nome_file}")
    
    with st.expander(f"🔍 {titolo.upper()} ({nome_file})", expanded=True, key=f"expander_{id_univoco}"):
        col1, col2 = st.columns([1, 1])
        with col1:
            img_path = data.get("img_path")
            
            # --- MODIFICA QUI ---
            if img_path and os.path.exists(img_path):
                # Leggiamo i bytes dal file, non apriamo subito con Image
                with open(img_path, "rb") as f:
                    img_bytes = f.read()
                
                # Ora passiamo i bytes alla funzione, come facevi prima
                img_display = disegna_punti_critici(img_bytes, punti_totali, abilita_marker=mostra_marker)
            else:
                img_display = Image.new('RGB', (300, 300), color=(200, 200, 200))

            click_data = streamlit_image_coordinates(
                img_display, 
                key=f"img_click_{id_univoco}",
                width=350
            )

            # 3. Logica per aggiungere il punto se l'utente clicca
            if click_data is not None:
                if st.button("📍 Fissa punto qui", key=f"fix_{id_univoco}"):
                    w, h = img_display.size
                    x_norm = (click_data['x'] / w) * 1000
                    y_norm = (click_data['y'] / h) * 1000
                    
                    punto_vuoto_trovato = False
                    for p in report['analisi_per_immagine'][0]['punti_critici']:
                        if p.get('coordinate', {}).get('x') is None:
                            p['coordinate'] = {'x': x_norm, 'y': y_norm}
                            punto_vuoto_trovato = True
                            break
                    
                    if not punto_vuoto_trovato:
                        report['analisi_per_immagine'][0]['punti_critici'].append({
                            "elemento": "Punto Manuale",
                            "commento": "Aggiunto manualmente",
                            "coordinate": {"x": x_norm, "y": y_norm},
                            "oggetto": "Nota manuale"
                        })
                    
                    st.session_state.storico_report[idx]['report'] = report
                    st.rerun()

            # 1. PULSANTI DI SISTEMA
            c1, c2, c3, c4 = st.columns(4)

            with c1:
                # Definisci il bottone SENZA on_click
                if st.button("🗑️ Elimina", key=f"del_{id_univoco}"):
                    st.session_state.storico_report = [r for r in st.session_state.storico_report if r["id"] != id_univoco]
                    st.rerun()

            if c4.button("🧹 Svuota Marker", key=f"clear_markers_{id_univoco}"):
                for img_data in report.get("analisi_per_immagine", []):
                    for p in img_data['punti_critici']:
                        p['coordinate'] = {'x': None, 'y': None} 
                st.session_state.storico_report[idx]['report'] = report
                st.rerun()

        with col2:
            st.markdown("#### Analisi")
            widget_analisi_immagine(idx, data)
            
            st.markdown("#### ⚠️ Punti critici rilevati")
            for idx_p, p in enumerate(punti_totali):
                widget_punto_critico(idx, idx_p, p, report)


# APP PRINCIPALE
inizializza_stato()


# --- ORA CHIAMA IL LOGIN ---
utente_connesso = login()

set_global_styles()



if "app_state" not in st.session_state:
    status_msg = None
    color = "white"
    st.session_state.app_state = "ready"
if st.session_state.app_state == "ready":
    set_bg_color("#ffffff") 
if st.session_state.app_state == "working":
    color = "#D0AD00"
    status_msg = "⚠️ ANALISI IN CORSO - NON INTERAGIRE"
elif st.session_state.app_state == "done":
    color = "#89D889"
    status_msg = "✅ ANALISI COMPLETATA CON SUCCESSO"
else:
    status_msg = None
    color = "white"


set_bg_color(color, status_msg)

# --- 3. CONTENUTO PRINCIPALE ---
def barra_salvataggio_superiore():
    # Creiamo un contenitore fisso in alto
    with st.container():
        col1, col2 = st.columns([0.5, 0.5])
        
        with col1:
            # Pulsante visibile subito, stile primario
            if st.button("🗄️ CARICA ULTIMA BOZZA SALVATA", type="primary", use_container_width=True):
                with st.spinner("Caricamento in corso..."):
                    if recupera_stato_completo():
                        st.toast("Caricato correttamente!", icon="✅")
                        st.rerun() # FONDAMENTALE: ricarica l'app con le versioni widget a 0
                    else:
                        st.error("Nessuna bozza trovata.")
            
        with col2:
            # Pulsante visibile subito, stile primario
            if st.button("💾 SALVA BOZZA ATTUALE", type="primary", use_container_width=True):
                with st.spinner("Salvataggio in corso..."):
                    # TEST DI CONNETTIVITÀ
                    st.session_state.debug_log = "TEST: Il bottone è stato premuto!\n" + st.session_state.debug_log
                    
                    # Ora chiama la funzione
                    salva_stato_completo()
    st.divider()

# Chiamata alla funzione subito dopo il Login
if utente_connesso:
    barra_salvataggio_superiore()

    status_placeholder = st.empty()


    # Invece di usare st.text_area semplice, usiamo st.session_state.log_text
    # Inizializzalo se non esiste
    if "debug_log" not in st.session_state:
        st.session_state.debug_log = "Attendo azioni..."
    st.sidebar.subheader("DEBUG")
    st.sidebar.text_area("Log Persistente:", value=st.session_state.debug_log, height=300)


    st.sidebar.subheader("Reset App")
    if st.sidebar.button("🔄 Inizia da zero"):
        status_placeholder.warning("Reset totale in corso...")
        resetta_tutto_il_sistema()
        time.sleep(1)
        st.rerun()
    st.sidebar.divider()


    # IMPOSTAZIONI 
    st.sidebar.header("⚙️ Impostazioni")

    # Mostra marker
    mostra_marker = st.sidebar.toggle("Mostra Marker sulla foto", value=True)

    # Scelta font
    font_s = st.sidebar.selectbox("Font", ["Arial", "Calibri", "Times New Roman"], index=0)
    
    # Scelta dimensione
    size_s = st.sidebar.slider("Dimensione Font (pt)", min_value=7, max_value=16, value=9)
    
    # Salviamo nello stato
    st.session_state.settings = {
        "font": font_s,
        "size": size_s
    }

    # Inizializzazione variabili di stato
    if "storico_report" not in st.session_state: st.session_state.storico_report = []
    if "edits" not in st.session_state: st.session_state.edits = {}

    tab1, tab2, tab3 = st.tabs(["🚀 Caricamenti", "📋 Analisi Tecniche", "👤 Report"])

    # --- TAB 1: ACQUISIZIONE E ANALISI ---
    with tab1:
        st.subheader("📸 Carica e descrivi")
        file = st.file_uploader("Carica una foto", type=["jpg", "png", "jpeg"], key="uploader_live")
            
        audio = mic_recorder(
            start_prompt="🟢 AVVIA REGISTRAZIONE", 
            stop_prompt="🛑 FERMA REGISTRAZIONE E AVVIA ANALISI", 
            key='recorder_live'
        )

        # Visualizzazione immagine di guida
        if file is not None:
            st.image(file, caption="Immagine di riferimento per il sopralluogo", use_container_width=True)
            set_bg_color("#ffffff") 

        if audio and file:
            audio_hash = hash(str(audio['bytes']))
            
            # Evita esecuzioni multiple
            if st.session_state.get("last_audio_hash") != audio_hash:
                
                # 1. Ottimizzazione Immagine (nuova logica)
                img = Image.open(file).convert("RGB")
                img_bytes_ottimizzati = get_img_bytes_optimized(img)
                
                # Creiamo il wrapper per mantenere la compatibilità
                class MockFile:
                    def __init__(self, name, data): 
                        self.name = name
                        self._data = data
                    def getvalue(self): return self._data
                
                file_ottimizzato = MockFile(file.name, img_bytes_ottimizzati)

                # 2. Ripristino Spinner e Colori
                with st.spinner("Analisi in corso..."):
                    set_bg_color("#D0AD00")
                    st.session_state.app_state = "working"
                    
                    # 3. Esecuzione con il file ottimizzato
                    report, testo = analizza_sicurezza_cantiere(audio['bytes'], file_ottimizzato)
                    
                    id_univoco = str(uuid.uuid4())
                    temp_path = f"/tmp/{id_univoco}.jpg"

                    # Scriviamo l'immagine su disco
                    with open(temp_path, "wb") as f:
                        f.write(img_bytes_ottimizzati)

                    st.session_state.storico_report.append({
                        "id": id_univoco,
                        "nome_file": file.name, 
                        "report": report, 
                        "trascrizione": testo, 
                        "img_path": temp_path, # SALVI IL PERCORSO, NON I BYTES
                        "version": 1
                    })
                    
                    st.session_state.last_audio_hash = audio_hash
                    
                    # 4. Feedback finale
                    st.session_state.app_state = "done"
                    set_bg_color("#b3ff99")
                    time.sleep(1)


    # --- TAB 2: VISUALIZZAZIONE E GESTIONE ---
    with tab2:
        
        if st.session_state.storico_report:
            # Non serve più creare una copia della lista, itera direttamente
            for data in st.session_state.storico_report:
                # Passiamo l'ID unico invece dell'indice idx
                render_expander_report(data["id"], data, mostra_marker)
                
    with tab3:

        form_anagrafiche()
                        
        # --- COMMESSA ---
        with st.expander("📝 Commessa e Oggetto", expanded=True):
            widget_campo_tecnico("commessa", "Commessa", "rec_commessa", "last_commessa_hash")
            widget_campo_tecnico("oggetto", "Oggetto", "rec_oggetto", "last_oggetto_hash")
        
        # --- CANTIERE ---
        with st.expander("🛠️ Attività e Personale", expanded=True):
            widget_campo_tecnico("attività", "Attività di Cantiere", "rec_attivita", "last_attivita_hash")
            widget_campo_tecnico("coordinamento", "Coordinamento", "rec_coord", "last_coord_hash")
            widget_campo_tecnico("personale", "Personale Presente", "rec_personale", "last_personale_hash")
            widget_campo_tecnico("verbali", "Verbali di Prescrizione/Sospensione", "rec_verbali", "last_verb_hash")

        form_allegati()


        # --- ESPORTAZIONE ---
        st.divider()
        st.subheader("📥 Esportazione Report")
        
        if st.button("📄 Genera Report Finale"):
            with st.spinner("Generazione documento..."):
                files = st.session_state.get("file_uploader_allegati", [])
                files = [f for f in files if f is not None]
                
                doc_bytes = genera_report_finale(st.session_state.storico_report, files)
                st.session_state.doc_bytes = doc_bytes 
                st.success("Report generato!")

        if "doc_bytes" in st.session_state:
            col_down, col_mail = st.columns(2)
            
            with col_down:
                b64 = base64.b64encode(st.session_state.doc_bytes).decode()
                # Timestamp per evitare cache del browser
                ts = int(time.time())
                nome_file = f"Report_Sicurezza_{ts}.docx"
                href = f'<a href="data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{b64}" download="{nome_file}" style="text-decoration:none; color:white; background-color:#FF4B4B; padding: 10px 20px; border-radius:5px; display:inline-block; width:100%; text-align:center;">✅ SCARICA IL REPORT</a>'
                st.markdown(href, unsafe_allow_html=True)
            
            with col_mail:
                if st.button("📧 Invia a me stesso via Email"):
                    destinatario = st.session_state.user_data["email"]
                    with st.spinner("Invio in corso..."):
                        success, msg = invia_report_via_email_graph(st.session_state.doc_bytes, "Report_Sicurezza.docx", destinatario)
                        if success: st.success(msg)
                        else: st.error(f"Errore: {msg}")