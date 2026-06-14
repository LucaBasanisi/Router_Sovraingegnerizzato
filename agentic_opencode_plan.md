# OpenCode Go: Agentic Proxy Plan

## 1. Il Concetto Base
Trasformare il router `router.py` da un semplice proxy di inoltro (pass-through) a un vero e proprio **Agente Autonomo**. Sfruttando la posizione "Man-in-the-Middle", il router intercetta i prompt dell'utente e avvia un ciclo di ragionamento e azione (ReAct) locale, dotando il modello LLM (come `deepseek-v4-pro`) della capacità di chiamare funzioni di sistema (Tools).

## 2. Flusso di Esecuzione Architetturale
1. **Intercettazione**: OpenCode Go invia un payload JSON a `/v1/chat/completions`.
2. **Analisi del Contesto**: Il router estrae il prompt, gli eventuali snippet di codice e tenta di dedurre la cartella di lavoro (CWD).
3. **Agent Loop (ReAct)**:
   - L'LLM valuta la richiesta.
   - L'LLM decide di invocare un Tool (es. `execute_bash`, `read_file`).
   - Il Router esegue il Tool sul sistema locale e restituisce l'output all'LLM.
   - Il ciclo si ripete finché l'LLM non ha una risposta definitiva.
4. **Streaming (Keep-Alive)**: Durante i "pensieri" dell'agente, il router fa streaming di log testuali verso OpenCode Go (es. `> Eseguendo comando...`) per prevenire il timeout del client HTTP.
5. **Risposta Finale**: Il router impacchetta la soluzione finale nell'ultimo chunk del flusso o nel JSON finale.

## 3. Sfide Tecniche & Soluzioni (Design Decisions)
- **Timeout HTTP & UI Pulita**: I loop agentici sono lenti. OpenCode Go andrà in timeout se non riceve dati. 
  *Decisione*: Il proxy effettuerà lo streaming di un'animazione testuale continua (es. "Analisi in corso... 🤔") verso OpenCode Go senza inquinare la UI con i log reali dell'agente. Questo tiene viva la connessione HTTP mantenendo pulita la chat.
- **Cartella di Lavoro (CWD)**: Il proxy gira in background, ignaro di dove l'utente stia eseguendo OpenCode Go.
  *Decisione*: Verrà creato un piccolo script "wrapper" per OpenCode Go. Questo wrapper leggerà la directory corrente del terminale (`$PWD`) e la inietterà automaticamente negli header HTTP prima di inviare la richiesta al proxy.
- **Sicurezza**: Esecuzione di codice arbitrario.
  *Soluzione*: Modalità "Ask for Permission" opzionale o limiti hard-coded al numero di iterazioni massime (es. max_steps = 5).

## 4. Decisioni Architetturali (Step 6 → 7)

Le seguenti scelte definiscono l'architettura finale del sistema multi-agente:

| Decisione | Scelta | Implicazione |
|---|---|---|
| **Comunicazione tra agenti** | Memoria Condivisa | Gli agenti leggono i risultati altrui prima di finalizzare (es. il Documentatore legge il codice dello Sviluppatore) |
| **Selezione degli agenti** | Flash decide autonomamente | Nessuna sintassi manuale richiesta; Flash interpreta il prompt e sceglie chi chiamare |
| **Memoria tra richieste** | Per processo (RAM) | La sessione corrisponde alla durata del router. Finché è acceso è una sessione; al riavvio si azzera |
| **Gerarchia di delega** | Agenti ricorsivi (DAG) | Un agente può delegare sotto-task ad altri agenti specializzati, formando un grafo di esecuzione |

### ⚠️ Rischio: Cicli Infiniti (Archi Ciclici nel DAG)
Con la delega ricorsiva esiste il rischio di loop (es. Revisore → chiede riscrittura → Sviluppatore → Revisore insoddisfatto → ...). **Soluzione obbligatoria**: implementare uno stack di esecuzione con un limite di profondità di ricorsione (es. `max_depth = 3`).

## 5. Piano di Implementazione a Step

### Step 1: Wrapper CWD — Sostituzione Trasparente di `opencode`
- [x] Creare uno script bash wrapper che esporta la variabile `OPENCODE_API_KEY` con il valore `dummy|$PWD` prima di invocare il binario originale (per iniettare in modo stateless la CWD tramite Bearer Token, utile per lo Step 9).
- [x] Rinominare il binario originale da `opencode` a `opencode-bin`.
- [x] Sostituire il comando `opencode` nel `PATH` (`~/.opencode/bin/opencode`), garantendo l'esperienza utente identica.
- [x] Verificare che il router legga correttamente l'header `Authorization`, estragga la CWD e la logghi (conferma di setup).

