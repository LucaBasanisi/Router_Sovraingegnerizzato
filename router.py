"""
Entry-point Principale e Server FastAPI.
Questo file serve come punto di ascolto (porta 8080) per le richieste del terminale locale.
Rappresenta l'infrastruttura di base, il vigile urbano che prende il traffico e lo indirizza
verso i moduli specialistici.
"""
import json
import logging
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn

# Importiamo i nostri componenti modulari e commentati
from core.config import get_api_key, BASE_URL, CHAT_MODEL, CODE_MODEL, REASONING_MODEL
from core.classifier import classify_prompt
from core.agent import agentic_stream_generator_factory

# Setup del sistema di logging visivo nel terminale per operazioni di debug
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("opencode-router")

app = FastAPI(title="OpenCode Go 3-Tier Dynamic Router")

# Precaricamento della Chiave API all'avvio del router per evitare di leggerla da disco su ogni request
API_KEY = get_api_key()

def extract_text_content(content) -> str:
    """
    Funzione di utility per estrapolare stringhe testuali in modo sicuro, 
    nel caso in cui il client CLI di OpenCode formatti i messaggi 'content' 
    come Array di Oggetti (es. messaggi multimediali) invece di stringhe grezze.
    """
    if isinstance(content, str): 
        return content
    if isinstance(content, list): 
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Endpoint intercettatore che emula l'interfaccia API standard (/v1/chat/completions).
    Qui avviene l'iniezione dello stato, il controllo della chiave e l'inoltro ai modelli.
    """
    
    # ESTRAZIONE STATO (CWD) DAL TOKEN BEARER
    # La CWD ci viene passata dallo script bash custom di avvio dell'utente
    auth_header = request.headers.get("Authorization", "")
    client_cwd = None
    if auth_header.startswith("Bearer ") and "|" in auth_header:
        # Separiamo la password fittizia dal vero payload (la cartella di lavoro in cui si trova l'utente)
        _, client_cwd = auth_header[len("Bearer "):].split("|", 1)

    # RE-CONTROLLO API KEY 
    # Controllo di sicurezza se la chiave non era pronta all'avvio dell'app
    global API_KEY
    if not API_KEY: 
        API_KEY = get_api_key()
    if not API_KEY: 
        raise HTTPException(status_code=500, detail="API Key not found in auth.json")

    # PARSING DELLA RICHIESTA
    body = await request.json()
    messages = body.get("messages", [])
    
    # Estraiamo l'ultimo messaggio immesso dall'utente nel terminale (l'ultimo con role "user")
    last_user_msg = extract_text_content(next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), ""))
    
    # CLASSIFICAZIONE DINAMICA TIER-ROUTING (Sceglie il livello di intelligenza necessario)
    decision = await classify_prompt(last_user_msg, API_KEY) if last_user_msg else "EASY"

    # Selezione del motore LLM da avviare basandosi sulla classificazione (FinOps Strategy)
    if decision == "HARD": chosen_model = REASONING_MODEL
    elif decision == "MEDIUM": chosen_model = CODE_MODEL
    else: chosen_model = CHAT_MODEL

    # Stampa sul terminale lato server il Tier scelto per scopi di monitoraggio visivo
    logger.info(f"Tier: {decision} -> Routing to: {chosen_model}")

    # CONFIGURAZIONE DEL CLIENT ASINCRONO
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    client = httpx.AsyncClient(timeout=60.0)
    
    # Verifica se l'utente richiede una risposta in live streaming (comportamento standard della CLI)
    is_stream = body.get("stream", False)

    # === DIVERGIMENTO DEGLI INOLTRI === #

    # 1. INOLTRO AGENTICO (MODALITA' PROATTIVA - HARD)
    # Se il modello selezionato è il REASONING_MODEL e si richiede streaming, evoca l'intelligenza asincrona multi-step.
    if chosen_model == REASONING_MODEL and is_stream:
        return agentic_stream_generator_factory(client, chosen_model, body, messages, headers, client_cwd)

    # 2. INOLTRO PASSIVO (MODALITA' SPECCHIO / STANDBY - EASY/MEDIUM)
    # Per chiamate semplici e veloci, funge da semplice "proxy pass" sovrascrivendo unicamente il modello.
    body["model"] = chosen_model
    
    if is_stream:
        # Se è in streaming, crea un tunnel diretto tra l'API Provider e il Client Locale (Pass-through Server-Sent Events)
        async def stream_generator():
            try:
                async with client.stream("POST", f"{BASE_URL}/chat/completions", json=body, headers=headers) as resp:
                    resp.raise_for_status()
                    # Rilancia i chunk (iter_raw) esattamente come ci arrivano senza alterarli
                    async for chunk in resp.aiter_raw(): 
                        yield chunk
            except Exception as e: 
                # Gestione standard errori di pass-through
                yield f"data: {json.dumps({'error': str(e)})}\n\n".encode("utf-8")
            finally: 
                await client.aclose()
                
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        # 3. CHIAMATA A BLOCCO UNICO
        # Raro: il client locale non richiede streaming, quindi si invia una PostRequest statica 
        # e si ritorna il dizionario JSON in blocco unico.
        try:
            resp = await client.post(f"{BASE_URL}/chat/completions", json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except: 
            raise HTTPException(status_code=500, detail="Upstream Provider Error")
        finally: 
            await client.aclose()

if __name__ == "__main__":
    # Avvia l'istanza ASGI locale all'indirizzo loopback classico 127.0.0.1 porta 8080
    uvicorn.run(app, host="127.0.0.1", port=8080)
