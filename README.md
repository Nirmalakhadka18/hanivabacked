Chat-to-Pay Backend Zip (FastAPI + MeshJS microservice)
------------------------------------------------------

What's included:
- fastapi/    -> FastAPI backend (intent detection, tx build proxy, submit signed tx, IPFS pinning)
- meshjs/     -> Node.js microservice scaffold for MeshJS/Hydra (mocked endpoints)
- supabase_schema.sql -> example Supabase table for transaction history
- deployment_guides.txt -> short deployment notes
- pitch_short.txt -> short pitch for judges

Quickstart (local):
1. Unzip and open in VS Code
2. Start meshjs: cd meshjs && npm install && npm start (port 3001)
3. Start fastapi: cd fastapi && pip install -r requirements.txt && uvicorn main:app --reload --port 8000
4. Test: POST http://localhost:8000/intent {"message":"Send 2 ADA to Nirmala"}
