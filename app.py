
import base64
import time
import streamlit as st
from PIL import Image
from streamlit_mic_recorder import mic_recorder
from streamlit_image_coordinates import streamlit_image_coordinates


# LIBRARIES 
from Lib_Outlook import invia_report_via_email_graph
from Lib_Image import get_img_bytes_optimized, disegna_punti_critici
from Lib_AI import elabora_anagrafica_ai, elabora_campo_tecnico_ai, analizza_sicurezza_cantiere
from Lib_Utility import login, salva_stato_completo, recupera_stato_completo, resetta_tutto_il_sistema
from Lib_Word import genera_report_finale

    

def set_global_styles():
    st.markdown(
        """
        <style>
        /* CSS per immagini standard e dentro expander */
        [data-testid="stExpander"] img,
        [data-testid="stImage"] img {
            max-width: 100% !important;
            height: auto !important;
            display: block;
            margin-left: auto;
            margin-right: auto;
        }
        
        /* Forza il contenitore dell'immagine a rispettare la larghezza del padre */
        [data-testid="stExpander"] [data-testid="stImage"],
        [data-testid="stImage"] {
            width: 100% !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def set_bg_color(color, status_text=None):
    # CSS per cambiare lo sfondo e creare il banner fisso
    banner_html = ""
    if status_text:
        banner_html = f"""
        <div style="position: fixed; top: 0; left: 0; width: 100%; background-color: #333; 
                    color: white; text-align: center; padding: 10px; z-index: 9999; font-weight: bold;">
            {status_text}
        </div>
        """
    
    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: {color} !important; }}
        </style>
        {banner_html}
        """,
        unsafe_allow_html=True
    )




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
                    
                    # Salviamo i byte pronti per essere inseriti in Word
                    st.session_state.allegati_ottimizzati.append({
                        "name": f.name,
                        "bytes": bytes_ottimizzati,
                        "type": f.type
                    })
                    st.success(f"✅ '{f.name}' pronto a essere inserito nel report finale.")
                else:
                    st.warning(f"⚠️ '{f.name}' non è formato di file inseribile nel report Word. Aggiungerò il nome all'elenco allegati ma il file dovrà essere allegato manualmente.")


def inizializza_stato():
    # 1. Inizializza anagrafica se non esiste
    if "anagrafica" not in st.session_state:
        st.session_state.anagrafica = {
            "mandataria": "", "mandante": "", "committente": "", 
            "indirizzo": "", "città": "", "provincia": "", 
            "commessa": "", "oggetto": "", "attività": "", 
            "coordinamento": "", "personale": "", "verbali": ""
        }
    
    # 2. Inizializza le altre chiavi di supporto
    if "anagrafica_version" not in st.session_state:
        st.session_state.anagrafica_version = 0

    # 1. Aggiungi questo all'inizializzazione se manca
    if "widget_version" not in st.session_state:
        st.session_state.widget_version = {}




# APP PRINCIPALE
inizializza_stato()


# --- ORA CHIAMA IL LOGIN ---
utente_connesso = login()

set_global_styles()

# log_sidebar_debug_completo()

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
                    # Qui forziamo l'aggiornamento di session_state dai widget
                    # (Streamlit lo fa automaticamente se usi le key, ma è un buon momento per forzare)
                    salva_stato_completo()
                    st.toast("Salvato correttamente!", icon="✅")
    st.divider()

