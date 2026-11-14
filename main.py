"""FolioTrack - a small personal investment-portfolio tracker (teaching application).

In-memory data only. Currency: INR. Not for real investment use.
"""
from __future__ import annotations

import copy
import secrets
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

APP_VERSION = "1.0.0"
STATIC_DIR = Path(__file__).parent / "static"

USERS = {"investor": "invest123"}

INSTRUMENTS: dict[str, dict[str, Any]] = {
    "RELIANCE": {"name": "Reliance Industries Ltd", "asset_class": "equity", "ltp": "2850.50"},
    "TCS": {"name": "Tata Consultancy Services Ltd", "asset_class": "equity", "ltp": "3920.00"},
    "INFY": {"name": "Infosys Ltd", "asset_class": "equity", "ltp": "1510.25"},
    "HDFCBANK": {"name": "HDFC Bank Ltd", "asset_class": "equity", "ltp": "1645.80"},
    "NIFTYBEES": {"name": "Nifty 50 Index ETF", "asset_class": "etf", "ltp": "245.60"},
    "GOLDBEES": {"name": "Gold ETF", "asset_class": "etf", "ltp": "58.35"},
    "FLEXICAP": {"name": "Flexi Cap Fund - Direct Growth", "asset_class": "mutual_fund", "ltp": "78.45"},
    "BLUECHIP": {"name": "Bluechip Fund - Direct Growth", "asset_class": "mutual_fund", "ltp": "56.20"},
}

SEED_TRANSACTIONS = [
    {"symbol": "TCS", "type": "BUY", "quantity": 10, "price": "3500.00", "trade_date": "2025-01-15"},
    {"symbol": "INFY", "type": "BUY", "quantity": 50, "price": "1450.00", "trade_date": "2025-02-20"},
    {"symbol": "NIFTYBEES", "type": "BUY", "quantity": 200, "price": "230.00", "trade_date": "2025-03-01"},
    {"symbol": "FLEXICAP", "type": "BUY", "quantity": 500, "price": "70.00", "trade_date": "2025-04-12"},
    {"symbol": "GOLDBEES", "type": "BUY", "quantity": 100, "price": "60.00", "trade_date": "2025-05-20"},
    {"symbol": "TCS", "type": "BUY", "quantity": 30, "price": "3800.00", "trade_date": "2025-06-10"},
    {"symbol": "INFY", "type": "SELL", "quantity": 20, "price": "1600.00", "trade_date": "2025-09-05"},
]

MAX_QUANTITY = 10000
LATEST_TRADE_DATE = date(2099, 12, 31)

STATE: dict[str, Any] = {}
TOKENS: dict[str, str] = {}


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def reset_state() -> None:
    STATE["transactions"] = []
    STATE["next_id"] = 1
    for seed in SEED_TRANSACTIONS:
        txn = copy.deepcopy(seed)
        txn["id"] = STATE["next_id"]
        STATE["next_id"] += 1
        STATE["transactions"].append(txn)


reset_state()

app = FastAPI(
    title="FolioTrack API",
    version=APP_VERSION,
    description="Teaching application - not for real investment use.",
)


# ---------------------------------------------------------------- errors
class ApiError(Exception):
    def __init__(self, status: int, error: str, message: str, field: str | None = None):
        self.status, self.error, self.message, self.field = status, error, message, field


def error_body(error: str, message: str, field: str | None = None) -> dict:
    body = {"error": error, "message": message}
    if field:
        body["field"] = field
    return body


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status, content=error_body(exc.error, exc.message, exc.field))


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    loc = [str(p) for p in first.get("loc", []) if p != "body"]
    return JSONResponse(
        status_code=422,
        content=error_body("validation_error", first.get("msg", "Invalid request"), ".".join(loc) or None),
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException):
    names = {404: "not_found", 405: "method_not_allowed", 401: "unauthorized"}
    return JSONResponse(status_code=exc.status_code, content=error_body(names.get(exc.status_code, "error"), str(exc.detail)))


def require_user(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "unauthorized", "Missing or invalid Authorization header (expected 'Bearer <token>')")
    token = authorization.split(" ", 1)[1].strip()
    user = TOKENS.get(token)
    if not user:
        raise ApiError(401, "unauthorized", "Invalid or expired token")
    return user


