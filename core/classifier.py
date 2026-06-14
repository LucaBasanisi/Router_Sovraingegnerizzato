"""
Modulo per la Classificazione delle Query (Dynamic Routing).
Si occupa di analizzare l'intenzione dell'utente (il prompt) e smistarla 
sulla tipologia di intelligenza (EASY, MEDIUM, HARD) necessaria a risolvere il problema,
ottimizzando tempo e denaro.
"""
import httpx
from .config import CLASSIFIER_MODEL, BASE_URL

def pre_classify(user_prompt: str) -> str | None:
    """
    Euristica veloce basata su semplici regole testuali.
    Evita di eseguire una costosa chiamata API per prompt banalissimi.
    """
    cleaned = user_prompt.strip().lower()
    
    # Se il prompt è molto corto (es. "aiuto", "come fai?"), consideralo EASY a prescindere
    if len(cleaned) < 15: 
        return "EASY"
    
    # Se il prompt è una chiacchiera standard o un saluto, etichettalo come EASY
    greetings = {"ciao", "hello", "hi", "hey", "help", "clear", "exit", "grazie", "thanks", "ok", "okay"}
    if cleaned in greetings: 
        return "EASY"
        
    # Elenco di parole chiave che denotano richieste molto complesse o uso del terminale
    hard_keywords = ["implementata", "architecture", "architettura", "memory leak", "race condition", "dietro le quinte", "system design", "progettazione", "design pattern", "tool", "esegui", "bash", "comando"]
    
    # Se è presente una keyword hard, instrada direttamente all'agente avanzato
    if any(kw in cleaned for kw in hard_keywords): 
        return "HARD"
        
    # Se non ricade in queste regole base, ritorna None e delega la decisione all'LLM Classifier
    return None

async def classify_prompt(user_prompt: str, api_key: str) -> str:
    """
    Analizza semanticamente un prompt avvalendosi di un LLM veloce.
    Il classificatore risponderà esclusivamente con un'etichetta.
    """
    # 1. Tentativo con euristica locale
    preset = pre_classify(user_prompt)
    if preset: 
        return preset

    # 2. Definizione dell'istruzione di sistema per il classificatore
    system_instruction = (
        "You are an AI router. Classify the user query into: 'EASY', 'MEDIUM', or 'HARD'.\n"
        "EASY: simple chat, definitions.\n"
        "MEDIUM: standard boilerplate, simple refactor.\n"
        "HARD: complex algorithms, file manipulation, using tools, deep architectural issues.\n"
        "Reply exactly 'EASY', 'MEDIUM', or 'HARD'."
    )
    
    try:
        # 3. Invio asincrono della richiesta al modello più veloce (es. deepseek-v4-flash)
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "model": CLASSIFIER_MODEL, 
                "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_prompt}], 
                "temperature": 0.0, # ZERO creatività per avere output stabili
                "max_tokens": 5     # Vogliamo solo una singola parola (EASY/MEDIUM/HARD)
            }
            response = await client.post(f"{BASE_URL}/chat/completions", json=payload, headers={"Authorization": f"Bearer {api_key}"})
            
            # Estrazione della parola restituita e sanitizzazione (tutto in maiuscolo)
            result = response.json()["choices"][0]["message"]["content"].strip().upper()
            
            # Mappatura sicura della risposta
            if "HARD" in result: return "HARD"
            elif "MEDIUM" in result: return "MEDIUM"
            return "EASY"
            
    except:
        # In caso di errori di timeout o API down, passiamo l'utente al livello massimo (HARD) per sicurezza
        return "HARD"
