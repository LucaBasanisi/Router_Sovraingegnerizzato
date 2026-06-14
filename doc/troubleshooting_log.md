# Registro Errori e Troubleshooting

Questo file funge da "memoria storica" del progetto. Qui documentiamo gli errori insidiosi incontrati durante lo sviluppo e le relative soluzioni adottate, così da non ripetere gli stessi sbagli quando la complessità del sistema aumenterà (in particolare verso l'architettura a microservizi).

---

## 1. `[Errno 98] Address already in use` all'avvio del Router
**Sintomo:** 
Avviando `./start.sh` viene restituito l'errore:
`error while attempting to bind on address ('127.0.0.1', 8080): [errno 98] address already in use`

**Causa:**
Un'istanza precedente del router (il processo Python con Uvicorn) è andata in background o non si è chiusa correttamente, mantenendo occupata la porta `8080`.

**Soluzione Adottata:**
Occorre trovare l'ID del processo (PID) che occupa la porta e forzarne la chiusura.
```bash
lsof -i :8080
kill -9 <PID>
```

---

## 2. API 400 Bad Request & "Unterminated string in JSON"
**Sintomo:**
Durante l'utilizzo di una query agentica ("HARD"), il terminale di OpenCode Go è crashato vomitando un JSON malformato nella chat con il messaggio:
`JSON parsing failed: Text: {"choices":[{"delta":{"content": "\n\n❌ Errore proxy LLM: Client error '400 Bad Request'... Unterminated string in JSON at position 145`

**Causa:**
Questo è stato un "doppio bug" interessante:
1. **(Il Bug HTTP Originale)** L'API LLM ha rifiutato la nostra richiesta proxy (400 Bad Request). Il motivo è che la CLI OpenCode originale invia parametri extra nel payload HTTP (es. `stream_options`, formattazioni custom). Aggiungendo l'array `tools` alla richiesta, i server OpenAI-like andavano in conflitto sulle flag contrastanti e rigettavano il payload.
2. **(Il Bug Visivo)** Il nostro `router.py` ha catturato l'eccezione, ma ha cercato di passarla all'utente via stream (SSE) stampandola a crudo in un formatter string f-string. L'eccezione conteneva dei ritorni a capo (`\n`) che hanno spezzato le virgolette del JSON finale, facendo impazzire il parser del client OpenCode ("Unterminated string").

**Soluzione Adottata:**
1. **Sanitizzazione del Payload:** In `router.py` è stata implementata una whitelist delle chiavi sicure (`safe_keys = ["model", "temperature", "top_p", "max_tokens"]`). Quando andiamo in "Agent Mode", cestiniamo qualsiasi altro parametro inutile o pericoloso inviato dal client.
2. **Escape JSON:** Il frammento JSON del finto stream di errore è stato wrappato in `json.dumps(chunk)` per fare l'encoding automatico e sicuro di tutti i caratteri speciali.

---

## 3. Il "Loop da 39 Iterazioni" (Retry Storm su Disconnect)
**Sintomo:**
L'Agente era stato limitato a un massimo di `max_steps = 5` iterazioni nel codice tramite un ciclo for. Tuttavia, durante un test in cui il modello ha deliberatamente speso tutte e 5 le iterazioni senza trovare la soluzione (il test per fargli ottenere "7"), l'utente ha riferito che il loop ha girato ben 39 volte!

**Causa:**
Un sottile bug nel protocollo Server-Sent Events (SSE). Quando il nostro proxy esauriva le 5 iterazioni del ciclo for asincrono, la funzione terminava brutalmente chiudendo la connessione HTTP `finally: await client.aclose()`. 
Dato che il proxy *non* ha mai inviato la stringa finale di chiusura stream `data: [DONE]\n\n`, il client locale (OpenCode Go) ha interpretato la chiusura della connessione come un "Errore di Rete" e ha attivato automaticamente la sua logica di auto-retry (riprovando in automatico a fare la richiesta). Siccome riprovava inviando tutta la nuova cronologia acquisita, l'agente rifaceva altre 5 iterazioni, si sganciava di nuovo, il client riprovava, creando una vera e propria **Retry Storm**.

**Soluzione Adottata:**
È stato aggiunto un costrutto `else:` alla fine del ciclo for in Python. Se il ciclo completa tutte le 5 iterazioni senza interruzioni (ovvero, l'LLM non ha mai fornito la risposta finale), il router invia un esplicito finto chunk SSE con l'avviso "⚠️ Limite di sicurezza raggiunto", seguito dall'obbligatorio pacchetto di terminazione `data: [DONE]\n\n` prima di disconnettersi. In questo modo il client capisce che la trasmissione è finita intenzionalmente e ferma i retry.