### Step 2: Proof of Concept (PoC) Tool Calling
- [x] Modificare la chiamata a `deepseek-v4-pro` nel router per supportare la sintassi di Function Calling (o tool use).
- [x] Implementare un singolo tool locale in Python: `run_bash_command(cmd: str) -> str` con **libertà totale di esecuzione** (nessuna whitelist).
- [x] La protezione è garantita da: (a) limite di iterazioni `max_steps`, (b) **log esplicito in streaming** di ogni comando eseguito direttamente nella chat (es. `🔧 Eseguendo: git status`), così l'utente è sempre consapevole.
- [x] Cablare l'LLM affinché possa chiamare la funzione e ricevere il risultato in risposta.

### Step 3: Gestione dello Streaming (Anti-Timeout)
- [x] Aggiornare la funzione di stream per inviare i "pensieri" del modello (es. "Tool Call invocato...") direttamente sulla UI di OpenCode Go, formattati come Markdown.
- [x] Testare task lunghi (es. "fai un find di tutti i file js e contali") per verificare che OpenCode Go non chiuda la connessione.

### Step 4: Refactoring in un vero Agent Loop
- [x] Costruire un vero loop `while not is_final_answer:` attorno alla logica.
- [x] Aggiungere altri tool: `read_file`, `write_file`, `list_dir`. (Nota: rimandati o coperti da run_bash_command per flessibilità)
- [x] Inserire un limite di sicurezza (max 15 iterazioni) per evitare cicli infiniti.

### Step 5: Testing Finale e Ottimizzazione
- [x] Usare OpenCode Go normalmente e testare task agentici come "Crea un nuovo componente React e installa le dipendenze".

### Step 6: L'Azienda Virtuale (Orchestrazione Multi-Agente Statica) — *Preparazione per lo Step 7*
> ⚠️ **Questo step non è l'obiettivo finale.** Ha come unico scopo costruire e testare l'infrastruttura parallela (streaming, sintetizzatore, fault tolerance) che servirà allo Step 7. Il pool di agenti qui è fisso e cablato nel codice: è uno step di addestramento, non il traguardo.

- [ ] Implementare Flash come "Project Manager" per scomporre il prompt dell'utente in due task fissi: **Codice** e **Documentazione**.
- [ ] Sfruttare `asyncio.gather` in Python per eseguire richieste in parallelo a modelli specializzati (`deepseek-v4-pro` per il codice, `minimax` o `mimo-v2.5` per i docs).
- [ ] Sviluppare un Agente "Sintetizzatore" che unisce i risultati in un'unica risposta streaming coerente verso OpenCode Go.
- [ ] Gestione degli Errori (Fault Tolerance): se un agente fallisce, il Sintetizzatore restituisce il lavoro completato con un avviso (es. "Codice pronto, documentazione fallita"), senza bloccare il flusso.

### Step 7: 🏆 Obiettivo Finale — Swarm Dinamico (Orchestrazione Autonoma)
> Ora creiamo un sistema in cui Flash non segue una pipeline fissa, ma **decide autonomamente in tempo reale** quali agenti specializzati attivare in base al contesto del prompt. Il grafo di esecuzione è un DAG dinamico con memoria condivisa e delega ricorsiva.

- [x] Definire un **pool di Agenti Specializzati** (es. `Sviluppatore`, `Documentatore`, `DBA_SQL`, `Revisore_Sicurezza`, `DevOps`), ognuno con il proprio system prompt e il proprio modello ottimale. *(Fatto: pool definito in core/config.py)*
- [ ] Implementare la **Memoria Condivisa di Sessione** (`session_store`: dizionario Python in RAM) in cui ogni agente scrive i propri risultati e legge quelli degli altri agenti completati.
- [x] Implementare la **fase di Orchestrazione Dinamica**: Flash riceve il prompt e risponde con un JSON strutturato:
  ```json
  {
    "required_agents": ["developer", "security_auditor"],
    "reasoning": "Richiede codice con autenticazione"
  }
  ```
  *(Fatto: implementato in core/classifier.py, che funge ora da Project Manager).*
- [ ] Il router parserizza il JSON e avvia **dinamicamente solo gli agenti richiesti** tramite `asyncio.gather`. *(Parzialmente fatto: router.py estrae gli agenti dal JSON ma per ora esegue in ReAct solo il primary_agent in attesa dello sviluppo parallelo).*
- [ ] Implementare la **Delega Ricorsiva**: ogni agente, dopo aver analizzato il proprio task, può emettere una nuova richiesta di delega verso un agente specializzato. Il router gestisce lo stack di chiamate ricorsive.
- [ ] Implementare il **limite di profondità** (`max_depth = 3`) per prevenire cicli infiniti nel DAG.
- [ ] Il Sintetizzatore (sviluppato nello Step 6) legge la `session_store` al completamento di tutti gli agenti e unisce i risultati in un'unica risposta finale coerente.
- [ ] Testing con prompt complessi multi-dominio (es. "Crea un endpoint REST con autenticazione JWT e scrivi i test unitari").


