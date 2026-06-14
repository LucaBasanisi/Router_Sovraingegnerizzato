# Router_Sovraingegnerizzato (OpenCode Go Agentic Proxy Router)
Router costruito per Opencode Go (https://opencode.ai/it/go) che permette l'utilizzo multi agentico.

## Cos'è
Un Proxy Router intelligente e "Man-in-the-Middle" per OpenCode Go, capace di trasformare una normale sessione di chat LLM in un vero e proprio sistema multi-agente autonomo. Questo proxy si inserisce tra il client locale e l'API LLM (es. DeepSeek, Mimo), intercettando le richieste, classificando dinamicamente la complessità del task e permettendo all'intelligenza artificiale di agire in modo proattivo sul sistema locale dell'utente.

## Come Funziona
Il router non è un semplice pass-through:
1. **Classificazione Dinamica:** Interpreta l'intento dell'utente e decide se assegnare un task a un modello rapido (EASY), a uno specialista del codice (MEDIUM) o a un modello di ragionamento complesso (HARD).
2. **Ciclo Agentico (ReAct):** Per query complesse, l'LLM non si limita a rispondere, ma esegue un loop logico decidendo autonomamente di invocare comandi bash locali per raccogliere contesto e applicare modifiche (Tool Calling).
3. **Stateless CWD Injection:** L'ambiente del terminale dell'utente viene iniettato elegantemente nelle richieste, rendendo ogni chiamata stateless e isolata.
4. **Streaming SSE Trasparente:** L'utente percepisce un'esperienza di chat continua (ricevendo notifiche testuali in tempo reale come `> 🔧 Agente esegue: ls -la`), superando i limiti di timeout dei classici client HTTP senza spezzare l'interfaccia utente originale.

## Casi d'Uso Principali
* **Assistente Locale Proattivo:** Puoi chiedere "Analizza i file in questa directory e dimmi perché il test fallisce". L'agente leggerà i file, eseguirà i comandi necessari, e proporrà (o applicherà) la soluzione.
* **Ottimizzazione Costi / FinOps (Dynamic Routing):** Risparmia sui costi API dirottando in automatico query semplici o chiacchiere (es. "come faccio un ciclo for in Python") su modelli più veloci ed economici, riservando la potenza di calcolo solo per problemi complessi.
* **Refactoring Autonomo Su Larga Scala:** Grazie al ciclo agentico (Agent Loop), l'LLM può muoversi all'interno della cartella di lavoro per esplorare la struttura del codice e modificare svariati file per sistemare un bug in totale autonomia.

> 📄 **Documentazione Tecnica:** Per dettagli sulle decisioni architetturali complesse del progetto (es. Finto Streaming SSE, Injection della cartella in ottica Cloud Native), visita la cartella `doc/`.
