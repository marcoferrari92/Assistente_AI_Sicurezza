
import time
import random
import json
import os
import datetime
import streamlit as st
from streamlit_local_storage import LocalStorage



# Metti questa istanza fuori, come variabile globale del modulo
_storage_cache = {}


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

    if "storico_report" not in st.session_state: 
        st.session_state.storico_report = []

    if "ls_master" not in st.session_state:
        st.session_state.ls_master = LocalStorage(key="MASTER_POINTER")



def get_ls(chiave):
    # Usiamo un dizionario locale al modulo, NON nel session_state 
    # per evitare che il componente venga ricreato durante i rerun
    global _storage_cache
    
    if chiave not in _storage_cache:
        # Questa riga viene eseguita SOLO UNA VOLTA per chiave
        _storage_cache[chiave] = LocalStorage(key=chiave)
        
    return _storage_cache[chiave]


def resetta_tutto_il_sistema():
    # 1. Pulisci solo i dati utente
    st.session_state.anagrafica = {}
    st.session_state.edits = {}
    st.session_state.storico_report = []
    
    # 2. Svuota solo i valori dei widget (senza toccare il dizionario widget_version)
    for k in list(st.session_state.keys()):
        if k.startswith("widget_") or k.startswith("field_"):
            st.session_state[k] = ""
            
    # 3. RIPRISTINO DI SICUREZZA (Soluzione al TypeError)
    # Assicurati che sia sempre un dizionario PRIMA di fare qualsiasi operazione
    if not isinstance(st.session_state.get("widget_version"), dict):
        st.session_state.widget_version = {}
    
    # Ora che siamo certi che sia un dizionario, azzeriamo i valori
    for k in st.session_state.widget_version:
        st.session_state.widget_version[k] = 0

    # 4. Pulizia file
    import glob, os
    for f in glob.glob("/tmp/*.jpg") + glob.glob("/tmp/allegato_*.jpg"):
        try: os.remove(f)
        except: pass
        
    st.rerun()


def recupera_stato_completo():
    st.session_state.debug_log = "Avvio recupero dati..."
    import json
    import datetime
    from streamlit_local_storage import LocalStorage
    try:
        # 1. Usiamo l'istanza globale
        master = st.session_state.ls_master
        
        # 2. Leggiamo i dati
        chiave_reale = master.getItem("chiave_valida")
        dati = master.getItem("imprendo_dati")
        
        if not dati:
            st.session_state.debug_log = "RECUPERO FALLITO: Nessun dato trovato nel LocalStorage."
            return False
            
        # 3. Ripristino Dati Base
        dati_anagrafica = dati.get("anagrafica", {})
        
        # DEBUG: Stampiamo cosa stiamo ricevendo realmente
        #st.write(f"DEBUG DATA RECUPERATA: {dati_anagrafica.get('data')}, Tipo: {type(dati_anagrafica.get('data'))}")
        
        if "data" in dati_anagrafica and isinstance(dati_anagrafica["data"], str):
            try:
                # Conversione forzata
                data_convertita = datetime.date.fromisoformat(dati_anagrafica["data"])
                dati_anagrafica["data"] = data_convertita
                st.session_state.debug_log += f"\nDEBUG: Data convertita in {data_convertita} (Tipo: {type(data_convertita)})"
            except Exception as e:
                st.session_state.debug_log += f"\nDEBUG: Errore conversione: {e}"
        
        # ASSEGNAZIONE ESPLICITA
        st.session_state.anagrafica = dati_anagrafica
        st.session_state.edits = dati.get("edits", {})
        
        # 4. FORZATURA REFRESH WIDGET
        if "anagrafica_version" in st.session_state:
            st.session_state.anagrafica_version += 1
        else:
            st.session_state.anagrafica_version = 1
            
        st.session_state.widget_version = {k: 0 for k in st.session_state.anagrafica.keys()}
        
        # 5. Ripristino Storico
        storico_recuperato = []
        immagini_perse = 0
        for item in dati.get("storico_report", []):
            item_copy = item.copy()
            path = item_copy.get("img_path")
            if path and not os.path.exists(path):
                item_copy["img_path"] = None 
                immagini_perse += 1
            storico_recuperato.append(item_copy)
        st.session_state.storico_report = storico_recuperato
        
        # 6. LOG DI CONFERMA TOTALE (CORRETTO PER EVITARE SERIALIZZAZIONE DATE)
        anagrafica_per_log = st.session_state.anagrafica.copy()
        if isinstance(anagrafica_per_log.get("data"), datetime.date):
            anagrafica_per_log["data"] = anagrafica_per_log["data"].isoformat()
            
        st.session_state.debug_log = (
            f"RECUPERO OK: {time.strftime('%H:%M:%S')}\n"
            f"CHIAVE LETTA: {chiave_reale}\n\n"
            f"--- ANAGRAFICA RIPRISTINATA ---\n"
            f"{json.dumps(anagrafica_per_log, indent=2)}\n\n"
            f"--- STORICO REPORT ---\n"
            f"Report caricati: {len(st.session_state.storico_report)}\n"
            f"Immagini assenti dal disco: {immagini_perse}\n\n"
            f"--- EDITS ---\n"
            f"Voci ripristinate: {len(st.session_state.edits)}\n"
        )
        st.rerun()
        return True
        
    except Exception as e:
        st.session_state.debug_log = f"!!! ERRORE CRITICO RECUPERO !!!\n{str(e)}"
        st.error(f"Errore durante il caricamento: {e}")
        return False