Problemi:
Ci sono agenti che scrivono e leggono in parallelo (asyncio.gather) sullo stesso dizionario Python. Con la delega ricorsiva, un agente che lancia un sotto-agente che a sua volta scrive sulla stessa store mentre il padre sta leggendo crea race condition sottili. asyncio è single-threaded quindi tecnicamente sicuro, ma un agente che await-a una sub-chiamata può lasciar eseguire un altro coroutine nel mezzo. Serve un lock esplicito o strutturare la store come append-only con ownership per agente.


### Step 8: 💰 FinOps — Ottimizzazione e Controllo dei Costi
> Applicare i principi FinOps al consumo delle API LLM: visibilità totale, uso del modello più economico sufficiente, limiti di budget e azzeramento degli sprechi.

**Principio 1 — Visibility (Visibilità)**
- [ ] Leggere il campo `usage` (token `prompt` + `completion`) da ogni risposta dell'API e registrarlo nella `session_store`.
- [ ] Mantenere un contatore aggregato per sessione: `{modello: {prompt_tokens, completion_tokens, costo_stimato}}`.
- [ ] Esporre un endpoint interno `GET /stats` nel router che restituisce un **report Markdown** leggibile direttamente con `curl localhost:8080/stats` dal terminale, o interrogabile dall'interno della chat di OpenCode Go.

