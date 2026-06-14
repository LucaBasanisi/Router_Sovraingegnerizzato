"""
Modulo per l'Orchestrazione Dinamica (Ex Classificatore).
Si occupa di analizzare l'intenzione dell'utente (il prompt) e smistarla 
sugli agenti specializzati necessari a risolvere il problema,
ottimizzando tempo e denaro.
"""
import json
import httpx
from .config import ORCHESTRATOR_MODEL, BASE_URL

def pre_classify(user_prompt: str) -> list[str] | None:
    """
    Euristica veloce basata su semplici regole testuali.
    Evita di eseguire una costosa chiamata API per prompt banalissimi.
    """
    cleaned = user_prompt.strip().lower()
    
    # Se il prompt è molto corto, consideralo general_chat a prescindere
    if len(cleaned) < 15: 
        return ["general_chat"]
    
    # Se il prompt è una chiacchiera standard o un saluto, etichettalo come general_chat
    greetings = {"ciao", "hello", "hi", "hey", "help", "clear", "exit", "grazie", "thanks", "ok", "okay"}
    if cleaned in greetings: 
        return ["general_chat"]
        
    # Se non ricade in queste regole base, ritorna None e delega la decisione all'Orchestratore
    return None

async def classify_prompt(user_prompt: str, api_key: str) -> list[str]:
    """
    Analizza semanticamente un prompt avvalendosi dell'Orchestratore (LLM veloce).
    Risponde con una lista degli agenti richiesti.
    """
    # 1. Tentativo con euristica locale
    preset = pre_classify(user_prompt)
    if preset: 
        return preset

    # 2. Definizione dell'istruzione di sistema per l'orchestratore
    system_instruction = (
        "You are the Orchestrator of an AI company. Your job is to analyze the user query "
        "and decide which specialized agents are required.\n"
        "Available agents:\n"
        "- 'general_chat': for simple chit-chat, greetings, or basic definitions.\n"
        "- 'developer': for writing code, algorithms, manipulating files, using the terminal.\n"
        "- 'documenter': for writing documentation, READMEs, or explaining code.\n"
        "- 'security_auditor': for finding vulnerabilities, race conditions, edge cases, memory leaks.\n"
        "\nReply ONLY with a valid JSON format like this:\n"
        '{"required_agents": ["developer", "security_auditor"], "reasoning": "Needs to write secure code."}'
    )
    
    try:
        # 3. Invio asincrono della richiesta all'orchestratore
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "model": ORCHESTRATOR_MODEL, 
                "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_prompt}], 
                "temperature": 0.0, # ZERO creatività per avere output stabili
                "response_format": {"type": "json_object"}
            }
            response = await client.post(f"{BASE_URL}/chat/completions", json=payload, headers={"Authorization": f"Bearer {api_key}"})
            
            # Estrazione del JSON
            content = response.json()["choices"][0]["message"]["content"]
            result = json.loads(content)
            agents = result.get("required_agents", ["developer"])
            
            # Mappatura sicura della risposta
            if not isinstance(agents, list) or len(agents) == 0:
                return ["developer"]
                
            return [a.lower() for a in agents]
            
    except Exception as e:
        # In caso di errori di timeout o API down, passiamo l'utente al livello developer per sicurezza
        print(f"Orchestrator error: {e}")
        return ["developer"]
