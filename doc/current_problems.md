# Criticità da affrontare


## **Bare `except:` clausole.**
In `classifier.py` e `router.py` ci sono blocchi `except:` nudi che catturano anche `KeyboardInterrupt` e `SystemExit`. La best practice è `except Exception:`.

## **L'euristica di pre-classificazione ha falsi positivi evidenti.**
La parola `"tool"` in qualsiasi contesto forza sempre `HARD`. Una domanda come *"cos'è il pattern Strategy nel design orientato a oggetti?"* — che contiene `"design pattern"` — viene instradata al modello più costoso inutilmente.

## **Nessun `data: [DONE]\n\n` nel path EASY/MEDIUM in caso di errore.**
Nel `stream_generator` del proxy passivo, in caso di eccezione viene emesso solo `data: {"error": ...}` senza il terminatore. Questo lascia la porta aperta allo stesso retry storm documentato nel troubleshooting log.

## **La `loop_messages` cresce senza limite.**
Nel ciclo agentico, ogni tool call aggiunge messaggi alla cronologia. Con 15 iterazioni e tool output pesanti, si possono raggiungere silenziosamente i token limit dell'LLM senza gestione esplicita.

## Mancanza di diagrammi architetturali
La documentazione spiega bene il "perché" delle scelte, ma mancano rappresentazioni visive:
- **Diagramma di flusso**: ciclo completo di una richiesta (Client → router.py → classifier → agente → tool → risposta)
- **Sequence diagram**: interazione temporale tra i componenti durante il loop agentico ReAct
- **Diagramma di componenti**: relazione tra `router.py` e i moduli `core/` (config, classifier, tools, agent)

## Guida di setup rapido assente
Il README non spiega come avviare il sistema. `start.sh` esiste ma non è documentato. Manca:
- Dipendenze richieste (Python, pip, pacchetti)
- Istruzioni per il wrapper bash `~/.opencode/bin/opencode`
- Verifica post-installazione

## Nessun riferimento API interno
Manca documentazione su:
- Endpoint esposti (es. `POST /v1/chat/completions`)
- Formati di payload attesi/inviati tra il router e i moduli `core/`
- Struttura del `session_store` (previsto per Step 7)


