# Architettura e Decisioni Tecniche

Questo documento raccoglie le decisioni architetturali complesse implementate in **OpenCode Go Router**, per mantenere traccia del "perché" certe soluzioni apparentemente strane o sovraingegnerizzate sono state adottate.

## 1. Gestione della CWD (Cartella di Lavoro) in modo "Stateless"
**Problema:** Il proxy (`router.py`) gira in background, ma l'utente invoca la CLI `opencode` da varie cartelle del sistema. Come fa il proxy a sapere in quale cartella si trova l'utente per far eseguire all'agente i comandi bash corretti?
**Soluzione "Cloud Native" (Trick del Bearer Token):** 
Non usiamo file temporanei sul disco. Invece, abbiamo creato un wrapper bash in `~/.opencode/bin/opencode` che prima di chiamare il vero binario altera la variabile d'ambiente dell'API key:
`export OPENCODE_API_KEY="dummy|$PWD"`
In questo modo, la CLI inoltra la cartella di lavoro direttamente dentro l'header HTTP `Authorization: Bearer dummy|/path/to/cwd`.
Il nostro router estrae il percorso per la sessione e usa internamente la vera chiave API. Questo rende il router al 100% **stateless** e pronto per l'implementazione Kubernetes a microservizi (Step 9).

## 2. Lo Streaming "Simulato" (Anti-Timeout) nel Ciclo Agentico
**Problema:** Quando il modello LLM entra in un "Agent Loop" per chiamare i tool (es. `run_bash_command`), l'esecuzione può durare svariati secondi (o minuti per task lunghi). La CLI originaria di OpenCode Go è progettata per ricevere un flusso testuale continuo (streaming) e, se non riceve nulla per troppo tempo, andrà in timeout chiudendo la connessione.
Inoltre, quando un LLM usa il Function Calling in modalità stream (`stream=True`), l'output del JSON del tool arriva frammentato in delta ed è infernale da ricostruire e parsare nel proxy.

**Soluzione (Finto Streaming SSE):**
Quando la query è complessa ("HARD") e il router decide di usare l'Agente:
1. Il router **spegne** lo stream verso l'LLM (`stream=False`), così da ricevere i blocchi JSON dei tools integri e facili da parsare.
2. Per evitare il timeout del client OpenCode Go e per far vedere all'utente cosa succede, il router **simula una risposta in stream (SSE)** generando a mano dei chunk conformi allo standard OpenAI (es. `data: {"choices": [{"delta": {"content": "> 🔧 Agente esegue: ls -la"}}]}\n\n`).
3. Quando l'Agente ha finito di eseguire i tool e restituisce la risposta finale testuale, il router invia la risposta in piccoli chunk per emulare l'esperienza di scrittura classica prima di chiudere lo stream con `data: [DONE]\n\n`.

## 3. Modularizzazione Architetturale ("Divide et Impera")
**Problema:** `router.py` stava accumulando troppe responsabilità (Endpoint REST, Classificazione LLM, definizioni Tool JSON, esecuzione comandi OS, ciclo Agentico e SSE Streaming), configurandosi come un tipico anti-pattern "God Object". In vista dell'introduzione dell'Orchestrazione Multi-Agente, il file sarebbe collassato su se stesso diventando in-manutenibile.

**Soluzione (Core Modulare):**
Il codice è stato disaccoppiato in moduli monolitici coesi all'interno della directory `core/`:
- `core/config.py`: Gestione costanti e secret management.
- `core/classifier.py`: Logica di routing dinamico (Euristica testuale locale + LLM via API) isolata.
- `core/tools.py`: Astrazione completa delle operazioni sul FileSystem (read, write, bash) e mapping del JSON.
- `core/agent.py`: La complessa macchina a stati dell'agente ReAct asincrono e del protocollo HTTP/SSE.
- `router.py` (Main): Degradato al semplice ruolo di API Controller. Riceve la request FastAPI, instanzia il flow corretto (Passivo o Agentico) e ritorna la response, senza gestire logica di dominio.
