import io
import base64
import json
import streamlit as st
from openai import OpenAI, AuthenticationError, RateLimitError

from Lib_Outlook import invia_email_allerta_crediti


def verifica_connessione_ai():
    """
    Verifica la validità della API Key e la presenza di credito.
    Da richiamare all'inizio dell'app.
    """
    try:
        # Assicurati di avere il client inizializzato correttamente
        client = OpenAI(api_key=st.secrets["openai_key"])
        
        # Facciamo una chiamata leggerissima per testare
        client.models.list()
        return True, "Connessione OK"

    except AuthenticationError:
        st.error("Errore: API Key non valida. Controlla i secrets.")
        return False, "Auth Error"
        
    except RateLimitError as e:
        if "insufficient_quota" in str(e):
            st.error("⚠️ **Credito API esaurito!** Vai su platform.openai.com per ricaricare.")
            invia_email_allerta_crediti()
        else:
            st.error(f"Errore di limite API: {e}")
        return False, "Quota Exceeded"
        
    except Exception as e:
        st.error(f"Impossibile connettersi ai servizi AI: {str(e)}")
        return False, "Generic Error"





def elabora_anagrafica_ai(audio_bytes):

    try: 
        client = OpenAI(api_key=st.secrets["openai_key"])
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"
        
        # 1. Trascrizione
        transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        
        # 2. Estrazione dati strutturati con AI
        prompt = f"""
        Sei l'assistente di un ispettore sicurezza nei cantieri che sta dirigendo un report.
        Estrai le informazioni dal seguente testo e restituiscile in formato JSON:
        "{transcript.text}"
        
        Restituisci JSON con queste chiavi (se un dato manca, metti una stringa vuota):
        {{
            "mandataria": "Elenco mandatarie (separate da ,)",
            "mandante": "Elenco mandanti (separate da ,)",
            "committente": "Nome committente",
            "indirizzo": "Indirizzo committente",
            "città": "Città",
            "provincia": "Provincia in formato (XX)",
        }}
        """
        
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        return json.loads(resp.choices[0].message.content)
    
    except RateLimitError as e:
        # Questo intercetta SPECIFICAMENTE il limite raggiunto
        st.error("⚠️ ERRORE API: Limite di quota raggiunto o credito esaurito.")
        invia_email_allerta_crediti()
        return None, None
    except Exception as e:
        # Questo intercetta qualsiasi altro errore
        st.error(f"⚠️ ERRORE GENERICO: {str(e)}")
        return None, None
    




