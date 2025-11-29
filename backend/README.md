FastAPI backend - Chat-to-Pay (Full backend scaffold)

Endpoints:
- POST /intent -> AI intent extraction (OpenAI fallback to simple parser)
- POST /create-unsigned-tx -> delegates to MeshJS microservice to build unsigned tx
- POST /submit-signed-tx -> submits signed tx via MeshJS microservice, pins receipt to web3.storage, saves to Supabase
- POST /verify-tx -> query tx status from MeshJS microservice
- POST /save-history -> save tx metadata to Supabase or local file

To run locally:
1. Copy .env.example to .env and fill API keys.
2. Start meshjs microservice (see meshjs/ folder)
3. Install deps: pip install -r requirements.txt
4. Start: uvicorn main:app --reload --port 8000
