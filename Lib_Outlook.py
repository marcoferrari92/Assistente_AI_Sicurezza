
import time
import streamlit as st
import requests
import base64




def invia_email_allerta_crediti():
    # Destinatari fissi a cui arriva l'avviso
    destinatari = ["m.zaltron@imprendosrl.com", "raffaella@imprendosrl.com", "segreteria@imprendosrl.com"]
    
    try:
        # 1. Recupero credenziali (SOLO ID E SECRET, non l'email)
        config = st.secrets["microsoft_exchange"]
        client_id = config["client_id"]
        client_secret = config["client_secret"]
        tenant_id = config["tenant_id"]
        
        # 2. Recupero email mittente DALLO STATO DELL'UTENTE LOGGATO
        if not st.session_state.user_data or "email" not in st.session_state.user_data:
            st.error("Errore: Utente non loggato o email mancante nello stato.")
            return False, "Utente non loggato"
            
        sender_email = st.session_state.user_data["email"]

        # 3. Ottenimento Token (Stessa logica)
        url_oauth = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        payload_oauth = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default"
        }
        risposta_oauth = requests.post(url_oauth, data=payload_oauth)
        if risposta_oauth.status_code != 200:
            return False, f"Errore Auth: {risposta_oauth.text}"
        
        token = risposta_oauth.json().get("access_token")

        # 4. Invio per ogni destinatario
        risultati = []
        for destinatario in destinatari:
            email_payload = {
                "message": {
                    "subject": "⚠️ ALLERTA CRITICA: Credito OpenAI Esaurito",
                    "body": {
                        "contentType": "HTML",
                        "content": f"<p>L'utente <strong>{st.session_state.user_data['nome']}</strong> ha riscontrato l'esaurimento del credito OpenAI.</p>"
                    },
                    "toRecipients": [{"emailAddress": {"address": destinatario}}]
                },
                "saveToSentItems": "true"
            }

            url_api = f"https://graph.microsoft.com/v1.0/users/{sender_email}/sendMail"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            
            risposta = requests.post(url_api, json=email_payload, headers=headers)
            
            if risposta.status_code == 202:
                st.success(f"✅ Allerta inviata da {sender_email} a {destinatario}")
                risultati.append(True)
            else:
                st.error(f"❌ Errore invio da {sender_email}: {risposta.status_code} - {risposta.text}")
                risultati.append(False)

        return all(risultati), "Processo completato"

    except Exception as e:
        st.error(f"Errore critico invio allerta: {str(e)}")
        return False, str(e)
    





def invia_report_via_email_graph(doc_bytes, nome_file, user_email):
    

    try:
        # 1. Recupero credenziali
        config = st.secrets["microsoft_exchange"]
        client_id = config["client_id"]
        client_secret = config["client_secret"]
        tenant_id = config["tenant_id"]

        # 2. Ottenimento Token
        url_oauth = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        payload_oauth = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default"
        }
        risposta_oauth = requests.post(url_oauth, data=payload_oauth)
        if risposta_oauth.status_code != 200:
            return False, f"Errore Auth: {risposta_oauth.text}"
        
        token = risposta_oauth.json().get("access_token")

        # 3. Preparazione allegato in Base64 (come nel tuo codice collaudato)
        encoded_content = base64.b64encode(doc_bytes).decode('utf-8')
        
        email_payload = {
            "message": {
                "subject": f"Report Sicurezza Cantiere - {time.strftime('%Y-%m-%d %H:%M')}",
                "body": {
                    "contentType": "HTML",
                    "content": "<p>In allegato il report di sicurezza generato.</p>"
                },
                "toRecipients": [{"emailAddress": {"address": user_email}}],
                "attachments": [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": nome_file,
                        "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "contentBytes": encoded_content
                    }
                ]
            },
            "saveToSentItems": "true"
        }

        # 4. Invio
        url_api = f"https://graph.microsoft.com/v1.0/users/{user_email}/sendMail"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        risposta = requests.post(url_api, json=email_payload, headers=headers)

        if risposta.status_code == 202:
            return True, "Email inviata con successo!"
        else:
            return False, f"Errore API ({risposta.status_code}): {risposta.text}"

    except Exception as e:
        return False, str(e)