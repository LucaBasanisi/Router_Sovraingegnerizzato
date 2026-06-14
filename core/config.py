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

# Definizione dei modelli per i tre tier di difficoltà
CHAT_MODEL = "deepseek-v4-flash"      # Modello per domande veloci ed EASY
CODE_MODEL = "mimo-v2.5"              # Modello per compiti di coding intermedi (MEDIUM)
REASONING_MODEL = "deepseek-v4-pro"   # Modello intelligente per logica agentica (HARD)
CLASSIFIER_MODEL = "deepseek-v4-flash" # Modello economico usato solo per la classificazione iniziale

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
