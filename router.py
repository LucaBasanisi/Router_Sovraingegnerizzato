import json
import os
import httpx
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("opencode-router")

app = FastAPI(title="OpenCode Go 3-Tier Dynamic Router")

# Configuration
OPENCODE_AUTH_PATH = os.path.expanduser("~/.local/share/opencode/auth.json")
BASE_URL = "https://opencode.ai/zen/go/v1"

# Model Mapping
CHAT_MODEL = "deepseek-v4-flash"      # Tier 1 (Free generalist)
CODE_MODEL = "mimo-v2.5"              # Tier 2 (Free code specialist)
REASONING_MODEL = "deepseek-v4-pro"   # Tier 3 (Paid reasoning model)

CLASSIFIER_MODEL = "deepseek-v4-flash"

def get_api_key():
    try:
        with open(OPENCODE_AUTH_PATH, "r") as f:
            data = json.load(f)
            return data["opencode-go"]["key"]
    except Exception as e:
        logger.error(f"Failed to read API key from {OPENCODE_AUTH_PATH}: {e}")
        raise RuntimeError("API Key not found or invalid.")

# Load API key once at startup
try:
    API_KEY = get_api_key()
    logger.info("API Key loaded successfully.")
except Exception as e:
    API_KEY = None
    logger.warning("Could not load API Key at startup. It will be retried on requests.")

def pre_classify(user_prompt: str) -> str | None:
    """
    Performs a fast local check to avoid network classification call for simple queries.
    Returns 'EASY', 'HARD' if matches heuristics, else None.
    """
    cleaned = user_prompt.strip().lower()
    
    # 1. Extremely short queries
    if len(cleaned) < 15:
        return "EASY"
        
    # 2. Simple common keywords/greetings/navigation commands
    greetings = {"ciao", "hello", "hi", "hey", "help", "clear", "exit", "grazie", "thanks", "ok", "okay"}
    if cleaned in greetings:
        return "EASY"
        
    # 3. Hard technical keywords
    hard_keywords = ["implementata dal punto di vista tecnico", "architecture", "architettura", "memory leak", "race condition", "under the hood", "dietro le quinte", "system design", "progettazione", "design pattern"]
    for kw in hard_keywords:
        if kw in cleaned:
            return "HARD"
            
    return None

async def classify_prompt(user_prompt: str, api_key: str) -> str:
    """
    Classifies the prompt complexity using the free Flash model.
    Returns 'EASY', 'MEDIUM', or 'HARD'.
    """
    # Run pre-classification heuristics first
    preset = pre_classify(user_prompt)
    if preset:
        logger.info(f"Pre-classification triggered: {preset}")
        return preset

    system_instruction = (
        "You are an AI router. Analyze the following user query for a software development coding assistant. "
        "Classify the query into one of three complexity tiers: 'EASY', 'MEDIUM', or 'HARD'.\n\n"
        "Criteria for EASY:\n"
        "- Casual conversation, greetings, simple thanks\n"
        "- Trivial programming definitions (e.g. 'what is a string', 'how to write a for loop')\n"
        "- Shell/terminal commands, basic git usage, environment questions\n"
        "- Very simple edits or formatting tasks\n\n"
        "Criteria for MEDIUM:\n"
        "- Writing standard boilerplate, functions, classes, or unit tests\n"
        "- Explaining or refactoring single snippets of code\n"
        "- Translating a small function from one language to another\n"
        "- General coding tasks that do not involve complex logic\n\n"
        "Criteria for HARD:\n"
        "- Deep technical questions about system architecture, internal mechanics, framework implementations or design patterns (e.g. 'How is X implemented under the hood?', 'come viene implementata dal punto di vista tecnico...')\n"
        "- Finding subtle bugs, memory leaks, or race conditions in complex code\n"
        "- Architectural design, multi-file changes, designing database schemas\n"
        "- Writing complex algorithms, mathematical logic, or highly optimized code\n"
        "- Large-scale refactoring, security audits, or complex system integrations\n\n"
        "Reply with exactly 'EASY', 'MEDIUM', or 'HARD'. Do not output any other text."
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": CLASSIFIER_MODEL,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": f"Query: {user_prompt}"}
                ],
                "temperature": 0.0,
                "max_tokens": 5
            }
            
            response = await client.post(f"{BASE_URL}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            classification = result["choices"][0]["message"]["content"].strip().upper()
            
            if "HARD" in classification:
                return "HARD"
            elif "MEDIUM" in classification:
                return "MEDIUM"
            return "EASY"
            
    except Exception as e:
        logger.error(f"Error during prompt classification: {e}. Defaulting to HARD for safety.")
        return "HARD"

def extract_text_content(content) -> str:
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            elif isinstance(part, str):
                text_parts.append(part)
        return "\n".join(text_parts)
    return ""

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    global API_KEY
    if not API_KEY:
        try:
            API_KEY = get_api_key()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"API Key initialization failed: {str(e)}")

    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="Messages list is empty")

    # Extract the last user message to analyze complexity
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content_val = msg.get("content", "")
            last_user_msg = extract_text_content(content_val)
            break

    # Classify complexity
    if last_user_msg:
        decision = await classify_prompt(last_user_msg, API_KEY)
    else:
        decision = "EASY"

    # Map decision to model
    if decision == "HARD":
        chosen_model = REASONING_MODEL
    elif decision == "MEDIUM":
        chosen_model = CODE_MODEL
    else:
        chosen_model = CHAT_MODEL

    logger.info(f"Prompt: '{last_user_msg[:60]}...' -> Tier: {decision} -> Routing to: {chosen_model}")

    # Prepare forwarding payload
    body["model"] = chosen_model

    # Forwarding headers
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # Setup connection to OpenCode Go API
    client = httpx.AsyncClient(timeout=60.0)

    # Check if streaming is requested
    is_stream = body.get("stream", False)

    if is_stream:
        async def stream_generator():
            try:
                # Forward request with stream
                async with client.stream("POST", f"{BASE_URL}/chat/completions", json=body, headers=headers) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_raw():
                        yield chunk
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield json.dumps({"error": {"message": f"Proxy streaming error: {str(e)}"}}).encode("utf-8")
            finally:
                await client.aclose()

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        try:
            resp = await client.post(f"{BASE_URL}/chat/completions", json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise HTTPException(status_code=500, detail=f"Proxy request failed: {str(e)}")
        finally:
            await client.aclose()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
