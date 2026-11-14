# FolioTrack

A small personal investment-portfolio tracker: a FastAPI REST API with in-memory data and a one-page web UI.

> **Teaching application – not for real investment use.** FolioTrack exists to be tested by
> automated tools. Instrument prices are fixed, illustrative values, data is lost on restart,
> and the software may contain defects.

## Features
- Login with a Bearer token (test user `investor` / `invest123`)
- Fixed master of 8 instruments (equity, ETF, mutual fund), currency INR
- BUY / SELL transactions with validation; list and delete
- Holdings with average cost, invested value, current value, P&L and P&L %
- Portfolio summary with totals and asset allocation
- `POST /api/reset` restores the seed data for tests

## Run
```bash
./run.sh                 # creates .venv, installs, serves http://127.0.0.1:8200
# or
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8200
```
Open http://127.0.0.1:8200 for the UI and http://127.0.0.1:8200/docs for interactive API docs.

## Quick API tour
```bash
curl -s http://127.0.0.1:8200/health
TOKEN=$(curl -s -X POST http://127.0.0.1:8200/api/login -H 'Content-Type: application/json' \
  -d '{"username":"investor","password":"invest123"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s http://127.0.0.1:8200/api/holdings -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://127.0.0.1:8200/api/transactions -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"RELIANCE","type":"BUY","quantity":5,"price":2800.00,"trade_date":"2025-07-01"}'
```

## Documents
- `docs/FolioTrack_PRD.md` / `.docx` – product requirements with acceptance criteria, worked examples and a UI element reference
- `docs/FolioTrack_API_Spec.yaml` – OpenAPI 3.0 specification
- `aat.yaml` – run manifest for the AI Assisted Testing app (install, start, health check, docs)

## License
MIT – see `LICENSE`.
