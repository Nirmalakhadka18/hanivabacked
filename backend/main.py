# chat_to_pay_fastapi.py
import os
import json
import uuid
from fastapi import FastAPI, HTTPException, Request, Query
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx
import requests

load_dotenv()

app = FastAPI(title="Chat-to-Pay Backend (FastAPI) - Full")

# --- Env / config ---
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
MESHJS_SERVICE_URL = os.getenv('MESHJS_SERVICE_URL', 'http://localhost:3001')
WEB3_STORAGE_TOKEN = os.getenv('WEB3_STORAGE_TOKEN', '')
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', '')
KOIOS_BASE = os.getenv('KOIOS_BASE', 'https://api.koios.rest/api/v0')
BLOCKFROST_KEY = os.getenv('BLOCKFROST_KEY', None)

# --- Pydantic models ---
class IntentRequest(BaseModel):
    message: str
    user_id: str | None = None

class IntentParsed(BaseModel):
    action: str
    amount: float | None = None
    to: str | None = None

class SendTxRequest(BaseModel):
    unsigned_tx: str | None = None
    signed_tx: str | None = None
    from_wallet: str | None = None
    to_address: str | None = None
    amount_lovelace: int | None = None
    metadata: dict | None = None

# ============ Intent endpoint (OpenAI -> JSON schema) ============
OPENAI_INTENT_PROMPT = """You are an assistant that extracts a single JSON action from user messages.
Only respond with valid JSON following the schema:
{ "action": "send_payment" | "check_balance" | "receive" | "unknown", "amount": number|null, "to": string|null }
Examples:
- "Send 200 to Nirmala" -> { "action": "send_payment", "amount": 200, "to": "Nirmala" }
- "What's my balance?" -> { "action": "check_balance", "amount": null, "to": null }
If you cannot detect intent, return { "action":"unknown", "amount": null, "to": null }.
"""

def call_openai_for_intent(message: str) -> dict:
    # If no API key, fallback to naive parser
    if not OPENAI_API_KEY:
        return simple_intent_parser(message)
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4o-mini",
        "prompt": OPENAI_INTENT_PROMPT + "\nUser: " + message + "\nJSON:",
        "max_tokens": 150,
        "temperature": 0,
        "top_p": 1
    }
    try:
        r = requests.post("https://api.openai.com/v1/completions", headers=headers, json=payload, timeout=10)
        if r.status_code != 200:
            return simple_intent_parser(message)
        text = r.json().get('choices', [{}])[0].get('text', '') or r.json().get('choices', [{}])[0].get('message', {}).get('content', '')
        # attempt to extract JSON from text
        import re
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            j = json.loads(m.group(0))
            return j
        return simple_intent_parser(message)
    except Exception as e:
        print("OpenAI call failed:", e)
        return simple_intent_parser(message)

def simple_intent_parser(text: str) -> dict:
    textl = text.lower()
    if any(w in textl for w in ['send', 'pay', 'transfer']):
        import re
        m = re.search(r'\b(\d+[,.]?\d*)\b', textl)
        amount = None
        if m:
            try:
                amount = float(m.group(1).replace(',', ''))
            except: amount = None
        parts = text.strip().split()
        to = parts[-1] if len(parts) > 1 else None
        return {"action":"send_payment", "amount": amount, "to": to}
    if 'balance' in textl:
        return {"action":"check_balance", "amount": None, "to": None}
    return {"action":"unknown", "amount": None, "to": None}

@app.post('/intent')
async def intent_endpoint(req: IntentRequest):
    parsed = call_openai_for_intent(req.message)
    return {"ok": True, "intent": parsed}

# ============ Build unsigned tx (delegates to MeshJS microservice) ============
@app.post('/create-unsigned-tx')
async def create_unsigned_tx(body: SendTxRequest):
    payload = {
        'to_address': body.to_address,
        'amount_lovelace': body.amount_lovelace,
        'metadata': body.metadata or {}
    }
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{MESHJS_SERVICE_URL}/build-unsigned-tx", json=payload, timeout=30.0)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as he:
            raise HTTPException(status_code=500, detail=f"MeshJS build failed: {he.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# ============ Submit signed tx ============
@app.post('/submit-signed-tx')
async def submit_signed_tx(body: SendTxRequest):
    if not body.signed_tx:
        raise HTTPException(status_code=400, detail='signed_tx required')
    payload = body.dict()
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{MESHJS_SERVICE_URL}/submit-tx", json=payload, timeout=30.0)
            r.raise_for_status()
            tx_res = r.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"MeshJS submit failed: {e}")

    # Create receipt and pin to IPFS (web3.storage)
    receipt = {
        'tx_id': tx_res.get('txid') or tx_res.get('tx_id') or tx_res.get('txHash'),
        'from': body.from_wallet,
        'to': body.to_address,
        'amount_lovelace': body.amount_lovelace,
        'metadata': body.metadata or {},
        'receipt_id': str(uuid.uuid4())
    }

    if WEB3_STORAGE_TOKEN:
        try:
            headers = { 'Authorization': f'Bearer {WEB3_STORAGE_TOKEN}', 'Content-Type': 'application/json' }
            resp = requests.post('https://api.web3.storage/upload', headers=headers, data=json.dumps(receipt), timeout=10)
            if resp.status_code in (200, 202):
                j = resp.json()
                # web3.storage responses vary, try to pull cid
                receipt['ipfs_cid'] = j.get('cid') or j.get('value', {}).get('cid')
        except Exception as e:
            print('web3.storage pin failed', e)

    # Save to Supabase (optional)
    if SUPABASE_URL and SUPABASE_SERVICE_KEY:
        try:
            url = f"{SUPABASE_URL}/rest/v1/transactions"
            headers = { 'apikey': SUPABASE_SERVICE_KEY, 'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}', 'Content-Type': 'application/json' }
            payload = {
                'tx_id': receipt.get('tx_id'),
                'from_address': body.from_wallet,
                'to_address': body.to_address,
                'amount_lovelace': body.amount_lovelace,
                'metadata': body.metadata or {},
                'ipfs_cid': receipt.get('ipfs_cid')
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=8)
            if resp.status_code not in (200,201,204):
                print('Supabase save failed', resp.status_code, resp.text)
        except Exception as e:
            print('Supabase save error', e)

    return { 'ok': True, 'tx': tx_res, 'receipt': receipt }

