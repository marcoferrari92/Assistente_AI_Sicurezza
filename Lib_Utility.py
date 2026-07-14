

import random
import streamlit as st
from streamlit_local_storage import LocalStorage



# Metti questa istanza fuori, come variabile globale del modulo
_storage_cache = {}

def get_ls(chiave):
    # Usiamo un dizionario locale al modulo, NON nel session_state 
    # per evitare che il componente venga ricreato durante i rerun
    global _storage_cache
    
    if chiave not in _storage_cache:
        # Questa riga viene eseguita SOLO UNA VOLTA per chiave
        _storage_cache[chiave] = LocalStorage(key=chiave)
        
    return _storage_cache[chiave]


def resetta_tutto_il_sistema():
    # 1. Definisci le chiavi base necessarie per non far crashare l'app
    chiavi_base = ["mandataria", "mandante", "committente", "indirizzo", "città", "provincia", 
                   "commessa", "oggetto", "attività", "coordinamento", "personale", "verbali"]
    
    # 2. Resetta i dati
    st.session_state.anagrafica = {k: "" for k in chiavi_base} # Ricrea il dizionario con valori vuoti
    st.session_state.storico_report = []
    st.session_state.edits = {}
    st.session_state.user_data = None
    
    # 3. Logica di cancellazione localStorage esistente
    master = get_ls("MASTER_POINTER")
    chiave = master.getItem("chiave_valida")
    if chiave:
        try:
            get_ls(chiave).deleteItem("imprendo_dati")
        except: pass
        master.deleteItem("chiave_valida")
            
    st.session_state.ls_registry = {}
    st.toast("Sistema resettato!", icon="🔄")

# --- 2. FUNZIONI DI SALVATAGGIO E RECUPERO UNIFICATE ---
# 1. Inizializzazione (nella funzione inizializza_stato)
if "log_text" not in st.session_state:
    st.session_state.log_text = "Sistema pronto."
if "log_version" not in st.session_state:
    st.session_state.log_version = 0

# 2. Funzione di salvataggio
def salva_stato_completo():
    master = get_ls("MASTER_POINTER")
    chiave_attuale = master.getItem("chiave_valida")
    if not chiave_attuale:
        chiave_attuale = f"storage_{random.randint(10000, 99999)}"
        master.setItem("chiave_valida", chiave_attuale)
    
    localS = get_ls(chiave_attuale)
    data = {
        "anagrafica": st.session_state.anagrafica,
        "storico_report": st.session_state.storico_report,
        "edits": st.session_state.edits
    }
    localS.setItem("imprendo_dati", data)
    
    st.session_state.log_text = f"Salvato: {time.strftime('%H:%M:%S')}"
    st.session_state.log_version += 1
    st.rerun()

# 3. Widget nella sidebar
with st.sidebar.expander("🛠️ LOG DI SISTEMA", expanded=True):
    st.text_area(
        "Log:", 
        value=st.session_state.log_text, 
        key=f"log_area_{st.session_state.log_version}", 
        disabled=True
    )

        

# 4. Recupero
def recupera_stato_completo():
    master = LocalStorage(key="MASTER_POINTER")
    chiave_reale = master.getItem("chiave_valida")
    
    if not chiave_reale:
        return False
        
    localS = LocalStorage(key=chiave_reale)
    dati = localS.getItem("imprendo_dati")
    
    if dati:
        # Ripristino dati
        st.session_state.anagrafica = dati.get("anagrafica", {})
        st.session_state.edits = dati.get("edits", {})
        
        # --- RESETTA LE VERSIONI DEI WIDGET ---
        # Questo costringe i frammenti a rigenerare i widget con i nuovi dati caricati
        st.session_state.widget_version = {k: 0 for k in st.session_state.anagrafica.keys()}
        
        # Ripristino storico (logica bytes esistente)
        storico_recuperato = []
        for item in dati.get("storico_report", []):
            item_copy = item.copy()
            if "bytes" in item_copy and isinstance(item_copy["bytes"], str):
                item_copy["bytes"] = base64.b64decode(item_copy["bytes"])
            storico_recuperato.append(item_copy)
        st.session_state.storico_report = storico_recuperato
        
        return True
    return False



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
