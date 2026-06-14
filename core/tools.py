"""
Modulo dei Tool (Strumenti).
Questo file contiene l'implementazione in Python di tutte le abilità (tools)
che il modello LLM può richiamare. Definisce anche lo schema JSON dei tool
che verrà inviato all'API di completamento.
"""
import os
import subprocess

def execute_bash_command(cmd: str, cwd: str) -> str:
    """
    Esegue un comando bash arbitrario nel terminale dell'utente locale.
    Questo tool è confinato nella directory di lavoro (cwd) dell'utente per sicurezza.
    Ha un timeout di 30 secondi per evitare comandi appesi (es. server web).
    """
    try:
        # subprocess.run lancia il processo in una sub-shell
        res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=30)
        # Tronchiamo l'output a 4000 caratteri per evitare di saturare la context window dell'LLM
        return f"EXIT CODE: {res.returncode}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"[:4000]
    except Exception as e:
        return f"Error executing: {str(e)}"

def read_file_tool(path: str, cwd: str) -> str:
    """
    Legge il contenuto di un file nel filesystem dell'utente locale.
    Supporta percorsi relativi e assoluti.
    """
    # Risolviamo il path assoluto se viene fornito un path relativo
    full_path = os.path.join(cwd, path) if not os.path.isabs(path) else path
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Tronchiamo l'output a 15000 caratteri e segnaliamo il taglio, se necessario
            return content[:15000] + ("\n[... TRUNCATED ...]" if len(content) > 15000 else "")
    except Exception as e:
        return f"Error reading file {path}: {str(e)}"

def write_file_tool(path: str, content: str, cwd: str) -> str:
    """
    Crea o sovrascrive un file nel filesystem locale inserendo il testo formattato.
    Crea automaticamente anche le cartelle padre se non esistono.
    """
    full_path = os.path.join(cwd, path) if not os.path.isabs(path) else path
    try:
        # Crea l'albero delle directory (come mkdir -p)
        os.makedirs(os.path.dirname(os.path.abspath(full_path)), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File {path} written successfully."
    except Exception as e:
        return f"Error writing file {path}: {str(e)}"

def list_dir_tool(path: str, cwd: str) -> str:
    """
    Elenca i file presenti all'interno di una determinata cartella.
    """
    full_path = os.path.join(cwd, path) if not os.path.isabs(path) else path
    try:
        # Ritorna una lista testuale dei contenuti
        return "\n".join(os.listdir(full_path))
    except Exception as e:
        return f"Error listing directory {path}: {str(e)}"

# Array JSON contenente la definizione strutturata di ogni tool, 
# indispensabile per l'invio all'API compatibile con OpenAI/Deepseek.
TOOLS_DEF = [
    {
        "type": "function",
        "function": {
            "name": "run_bash_command",
            # Il prompt engineering integrato nella descrizione proibisce manipolazioni dei file in bash
            "description": "Esegue un comando bash. Usa questo tool SOLO per eseguire script, test, compilazioni, git o processi di sistema. NON USARLO MAI per creare, leggere o modificare file: usa esclusivamente i tool appositi (read_file, write_file).",
            "parameters": {"type": "object", "properties": {"cmd": {"type": "string", "description": "Comando bash"}}, "required": ["cmd"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Legge il contenuto di un file.",
            "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Percorso del file (es. src/main.py)"}}, "required": ["path"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Scrive e sovrascrive un file con il nuovo contenuto.",
            "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Percorso del file"}, "content": {"type": "string", "description": "Contenuto del file"}}, "required": ["path", "content"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "Elenca i file in una directory.",
            "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Percorso ('./' per la corrente)."}}, "required": ["path"]}
        }
    }
]
