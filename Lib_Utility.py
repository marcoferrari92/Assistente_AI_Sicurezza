
import time
import random
import json
import os
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
        data = {
            "anagrafica": st.session_state.anagrafica,
            "storico_report": st.session_state.storico_report,
            "edits": st.session_state.edits
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