def salva_stato_completo():
    # 1. RESET TOTALE DEL LOG (Nessuna concatenazione)
    st.session_state.debug_log = "Avvio salvataggio..."
    
    # 2. CONTROLLO DI COERENZA
    if not st.session_state.storico_report:
        st.session_state.debug_log = "Salvataggio non eseguito: storico vuoto."
        return

    try:
        # 3. PULL DATI (Sincronizzazione Widget -> State)
        salt = st.session_state.get("anagrafica_version", 0)
        for campo in st.session_state.anagrafica.keys():
            key_widget = f"widget_{campo}_{salt}"
            if key_widget in st.session_state:
                st.session_state.anagrafica[campo] = st.session_state[key_widget]
        
        # 4. PREPARAZIONE STRUTTURA DATI
        def pulisci(obj):
            if hasattr(obj, 'strftime'):
                return obj.strftime("%Y-%m-%d")
            elif isinstance(obj, dict):
                return {k: pulisci(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [pulisci(i) for i in obj]
            return obj

        data = {
            "anagrafica": pulisci(st.session_state.anagrafica),
            "storico_report": pulisci(st.session_state.storico_report),
            "edits": pulisci(st.session_state.edits)
        }
        
        # 5. SCRITTURA SU LOCALSTORAGE MASTER
        ls = st.session_state.ls_master
        chiave = ls.getItem("chiave_valida")
        if not chiave:
            chiave = f"storage_{random.randint(10000, 99999)}"
            ls.setItem("chiave_valida", chiave)
            
        ls.setItem("imprendo_dati", data)
        
        # 6. LOG DETTAGLIATO E COMPLETO (Dump chirurgico)
        # Espandiamo le anteprime per vedere i contenuti reali
        report_preview = []
        for r in data['storico_report']:
            report_preview.append({
                "id": r.get("id"),
                "trascrizione_anteprima": r.get("trascrizione", "")[:100],
                "path_img": r.get("img_path"),
                "punti_critici_conteggio": len(r.get("report", {}).get("analisi_per_immagine", [{}])[0].get("punti_critici", []))
            })

        st.session_state.debug_log = (
            f"SALVATAGGIO OK: {time.strftime('%H:%M:%S')}\n"
            f"CHIAVE: {chiave}\n\n"
            f"--- ANAGRAFICA (12 campi) ---\n"
            f"{json.dumps(data['anagrafica'], indent=2)}\n\n"
            f"--- STORICO REPORT ({len(report_preview)} elementi) ---\n"
            f"{json.dumps(report_preview, indent=2)}\n\n"
            f"--- EDITS (CONTENUTI REALI) ---\n"
            f"{json.dumps(data['edits'], indent=2)}"
        )
        
        st.toast("Salvato correttamente!", icon="💾")
        
    except Exception as e:
        st.session_state.debug_log = f"!!! ERRORE CRITICO !!!\n{str(e)}"
        st.error(f"Errore: {e}")

        







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
                
                # 1. Impostiamo i dati utente
                st.session_state.user_data = {
                    "username": username, 
                    "email": db_user["email"], 
                    "nome": real_name,
                    "id": db_user.get("id", "") 
                }
                
                # 2. Inizializziamo l'anagrafica se non esiste
                # if "anagrafica" not in st.session_state:
                #     st.session_state.anagrafica = {}
                
                # ORA recupera i dati: questo andrà a riempire o sovrascrivere 
                # i dizionari vuoti con quelli salvati nel browser
                recupera_stato_completo()
                
                # 4. Ricarichiamo per entrare nell'app
                st.rerun()
            else:
                st.error(f"❌ **Password errata!**")
        else:
            st.error(f"❌ **Utente non trovato!**")
    return None
