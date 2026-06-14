"""
Modulo di configurazione globale.
Questo file centralizza le costanti, gli indirizzi API e i nomi dei modelli
utilizzati in tutta l'applicazione per mantenere il codice pulito e manutenibile.
"""
import os
import json

# Percorso predefinito del file di configurazione dell'autenticazione di OpenCode
OPENCODE_AUTH_PATH = os.path.expanduser("~/.local/share/opencode/auth.json")

# URL base per l'API proxy di OpenCode
BASE_URL = "https://opencode.ai/zen/go/v1"

# Modello per l'orchestrazione dinamica (Project Manager)
ORCHESTRATOR_MODEL = "deepseek-v4-flash"

# Pool di Agenti Specializzati
GENERAL_CHAT_MODEL = "deepseek-v4-flash"   # Risponditore semplice per chiacchierate
DEVELOPER_AGENT_MODEL = "deepseek-v4-pro"  # Ottimizzato per scrivere codice (ReAct)
DOCUMENTER_AGENT_MODEL = "mimo-v2.5"       # Ottimizzato per spiegazioni e markdown
SECURITY_AUDITOR_MODEL = "glm-5.1"         # Ottimizzato per analisi di vulnerabilità e edge-cases

def get_api_key():
    """
    Legge la chiave API locale dal file auth.json di OpenCode.
    Ritorna la stringa della chiave se il file esiste ed è formattato correttamente,
    altrimenti ritorna None.
    """
    try:
        with open(OPENCODE_AUTH_PATH, "r") as f:
            return json.load(f)["opencode-go"]["key"]
    except:
        return None