# ============ Verify tx (delegates to meshjs tx lookup) ============
@app.post('/verify-tx')
async def verify_tx(body: dict):
    tx_id = body.get('tx_id')
    if not tx_id:
        raise HTTPException(status_code=400, detail='tx_id required')
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{MESHJS_SERVICE_URL}/tx/{tx_id}", timeout=10.0)
            r.raise_for_status()
            return { 'ok': True, 'tx': r.json() }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# ============ Save history (Supabase proxy or local fallback) ============
@app.post('/save-history')
async def save_history(payload: dict):
    if SUPABASE_URL and SUPABASE_SERVICE_KEY:
        try:
            url = f"{SUPABASE_URL}/rest/v1/transactions"
            headers = { 'apikey': SUPABASE_SERVICE_KEY, 'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}', 'Content-Type': 'application/json' }
            r = requests.post(url, headers=headers, json=payload, timeout=8)
            return { 'ok': r.status_code in (200,201,204), 'supabase_response_status': r.status_code, 'body': payload }
        except Exception as e:
            return { 'ok': False, 'error': str(e) }
    else:
        try:
            with open('history_local.json', 'a') as f:
                f.write(json.dumps(payload) + "\n")
            return { 'ok': True, 'saved_to': 'history_local.json' }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# ============ Koios read-only endpoints (new) ============
# GET single address via query param
@app.get("/koios/address_info")
async def koios_address_info_query(address: str = Query(..., description="Cardano address to look up")):
    """
    Query Koios address_info for a single address (GET ?address=...).
    Uses Koios endpoint POST /address_info with JSON { _addresses: [address] }
    """
    payload = {"_addresses": [address]}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{KOIOS_BASE}/address_info", json=payload, timeout=20.0)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as he:
            raise HTTPException(status_code=502, detail=f"Koios error: {he.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# POST multiple addresses
@app.post("/koios/address_info")
async def koios_address_info_post(body: dict):
    """
    POST body: { "addresses": ["addr1", "addr2", ...] }
    """
    addresses = body.get("addresses") or body.get("_addresses")
    if not addresses or not isinstance(addresses, (list, tuple)):
        raise HTTPException(status_code=400, detail="addresses array required")
    payload = {"_addresses": addresses}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{KOIOS_BASE}/address_info", json=payload, timeout=25.0)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as he:
            raise HTTPException(status_code=502, detail=f"Koios error: {he.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# POST address utxos
@app.post("/koios/address_utxo")
async def koios_address_utxo(body: dict):
    """
    POST body: { "addresses": [...] }
    Calls Koios endpoint address_utxos (or address_utxo_history if you prefer)
    """
    addresses = body.get("addresses") or body.get("_addresses")
    if not addresses or not isinstance(addresses, (list, tuple)):
        raise HTTPException(status_code=400, detail="addresses array required")
    payload = {"_addresses": addresses}
    async with httpx.AsyncClient() as client:
        try:
            # choose endpoint name available on Koios (address_utxos or address_utxo_history)
            r = await client.post(f"{KOIOS_BASE}/address_utxos", json=payload, timeout=25.0)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as he:
            # try fallback to address_utxo_history if first fails
            try:
                r2 = await client.post(f"{KOIOS_BASE}/address_utxo_history", json=payload, timeout=25.0)
                r2.raise_for_status()
                return r2.json()
            except Exception:
                raise HTTPException(status_code=502, detail=f"Koios error: {he.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# ============ root / health ============
@app.get("/health")
async def health():
    return {"status":"ok", "time": str(json.dumps({"now": str(uuid.uuid4())})) }

@app.get("/")
async def root():
    return {"ok": True, "service": "Chat-to-Pay Backend (FastAPI) - Full"}

# ============ Run app (if executed directly) ============
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv("PORT", "8000")))