# API Intercepts & Payload Manipulation

OpenCode Go Router si inserisce "man in the middle" (MITM) tra il client locale e il fornitore LLM remoto (es. Deepseek via `opencode.ai`). Sebbene il proxy esponga un'interfaccia apparentemente identica allo standard OpenAI (`/v1/chat/completions`), sotto il cofano compie manipolazioni aggressive sia sui payload in ingresso (richiesta HTTP) sia su quelli in uscita (flusso SSE).

Questo documento serve a tracciare **esattamente** quali campi vengono alterati, rimossi o forgiati dal nostro router. È vitale nel caso in cui si voglia usare questo Proxy non solo con OpenCode Go, ma con altre CLI o plugin IDE.

---

## 1. Intercettazione Headers (Authorization Hack)
Poiché l'API REST di natura è "Stateless", il router non sa in quale cartella il client si trovi. 
Il client CLI è stato "hackerato" tramite script bash (`~/.opencode/bin/opencode`) per iniettare il percorso locale nell'Header Authorization.

* **Payload in ingresso (Dal Client):**
  `Authorization: Bearer dummy|/home/user/my_project`
* **Azione del Router:**
  Separa la stringa tramite la pipe `|`. Estrae `/home/user/my_project` mettendola in memoria RAM come `client_cwd` per l'esecuzione dei tools.
* **Payload in uscita (Verso Provider LLM):**
  L'header viene sovrascritto con la *vera* API Key letta segretamente dal disco (`~/.local/share/opencode/auth.json`), nascosta per sempre al client:
  `Authorization: Bearer ds-xxxxxx`

---

## 2. Manipolazione Body JSON (Whitelist e Sanitizzazione)
I client CLI spesso inviano parametri aggiuntivi non strettamente standard (es. formattazioni, `stream_options`, ecc.) che causano errori `400 Bad Request` se affiancati all'oggetto `tools`. 
Quando il Router valuta la query come `HARD` ed evoca il Loop Agentico, distrugge il payload originale per ricostruirne uno sicuro.

* **Filtro Whitelist:** 
  Il router conserva unicamente: `["model", "temperature", "top_p", "max_tokens"]`.
* **Disattivazione Forzata Streaming:** 
  Anche se il Client richiede `stream: true`, il Router sovrascrive forzatamente `payload["stream"] = False` verso il Provider. Questo permette al Router di ricevere le chiamate ai Function Tools in blocco JSON intero, prevenendo la follia di parsare stringhe di testo frammentate (delta).
* **Iniezione Dinamica dei Tools:** 
  Il Router aggiunge l'array `TOOLS_DEF` solo nel layer "Agentico" (Tier HARD). Ai layer inferiori ("EASY/MEDIUM") non viene passato per risparmiare pesantemente sui token.

---

## 3. Forgiatura del Server-Sent Events (SSE)
Per ingannare il Client locale, che ha richiesto una connessione in streaming e potrebbe chiudere per timeout (es. 60s di inattività), il Router falsifica l'intero protocollo SSE.

**Flusso Emulato:**
1. **Notifiche Tool (Fake Chunk):** 
   Mentre l'LLM pensa o mentre uno script bash impiega 10 secondi ad eseguire, il router emette dei chunk generati localmente:
   ```json
   data: {"id": "tool", "model": "deepseek-v4-pro", "choices": [{"delta": {"content": "\n> 💻 **Bash:** `npm install`\n\n"}}]}
   ```
2. **Scrittura Risposta Finale (Simulata):**
   Quando l'LLM sputa fuori l'intera risposta finale in blocco JSON, il Router la spezzetta in frammenti di 50 caratteri. I frammenti vengono sparati in rapida successione sullo stream (con `yield` asincrono), creando un bellissimo effetto "macchina da scrivere" nel terminale del Client, garantendo compatibilità con le animazioni di rendering di qualsiasi IDE.
3. **Gestione del Retry Storm (Bug Limit):**
   Qualora si superasse il numero massimo di 15 iterazioni consentite senza che l'LLM formuli una risposta finale, il Router genera un errore formattato:
   `⚠️ Limite di sicurezza raggiunto`
   Seguito *immediatamente* dal pacchetto di terminazione obbligatorio:
   `data: [DONE]\n\n`
   Senza questo pacchetto di terminazione formale, i client moderni non riconoscono l'intenzionalità della chiusura e lanciano immediatamente tentativi "Retry", causando loop infiniti chiamati Retry Storms.

---

## Conclusioni
Tutte le manipolazioni elencate operano unicamente sul tier `HARD`. Quando il Router classifica una richiesta come `EASY` o `MEDIUM`, funge da purissimo reverse-proxy specchio ("Pass-through"), limitandosi a cambiare solo il nome del parametro `model` e inoltrando pacchetti e stream al 100% inalterati e passivi.
