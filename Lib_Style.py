
import streamlit as st

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