# Chiamata alla funzione subito dopo il Login
if utente_connesso:
    barra_salvataggio_superiore()

    status_placeholder = st.empty()


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
                    
                    # Aggiornamento storico
                    if "storico_report" not in st.session_state: 
                        st.session_state.storico_report = []
                    
                    st.session_state.storico_report.append({
                        "nome_file": file.name, 
                        "report": report, 
                        "trascrizione": testo, 
                        "bytes": img_bytes_ottimizzati, # Salva i bytes leggeri!
                        "version": 1
                    })
                    
                    st.session_state.last_audio_hash = audio_hash
                    salva_stato_completo()
                    
                    # 4. Feedback finale
                    st.session_state.app_state = "done"
                    set_bg_color("#b3ff99")
                    time.sleep(2)
                    #st.rerun()

    # --- TAB 2: VISUALIZZAZIONE E GESTIONE ---
    with tab2:
        if st.session_state.storico_report:
            # Creiamo una copia della lista per evitare problemi di iterazione durante la modifica
            report_list = st.session_state.storico_report
            
            for idx in range(len(report_list)):
                data = report_list[idx]
                
                # CHIAVE SEMPLICE E UNIVOVA BASATA SULL'INDICE ATTUALE
                # Aggiungiamo un timestamp casuale se vuoi forzare il reset totale, 
                # ma per ora basiamoci sull'indice.
                expander_key = f"expander_box_{idx}"
                
                nome_file = data["nome_file"]
                report = data["report"]
                punti_totali = [p for img_data in report.get("analisi_per_immagine", []) for p in img_data['punti_critici']]
                titolo = report.get("riassunto_generale", f"Analisi {nome_file}")
                
                with st.expander(f"🔍 {titolo.upper()} ({nome_file})", expanded=True, key=expander_key):
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        
                        # 2. IMMAGINE INTERATTIVA
                        img_da_disegnare = data.get("bytes")
                        if img_da_disegnare:
                            # Caso standard: hai i bytes, disegna tutto
                            img_display = disegna_punti_critici(img_da_disegnare, punti_totali, abilita_marker=mostra_marker)
                        else:
                            # Caso fallback: non hai i bytes (sono stati filtrati), 
                            # ma forse hai il file caricato nel widget uploader o altro riferimento?
                            # Se non c'è, carica un'immagine neutra per evitare il crash
                            
                            img_display = Image.new('RGB', (300, 300), color=(200, 200, 200))
                            st.warning("Immagine originale non caricata in memoria.")


                        # 2. Rendiamo l'immagine cliccabile (al posto di st.image)
                        # Nota: dobbiamo passare l'immagine PIL (img_display)
                        click_data = streamlit_image_coordinates(
                            img_display, 
                            key=f"img_click_{idx}",
                            width=350
                        )

                        # 3. Logica per aggiungere il punto se l'utente clicca
                        if click_data is not None:
                            if st.button("📍 Fissa punto qui", key=f"fix_{idx}"):
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
                                #salva_stato_completo()
                                #st.rerun()

                        
                        # 1. PULSANTI DI SISTEMA (Spostati in alto per evitare conflitti)
                        c1, c2, c3, c4 = st.columns(4)

                        with c1:
                            if st.button("🗑️ Elimina", key=f"del_{idx}"):
                                # 1. Rimuovi l'elemento corretto dalla lista
                                st.session_state.storico_report.pop(idx)
                                
                                # 2. Pulisci SOLO le chiavi associate all'indice rimosso
                                # (Questo è opzionale ma pulito)
                                keys_to_delete = [k for k in st.session_state.keys() if f"_{idx}" in k]
                                for k in keys_to_delete:
                                    del st.session_state[k]
                                    
                                # 3. Salva e Ricarica
                                salva_stato_completo()
                                st.rerun()
                            
                        # NUOVO PULSANTE: Svuota solo le coordinate (i testi restano!)

                        if c4.button("🧹 Svuota Marker", key=f"clear_markers_{idx}"):
                            for img_data in report.get("analisi_per_immagine", []):
                                for p in img_data['punti_critici']:
                                    p['coordinate'] = {'x': None, 'y': None} # Rende i cerchi invisibili
                            st.session_state.storico_report[idx]['report'] = report
                            #salva_stato_completo()
                            st.rerun()


                    with col2:
                        st.markdown("#### Analisi")
                        
                        # 1. Inizializzazione dati (solo se mancano)
                        key_testo = f"edit_testo_{idx}"
                        if key_testo not in st.session_state.edits:
                            st.session_state.edits[key_testo] = data["trascrizione"]

                        # 2. Sincronizzazione: Se l'AI ha generato un nuovo testo (es. dopo un rework), 
                        # aggiorniamo il valore SOLO SE l'utente non ha ancora iniziato a modificare manualmente
                        # oppure se forziamo un reset.
                        # Consiglio: non usare st.session_state.edits[key_testo] != data["trascrizione"] 
                        # qui dentro se vuoi che l'utente possa editare senza che l'AI sovrascriva.
                        # Fai l'aggiornamento solo quando chiami la funzione "rework" (nel Tab 2).

                        # 3. WIDGET CON CHIAVE STATICA (La chiave NON DEVE dipendere da ver)
                        valore_attuale = st.session_state.edits[key_testo]

                        st.session_state.edits[key_testo] = st.text_area(
                            "Modifica il verbale:", 
                            value=valore_attuale, 
                            height=230,
                            key=key_testo 
                            #on_change=salva_stato_completo 
                        )
                        
                        st.markdown("#### ⚠️ Punti critici rilevati")
                        
                        # Usiamo un contatore sicuro
                        for idx_p, p in enumerate(punti_totali):
                            # Creiamo un ID unico che non dipende dal numero di elementi nella lista
                            # Se il punto ha un 'id' nel dizionario, usa quello. Altrimenti usa le coordinate.
                            id_univoco = p.get('id', f"x{p.get('coordinate',{}).get('x')}_y{p.get('coordinate',{}).get('y')}_{idx_p}")
                            
                            c_punto1, c_punto2 = st.columns([0.9, 0.1])
                            
                            with c_punto1:
                                key_punto = f"edit_punto_{idx}_{id_univoco}"
                                if key_punto not in st.session_state.edits:
                                    st.session_state.edits[key_punto] = p.get('commento', '')
                                
                                st.session_state.edits[key_punto] = st.text_area(
                                    f"{idx_p + 1}. {p.get('elemento', 'Punto')} ({p.get('oggetto', 'Nota')})",
                                    value=st.session_state.edits[key_punto],
                                    height=130,
                                    key=key_punto
                                    #on_change=salva_stato_completo
                                )
                            
                            with c_punto2:
                                # Il bottone usa la stessa chiave univoca, non i
                                if st.button("❌", key=f"del_punto_{idx}_{id_univoco}"):
                                    # Rimuovi il punto e forza il rerun
                                    for img_data in report.get("analisi_per_immagine", []):
                                        if p in img_data['punti_critici']:
                                            img_data['punti_critici'].remove(p)
                                            st.session_state.storico_report[idx]['report'] = report
                                            salva_stato_completo()
                                            st.rerun()

        else:
            st.info("Esegui un'analisi per vedere i risultati qui.")

    
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