async def read_json(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        raise ApiError(422, "validation_error", "Request body must be valid JSON")
    if not isinstance(data, dict):
        raise ApiError(422, "validation_error", "Request body must be a JSON object")
    return data


# ---------------------------------------------------------------- calculations
def held_quantity(symbol: str, transactions: list[dict] | None = None) -> int:
    txns = STATE["transactions"] if transactions is None else transactions
    qty = 0
    for t in txns:
        if t["symbol"] == symbol:
            qty += t["quantity"] if t["type"] == "BUY" else -t["quantity"]
    return qty


def average_cost(buys: list[dict]) -> Decimal:
    if not buys:
        return Decimal("0")
    prices = [Decimal(b["price"]) for b in buys]
    return sum(prices) / len(prices)


def percent_of(part: Decimal, invested: Decimal, current: Decimal) -> Decimal:
    if current == 0:
        return Decimal("0.00")
    return money(part / current * 100)


def compute_holdings() -> list[dict]:
    holdings = []
    for symbol, inst in INSTRUMENTS.items():
        qty = held_quantity(symbol)
        if qty == 0:
            continue
        buys = [t for t in STATE["transactions"] if t["symbol"] == symbol and t["type"] == "BUY"]
        avg = average_cost(buys)
        ltp = Decimal(inst["ltp"])
        invested = money(avg * qty)
        current = money(ltp * qty)
        pnl = current - invested
        holdings.append({
            "symbol": symbol,
            "name": inst["name"],
            "asset_class": inst["asset_class"],
            "quantity": qty,
            "avg_cost": float(money(avg)),
            "invested_value": float(invested),
            "ltp": float(ltp),
            "current_value": float(current),
            "pnl": float(pnl),
            "pnl_pct": float(percent_of(pnl, invested, current)),
        })
    return holdings


def compute_summary() -> dict:
    holdings = compute_holdings()
    invested = sum((Decimal(str(h["invested_value"])) for h in holdings), Decimal("0"))
    current = sum((Decimal(str(h["current_value"])) for h in holdings), Decimal("0"))
    pnl = current - invested
    allocation = []
    for asset_class in ("equity", "etf", "mutual_fund"):
        value = sum((Decimal(str(h["current_value"])) for h in holdings if h["asset_class"] == asset_class), Decimal("0"))
        pct = money(value / current * 100) if current else Decimal("0.00")
        allocation.append({"asset_class": asset_class, "current_value": float(money(value)), "percent": float(pct)})
    return {
        "currency": "INR",
        "total_invested": float(money(invested)),
        "total_current_value": float(money(current)),
        "total_pnl": float(money(pnl)),
        "total_pnl_pct": float(percent_of(pnl, invested, current)),
        "holdings_count": len(holdings),
        "allocation": allocation,
    }


# ---------------------------------------------------------------- validation
def validate_transaction(data: dict) -> dict:
    symbol = data.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ApiError(422, "validation_error", "symbol is required", "symbol")
    symbol = symbol.strip().upper()
    if symbol not in INSTRUMENTS:
        raise ApiError(422, "validation_error", f"Unknown instrument symbol '{symbol}'", "symbol")

    ttype = data.get("type")
    if not isinstance(ttype, str) or ttype.upper() not in ("BUY", "SELL"):
        raise ApiError(422, "validation_error", "type must be BUY or SELL", "type")
    ttype = ttype.upper()

    qty = data.get("quantity")
    if isinstance(qty, bool) or not isinstance(qty, (int, float)) or (isinstance(qty, float) and not qty.is_integer()):
        raise ApiError(422, "validation_error", f"quantity must be a whole number between 1 and {MAX_QUANTITY}", "quantity")
    qty = int(qty)
    if qty < 1 or qty > MAX_QUANTITY:
        raise ApiError(422, "validation_error", f"quantity must be a whole number between 1 and {MAX_QUANTITY}", "quantity")

    raw_price = data.get("price")
    if isinstance(raw_price, bool) or not isinstance(raw_price, (int, float, str)):
        raise ApiError(422, "validation_error", "price must be a number greater than 0 with at most 2 decimals", "price")
    try:
        price = Decimal(str(raw_price))
    except InvalidOperation:
        raise ApiError(422, "validation_error", "price must be a number greater than 0 with at most 2 decimals", "price")
    if not price.is_finite() or price <= 0 or price.as_tuple().exponent < -2:
        raise ApiError(422, "validation_error", "price must be a number greater than 0 with at most 2 decimals", "price")

    raw_date = data.get("trade_date")
    try:
        trade_date = date.fromisoformat(raw_date) if isinstance(raw_date, str) and len(raw_date) == 10 else None
    except ValueError:
        trade_date = None
    if trade_date is None:
        raise ApiError(422, "validation_error", "trade_date must be a valid date in YYYY-MM-DD format", "trade_date")
    if trade_date > LATEST_TRADE_DATE:
        raise ApiError(422, "validation_error", "trade_date cannot be in the future", "trade_date")

    if ttype == "SELL":
        held = held_quantity(symbol)
        if qty - held > 1:
            raise ApiError(409, "insufficient_holding",
                           f"Cannot sell {qty} units of {symbol}; current holding is {held}")

    return {"symbol": symbol, "type": ttype, "quantity": qty,
            "price": str(money(price)), "trade_date": trade_date.isoformat()}


def txn_out(t: dict) -> dict:
    inst = INSTRUMENTS[t["symbol"]]
    return {"id": t["id"], "symbol": t["symbol"], "name": inst["name"], "type": t["type"],
            "quantity": t["quantity"], "price": float(Decimal(t["price"])),
            "amount": float(money(Decimal(t["price"]) * t["quantity"])), "trade_date": t["trade_date"]}


# ---------------------------------------------------------------- routes
@app.get("/health")
def health():
    return {"status": "ok", "version": APP_VERSION}


@app.post("/api/login")
async def login(request: Request):
    data = await read_json(request)
    username, password = data.get("username"), data.get("password")
    if not username or not password:
        raise ApiError(422, "validation_error", "username and password are required")
    if USERS.get(username) != password:
        raise ApiError(401, "unauthorized", "Invalid username or password")
    token = secrets.token_hex(16)
    TOKENS[token] = username
    return {"access_token": token, "token_type": "bearer", "username": username}


@app.post("/api/reset")
def reset():
    reset_state()
    return {"status": "reset", "transactions": len(STATE["transactions"])}


@app.get("/api/instruments")
def list_instruments():
    return [{"symbol": s, "name": i["name"], "asset_class": i["asset_class"], "ltp": float(Decimal(i["ltp"]))}
            for s, i in INSTRUMENTS.items()]


@app.get("/api/transactions")
def list_transactions(authorization: str | None = Header(default=None)):
    require_user(authorization)
    txns = sorted(STATE["transactions"], key=lambda t: (t["trade_date"], t["id"]))
    return [txn_out(t) for t in txns]


@app.post("/api/transactions", status_code=201)
async def create_transaction(request: Request, authorization: str | None = Header(default=None)):
    require_user(authorization)
    data = await read_json(request)
    txn = validate_transaction(data)
    txn["id"] = STATE["next_id"]
    STATE["next_id"] += 1
    STATE["transactions"].append(txn)
    return JSONResponse(status_code=201, content=txn_out(txn))


@app.delete("/api/transactions/{txn_id}", status_code=204)
def delete_transaction(txn_id: int, authorization: str | None = Header(default=None)):
    require_user(authorization)
    txn = next((t for t in STATE["transactions"] if t["id"] == txn_id), None)
    if txn is None:
        raise ApiError(404, "not_found", f"Transaction {txn_id} not found")
    remaining = [t for t in STATE["transactions"] if t["id"] != txn_id]
    if held_quantity(txn["symbol"], remaining) < 0:
        raise ApiError(409, "insufficient_holding",
                       f"Deleting transaction {txn_id} would leave a negative holding of {txn['symbol']}")
    STATE["transactions"] = remaining
    return Response(status_code=204)


@app.get("/api/holdings")
def holdings(authorization: str | None = Header(default=None)):
    require_user(authorization)
    return compute_holdings()


@app.get("/api/portfolio/summary")
def summary(authorization: str | None = Header(default=None)):
    require_user(authorization)
    return compute_summary()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