**Principio 2 — Right-sizing (Agent-Based Routing)**
- [x] Documentare formalmente il routing basato sugli agenti (Orchestratore/General Chat → Flash, Developer → Pro, Security → GLM-5.1, Documenter → Mimo) come policy FinOps. L'Orchestratore sceglie il modello più economico idoneo alla task.
- [ ] Verificare periodicamente che la distribuzione reale delle chiamate agli agenti rispecchi le aspettative (es. se il 90% delle richieste va al Developer Pro, l'Orchestratore potrebbe essere troppo permissivo).

**Principio 3 — Budgeting & Alerts (Tetto di Spesa)**
- [ ] Definire un `SESSION_TOKEN_BUDGET` configurabile (es. 100.000 token per sessione).
- [ ] Quando il budget residuo scende sotto il 20%, il router forza automaticamente il **downgrade** di tutte le richieste successive al modello Flash, indipendentemente dalla classificazione.
- [ ] Notificare l'utente via streaming con un messaggio in chat (es. `⚠️ Budget quasi esaurito. Modalità risparmio attivata.`).

**Principio 4 — Waste Elimination (Cache)**
- [ ] Implementare una **cache in RAM** delle ultime N risposte (es. N=50), indicizzata tramite **hash esatto** del prompt normalizzato (lowercase, spazi collassati): O(1), zero dipendenze aggiuntive.
- [ ] Prima di ogni chiamata API, calcolare l'hash del prompt e verificare se esiste già in cache.
- [ ] Se la cache viene colpita, restituire la risposta salvata direttamente senza consumare token.
- [ ] (Futuro) Se si volesse catturare anche prompt riformulati, aggiungere un layer di embedding semantico come fallback secondario senza riscrivere la logica principale.

**Principio 5 — Reporting (Log Persistente)**
- [ ] Scrivere su disco un file di log giornaliero in formato `.jsonl` (`~/.opencode-router/usage_YYYY-MM-DD.jsonl`) con ogni chiamata: timestamp, modello, token usati, costo stimato, tier assegnato.
- [ ] (Opzionale) Creare un semplice script Python `usage_report.py` che legge i log e stampa un riepilogo settimanale di spesa e distribuzione dei tier.


## Step 9
Ho 2 possibilità per lo step 9, molto probabilmente usaerò il cloud native showcase.

### Enterprise Over-Engineering (Cloud Native Showcase)
> ⚠️ **Attenzione:** Questo step è deliberatamente sovra-ingegnerizzato. L'obiettivo non è l'efficienza per un proxy locale, ma creare un **Portfolio Project** che dimostri padronanza assoluta dei paradigmi Cloud Native, architetture a microservizi e sistemi distribuiti.

**Stack Tecnologico Selezionato:**
- **Framework Microservizi:** FastAPI (Mantiene coerenza con il codice attuale e supporta async).
- **Message Broker (Event-Driven):** Redis Pub/Sub (Leggero e riutilizza lo stesso datastore dello stato).
- **State Management:** Redis (Sostituisce la memoria condivisa in RAM per permettere lo scale-out).
- **Consenso Distribuito:** etcd (Per l'elezione del Leader Orchestrator, sfruttando Raft).
- **Kubernetes Locale:** K3s / K3d (Cluster K8s ultra-leggero).
- **Deployment / IaC:** Helm (Package manager standard per K8s).


Da rivedere un attimo: Leader election con Raft ha senso con N≥3 nodi reali; su un singolo laptop con K3d è narcisismo puro. Potresti considerare di usarlo come showcase documentato ma non funzionale, o sostituirlo con un'architettura HA su 3 container Docker che sia effettivamente dimostrabile.


**Piano Operativo:**
- [ ] **Microservizi con FastAPI:** Dividere il router in microservizi indipendenti (es. `API Gateway`, `Classification Service`, `Agent Worker`). Containerizzare con Docker.
- [ ] **Event-Driven con Redis Pub/Sub:** Sostituire le chiamate `asyncio` dirette con un'architettura ad eventi. L'orchestratore pubblica su canali Redis, i worker consumano.
- [ ] **State Management su Redis:** Salvare lo stato della conversazione e i risultati parziali degli agenti su Redis, garantendo statelessness ai worker.
- [ ] **Leader Election con etcd:** Implementare l'elezione di un master tra i nodi dell'API Gateway per garantire High Availability.
- [ ] **Deployment su K3d tramite Helm:** Creare i chart Helm per fare il deploy dell'intera infrastruttura sul cluster Kubernetes locale.



### Hardened Production Router
Questa è una soluzione più "realistica" e non fatta per "flexare" certe doti.

Pilastro 1 — Sandboxed Tool Execution (il vero problema da risolvere)

Ogni chiamata bash va eseguita in un namespace Linux isolato usa-e-getta via **bubblewrap** (`bwrap`), lo stesso sandboxing che usa Flatpak e Podman internamente. Zero daemon, zero overhead, puro kernel Linux.

Aggiungi un profilo **seccomp-bpf** per bloccare le syscall pericolose a livello kernel. La whitelist minima include `read`, `write`, `open`, `execve`, `fork`, `wait`, `exit` — tutto il resto viene bloccato con `EPERM`:

```python
# Genera il profilo con seccomp-tools e passalo come file descriptor:
# bwrap --seccomp 3 3< /etc/opencode-router/seccomp-bash.bpf ...
```

Questo trasforma `shell=True` da vulnerabilità critica a rischio residuo minimo. Un LLM che prova `rm -rf /` trova solo `/workspace`.

---

Pilastro 2 — Deployment con systemd Hardened
`systemd` ha primitive di sicurezza più granulari di K3d per un servizio locale, senza overhead.

---

Pilastro 3 — Ottimizzazione Performance Concreta

**Tre cambi misurabili, zero sovra-ingegneria:**

```python
# 1. uvloop: event loop C, ~2x più veloce dell'asyncio default
import uvloop
uvloop.install()  # una sola riga prima di uvicorn.run()

# 2. orjson: serializzazione JSON ~3-5x più veloce di json standard
import orjson
# Sostituisce json.dumps() → orjson.dumps().decode()
# Critico nell'agent loop che serializza/deserializza ad ogni step

# 3. httpx AsyncClient a livello app, NON per-request (problema attuale)
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(
        timeout=60.0,
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
    )
    yield
    await app.state.http_client.aclose()

app = FastAPI(lifespan=lifespan)
```

Il problema del client ricreato ad ogni request è invisibile con 1 utente, ma crea overhead reale nell'agent loop dove ogni step apre e chiude una connessione TLS verso l'upstream.

---

Pilastro 4 — Observability Reale (senza Prometheus theater)

Dato che hai già progettato il log `.jsonl` nello Step 8, estendilo con **OpenTelemetry** in modalità locale: trace ogni agent loop come uno span, con i tool call come sotto-span. Costa un'unica dipendenza (`opentelemetry-sdk`) e ti dà visibilità immediata su dove il tempo viene speso, esportabile su Jaeger locale o su file.

---

## Confronto diretto

| | Step 9 | Step 9 Alternativo |
|---|---|---|
| **Problema risolto** | Scale-out che non hai | Vulnerabilità reali che hai |
| **Complessità** | etcd + K3d + Helm + Redis | bwrap + systemd + uvloop |
| **Sicurezza** | K8s RBAC (coordinata, non sandboxing) | seccomp + namespace isolation per ogni tool call |