def elabora_campo_tecnico_ai(audio_bytes, nome_campo):

    try:
        client = OpenAI(api_key=st.secrets["openai_key"])
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"
        transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        
        # DEFINIZIONE DEI PROMPT ESPANSI
        if nome_campo == "commessa":
            istruzione = f"""
            Trascrizione: {transcript.text}
            
            Riassumi la commessa in modo conciso ma esasustivo.
            
            REGOLE:
            - Usa un linguaggio tecnico, professionale e formale. 
            - NON INVENTARE, ATTIENITI ALLA TRASCRIZIONE. Se è breve, devi essere breve.
            - Vietato l'uso di elenchi puntati o numerati.
            - Vietato inserire prefissi come "Commessa:" o etichette simili.
            - Inizia direttamente a scrivere il contenuto.
            
            """
            
        elif nome_campo == "oggetto":
            istruzione = f"""
            Trascrizione: {transcript.text}
            
            Riassumi l'oggetto dell'incarico in modo conciso ma esasustivo.
            
            REGOLE:
            - Usa un linguaggio tecnico, professionale e formale. 
            - NON INVENTARE, ATTIENITI ALLA TRASCRIZIONE. Se è breve, devi essere breve.
            - NON AGGIUNGERE NESSUNA INFORMAZIONE NON PRESENTE NELLA TRASCRIZIONE.
            - Vietato l'uso di elenchi puntati o numerati.
            - Vietato inserire prefissi come "Oggetto:" o etichette simili.
            - Inizia direttamente a scrivere il contenuto.
            
            """
            
        elif nome_campo == "attività":
            istruzione = f"""
            Trascrizione: {transcript.text}
            
            Riassumi le attività lavorative in corso nel cantiere in modo conciso ma esaustivo.
            
            REGOLE:
            - Usa un linguaggio tecnico, professionale e formale. 
            - NON INVENTARE, ATTIENITI ALLA TRASCRIZIONE. Se è breve, devi essere breve. 
            - NON AGGIUNGERE NESSUNA INFORMAZIONE NON PRESENTE NELLA TRASCRIZIONE.
            - Vietato l'uso di elenchi puntati o numerati.
            - Vietato inserire prefissi come "Attività:" o etichette simili.
            - Inizia direttamente a scrivere il contenuto.
            
            """
            
        elif nome_campo == "coordinamento":
            istruzione = f"""
            Trascrizione: {transcript.text}
            
            Riassumi le attività di coordinamento e vigilanza in modo puramente discorsivo.
            
            REGOLE:
            - Usa un linguaggio tecnico, professionale e formale. 
            - NON INVENTARE, ATTIENITI ALLA TRASCRIZIONE. Se è breve, devi essere breve. 
            - NON AGGIUNGERE NESSUNA INFORMAZIONE NON PRESENTE NELLA TRASCRIZIONE.
            - Vietato l'uso di elenchi puntati o numerati.
            - Vietato inserire prefissi come "Coordinamento:" o etichette simili.
            - Inizia direttamente a scrivere il contenuto.
            """
            
        elif nome_campo == "personale":
            istruzione = f"""
            Trascrizione: {transcript.text}
            
            Estrai il personale presente in cantiere menzionato nella trascrizione. 
            Per ogni persona trovata, scrivi una riga nel formato: Nome Cognome - Azienda di appartenenza.
            
            REGOLE:
            - Usa un linguaggio tecnico, professionale e formale. 
            - NON INVENTARE, ATTIENITI ALLA TRASCRIZIONE. Se non viene menzionata l'azienda, scrivi il nome seguito da "- Non specificata".
            - Restituisci un elenco riga per riga (ogni persona sulla sua riga).
            - Vietato inserire prefissi come "Personale:" o etichette simili.
            - Inizia direttamente a scrivere il contenuto della prima riga.
            """
            
        elif nome_campo == "verbali":
            istruzione = f"""
            Trascrizione: {transcript.text}
            
            Riassumi le prescrizioni, le sospensioni e i verbali emessi in modo conciso.
            
            REGOLE:
            - Usa un linguaggio tecnico, professionale e formale.
            - NON INVENTARE, ATTIENITI ALLA TRASCRIZIONE. Se è breve, devi essere breve. 
            - NON AGGIUNGERE NESSUNA INFORMAZIONE NON PRESENTE NELLA TRASCRIZIONE. 
            - Vietato inserire prefissi come "Verbali:" o etichette simili.
            - Inizia direttamente a scrivere il contenuto.
            """
            
        else:
            istruzione = f"Trascrizione: {transcript.text}. Redigi un resoconto tecnico discorsivo."

        # CHIAMATA API
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": "Sei un tecnico della sicurezza. Scrivi solo testo discorsivo narrativo. Vietato usare elenchi, trattini, etichette o prefissi all'inizio della risposta."
                },
                {"role": "user", "content": istruzione}
            ]
        )
        
        testo = resp.choices[0].message.content.strip()
            
        return testo

    except RateLimitError as e:
        # Questo intercetta SPECIFICAMENTE il limite raggiunto
        st.error("⚠️ ERRORE API: Limite di quota raggiunto o credito esaurito.")
        invia_email_allerta_crediti()
        return None, None
    except Exception as e:
        # Questo intercetta qualsiasi altro errore
        st.error(f"⚠️ ERRORE GENERICO: {str(e)}")
        return None, None
    




def analizza_sicurezza_cantiere(audio_bytes, image_file):
    """
    Analizza una singola immagine e le note vocali.
    image_file: l'oggetto file di streamlit (quello che ha .name e .getvalue())
    """

    try:
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

    except RateLimitError as e:
        # Questo intercetta SPECIFICAMENTE il limite raggiunto
        st.error("⚠️ ERRORE API: Limite di quota raggiunto o credito esaurito.")
        invia_email_allerta_crediti()
        return None, None
    except Exception as e:
        # Questo intercetta qualsiasi altro errore
        st.error(f"⚠️ ERRORE GENERICO: {str(e)}")
        return None, None

