# Hanivabacked - Chat-To-Pay Backend

A full-stack Chat-to-Pay payment system combining a **FastAPI backend** with a **Node.js MeshJS microservice** for Cardano blockchain integration.

##  Project Overview

**Hanivabacked** enables users to send blockchain payments through natural language intent (e.g., "Send 2 ADA to Nirmala"). The backend processes intent recognition, builds transactions, and handles blockchain submission, while the MeshJS service manages Hydra wallet interactions.

##  Project Structure

```
Hanivabacked/
 backend/                # FastAPI REST API (Python 3.11)
    main.py              # Core endpoints: /intent, /submit, /verify
    requirements.txt     # Python dependencies
    .env                 # Environment variables (secrets)
    README.md            # Backend-specific docs
 meshjs/                 # Node.js microservice (MeshJS + Hydra)
    index.js             # Entry point
    package.json         # Node dependencies
    meshjs.env           # MeshJS configuration
    README.md            # MeshJS-specific docs
 Haniva_Frontend/        # Frontend application (React/TypeScript)
 supabase_schema.sql     # Example Supabase schema for tx history
 deployment_guides.txt   # Deployment notes for cloud providers
 pitch_short.txt         # Project pitch for judges/investors
 LICENSE                 # MIT License
 .gitignore              # Git ignore rules
```

##  Quick Start

### Prerequisites
- Python 3.11+ (for backend)
- Node.js 18+ (for meshjs)
- pip and npm

### 1. Clone & Install

```bash
git clone https://github.com/Nirmalakhadka18/Hanivabacked.git
cd Hanivabacked
```

### 2. Run Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Backend runs at http://localhost:8000
- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 3. Run MeshJS Service (in another terminal)

```bash
cd meshjs
npm install
npm start
```

MeshJS service runs at http://localhost:3001

### 4. Test Intent Endpoint

```bash
curl -X POST http://localhost:8000/intent -H "Content-Type: application/json" -d '{"message":"Send 2 ADA to Nirmala"}'
```

##  Documentation

- Backend API: See backend/README.md for detailed endpoint docs
- MeshJS Service: See meshjs/README.md for integration details
- Deployment: See deployment_guides.txt for cloud setup (AWS, Azure, Heroku)
- Database: See supabase_schema.sql for transaction history schema

##  Environment Variables

### Backend (.env in backend/ folder)
```
SUPABASE_URL=<your-supabase-url>
SUPABASE_KEY=<your-supabase-api-key>
MESHJS_SERVICE_URL=http://localhost:3001
```

### MeshJS (.env in meshjs/ folder)
```
BLOCKFROST_API_KEY=<your-blockfrost-key>
NETWORK=preprod
```

##  License

MIT License - See LICENSE for details.
