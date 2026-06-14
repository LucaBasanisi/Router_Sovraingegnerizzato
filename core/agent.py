"""
Modulo dell'Agente e Generatore di Streaming Asincrono (SSE).
Questo è il "cuore" del Proxy Agentico. Intercetta la connessione HTTP del client,
lancia il loop decisionale del ReAct e fornisce all'utente finale le notifiche in streaming
falsificando la risposta Server-Sent Events finché l'agente non formula il pensiero testuale.
"""
import json
import os
from fastapi.responses import StreamingResponse
from .config import BASE_URL
from .tools import TOOLS_DEF, execute_bash_command, read_file_tool, write_file_tool, list_dir_tool

def agentic_stream_generator_factory(client, chosen_model, body, messages, headers, client_cwd):
    """
    Ritorna uno StreamingResponse che tiene viva la connessione HTTP.
    Il generatore interno (agentic_stream_generator) si occuperà di creare e restituire
    i frammenti (chunk) JSON validi, compatibili con le CLI moderne.
    """
    
    async def agentic_stream_generator():
        try:
            # Creiamo una copia della storia della chat locale su cui l'agente lavorerà 
            loop_messages = messages.copy()
            
            # Whitlist: puliamo il payload per evitare che opzioni streaming del client inibiscano il Tool Calling
            safe_keys = ["model", "temperature", "top_p", "max_tokens"]
            payload = {k: body[k] for k in safe_keys if k in body}
            payload["model"] = chosen_model
            
            # ATTENZIONE: Disabilitiamo lo stream verso il server LLM remoto 
            # altrimenti intercettare l'oggetto JSON del tool diventerebbe complesso.
            payload["stream"] = False
            
            # Attiviamo la possibilità per l'LLM di chiamare i tools definiti
            payload["tools"] = TOOLS_DEF
            
            # Definiamo un hard-limit di iterazioni per evitare cicli infiniti (Maximum Steps)
            for step in range(15):
                payload["messages"] = loop_messages
                
                try:
                    # Chiamata bloccante al modello "esperto"
                    resp = await client.post(f"{BASE_URL}/chat/completions", json=payload, headers=headers)
                    resp.raise_for_status()
                    result = resp.json()
                except Exception as e:
                    # SEZIONE DI GESTIONE ERRORE API 
                    # Se l'API restituisce 400 Bad Request, si forma un chunk in streaming per informare l'utente
                    err_details = f" Details: {e.response.text}" if hasattr(e, 'response') and e.response else ""
                    chunk = {"id": "err", "object": "chat.completion.chunk", "model": chosen_model, "choices": [{"index": 0, "delta": {"content": f"\n\n❌ Errore proxy LLM: {str(e)}{err_details}"}}]}
                    yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
                    break
                    
                message = result["choices"][0]["message"]
                
                # SEZIONE DELLA RISPOSTA FINALE
                # Se l'LLM non restituisce una chiamata ai tool, significa che ha una risposta discorsiva pronta
                if not message.get("tool_calls"):
                    content = message.get("content", "")
                    
                    # Simula lo streaming testuale suddividendo la stringa in blocchi di 50 caratteri 
                    # (per far apparire il testo "in tempo reale" nel client locale)
                    for i in range(0, len(content), 50):
                        yield f"data: {json.dumps({'id': 'fin', 'object': 'chat.completion.chunk', 'model': chosen_model, 'choices': [{'index': 0, 'delta': {'content': content[i:i+50]}}]})}\n\n".encode("utf-8")
                    
                    # Segnale di arresto al client locale e fine dell'SSE
                    yield f"data: {json.dumps({'id': 'fin', 'object': 'chat.completion.chunk', 'model': chosen_model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n".encode("utf-8")
                    yield b"data: [DONE]\n\n"
                    
                    # Uscita definitiva dal loop di ragionamento
                    break
                    
                # SEZIONE DELL'ESECUZIONE DEI TOOL
                tool_calls = message.get("tool_calls", [])
                
                # Aggiunge in cronologia la mossa che l'assistente ha deciso di fare, 
                # omettendo parametri non supportati dalle API rigorose (es. reason_content)
                clean_msg = {k: v for k, v in message.items() if k in ["role", "content", "tool_calls"]}
                loop_messages.append(clean_msg)
                
                # Iterazione dei tool richiesti dall'LLM
                for tool_call in tool_calls:
                    f_name = tool_call["function"]["name"]
                    try: 
                        # Estrazione parametro dal JSON e catch per sintassi malformata
                        args = json.loads(tool_call["function"]["arguments"])
                    except: 
                        args = {}
                    
                    alert_txt = f"\n> 🔧 **Agent:** `{f_name}`\n\n"
                    
                    # Logica di Routing (Switch-Case) per determinare l'azione da eseguire
                    if f_name == "run_bash_command":
                        cmd = args.get("cmd", "")
                        alert_txt = f"\n> 💻 **Bash:** `{cmd}`\n\n"
                        # Esegue sulla directory remota del client estrattà dal token
                        cmd_out = execute_bash_command(cmd, client_cwd or os.getcwd())
                        
                    elif f_name == "read_file":
                        path = args.get("path", "")
                        alert_txt = f"\n> 📖 **Lettura File:** `{path}`\n\n"
                        cmd_out = read_file_tool(path, client_cwd or os.getcwd())
                        
                    elif f_name == "write_file":
                        path = args.get("path", "")
                        alert_txt = f"\n> ✍️ **Scrittura File:** `{path}`\n\n"
                        cmd_out = write_file_tool(path, args.get("content", ""), client_cwd or os.getcwd())
                        
                    elif f_name == "list_dir":
                        path = args.get("path", ".")
                        alert_txt = f"\n> 📂 **Lista Dir:** `{path}`\n\n"
                        cmd_out = list_dir_tool(path, client_cwd or os.getcwd())
                        
                    else:
                        cmd_out = "Tool not found"
                        
                    # Streamiamo verso la UI dell'utente l'icona con l'azione in corso
                    yield f"data: {json.dumps({'id': 'tool', 'object': 'chat.completion.chunk', 'model': chosen_model, 'choices': [{'index': 0, 'delta': {'content': alert_txt}}]})}\n\n".encode("utf-8")
                    # E infine streamiamo un segnale di azione completata per feedback visivo
                    yield f"data: {json.dumps({'id': 'tool-fin', 'object': 'chat.completion.chunk', 'model': chosen_model, 'choices': [{'index': 0, 'delta': {'content': f'> 🟢 **Fatto.**\\n\\n'}}]})}\n\n".encode("utf-8")
                    
                    # Iniettiamo l'esito reale del comando dentro la cronologia in memoria sotto forma di "tool" role.
                    # Alla prossima iterazione del loop 'for', l'LLM leggerà questo esito.
                    loop_messages.append({"role": "tool", "tool_call_id": tool_call["id"], "content": cmd_out})
                    
            else:
                # RETRY STORM PREVENTION BLOCK
                # Questo costrutto 'else' è agganciato al ciclo 'for'. Si esegue solo se 
                # il ciclo for termina naturalmente esaurendo le 15 iterazioni senza incappare in un "break".
                # Significa che l'intelligenza artificiale non ha formulato la risposta definitiva e andrebbe in timeout.
                avviso_limite = "\n\n⚠️ **Limite di sicurezza raggiunto (15 iterazioni).** L'agente è stato forzatamente fermato per evitare cicli infiniti."
                chunk_limite = {"id": "limite-max", "object": "chat.completion.chunk", "model": chosen_model, "choices": [{"index": 0, "delta": {"content": avviso_limite}, "finish_reason": "stop"}]}
                
                # Invia un messaggio visuale e tronca istantaneamente lo streaming con DONE, 
                # informando il Client locale che la fine è intenzionale e bloccando così un auto-retry storm.
                yield f"data: {json.dumps(chunk_limite)}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"
                
        finally: 
            # In qualsiasi caso, errore o successo, chiudi la connessione HTTPS persistente con il fornitore (Deepseek)
            await client.aclose()
        
    return StreamingResponse(agentic_stream_generator(), media_type="text/event-stream")
