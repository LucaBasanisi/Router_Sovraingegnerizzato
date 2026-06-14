# Criticità da affrontare


## **Bare `except:` clausole.**
In `classifier.py` e `router.py` ci sono blocchi `except:` nudi che catturano anche `KeyboardInterrupt` e `SystemExit`. La best practice è `except Exception:`.

## **L'euristica di pre-classificazione ha falsi positivi evidenti.**
La parola `"tool"` in qualsiasi contesto forza sempre `HARD`. Una domanda come *"cos'è il pattern Strategy nel design orientato a oggetti?"* — che contiene `"design pattern"` — viene instradata al modello più costoso inutilmente.

## **Nessun `data: [DONE]\n\n` nel path EASY/MEDIUM in caso di errore.**
Nel `stream_generator` del proxy passivo, in caso di eccezione viene emesso solo `data: {"error": ...}` senza il terminatore. Questo lascia la porta aperta allo stesso retry storm documentato nel troubleshooting log.

## **La `loop_messages` cresce senza limite.**
Nel ciclo agentico, ogni tool call aggiunge messaggi alla cronologia. Con 15 iterazioni e tool output pesanti, si possono raggiungere silenziosamente i token limit dell'LLM senza gestione esplicita.


