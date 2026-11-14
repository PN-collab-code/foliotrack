# FolioTrack – Product Requirements Document

| Item | Value |
|---|---|
| Product | FolioTrack – personal investment-portfolio tracker |
| Version | 1.0 |
| Status | Approved for build |
| Currency | INR (₹) |
| Audience | Teaching application – not for real investment use |

## 1. Goals

1. Let an individual investor record BUY and SELL transactions for a fixed list of instruments.
2. Show current holdings with average cost, invested value, current value and profit and loss (P&L).
3. Show a portfolio summary with totals and asset allocation.
4. Provide a small, well-specified REST API and web UI that can be tested automatically.

Non-goals: live market prices, multiple currencies, tax lots, dividends, corporate actions, multi-user accounts, persistent storage.

## 2. Users

| Persona | Description |
|---|---|
| Investor | A single individual tracking their own investments. Test account: username `investor`, password `invest123`. |
| Tester / automation | Uses the API (including `POST /api/reset`) to put the application into a known state. |

## 3. Instrument master

The application has a fixed instrument master of 8 instruments. The last traded price (LTP) is fixed and never changes.

| Symbol | Name | Asset class | LTP (₹) |
|---|---|---|---|
| RELIANCE | Reliance Industries Ltd | equity | 2850.50 |
| TCS | Tata Consultancy Services Ltd | equity | 3920.00 |
| INFY | Infosys Ltd | equity | 1510.25 |
| HDFCBANK | HDFC Bank Ltd | equity | 1645.80 |
| NIFTYBEES | Nifty 50 Index ETF | etf | 245.60 |
| GOLDBEES | Gold ETF | etf | 58.35 |
| FLEXICAP | Flexi Cap Fund - Direct Growth | mutual_fund | 78.45 |
| BLUECHIP | Bluechip Fund - Direct Growth | mutual_fund | 56.20 |

## 4. Seed data

`POST /api/reset` restores exactly these transactions (ids 1–7):

| Id | Date | Symbol | Type | Qty | Price (₹) |
|---|---|---|---|---|---|
| 1 | 2025-01-15 | TCS | BUY | 10 | 3500.00 |
| 2 | 2025-02-20 | INFY | BUY | 50 | 1450.00 |
| 3 | 2025-03-01 | NIFTYBEES | BUY | 200 | 230.00 |
| 4 | 2025-04-12 | FLEXICAP | BUY | 500 | 70.00 |
| 5 | 2025-05-20 | GOLDBEES | BUY | 100 | 60.00 |
| 6 | 2025-06-10 | TCS | BUY | 30 | 3800.00 |
| 7 | 2025-09-05 | INFY | SELL | 20 | 1600.00 |

## 5. Calculation rules (apply to all requirements)

- **R-MONEY:** All money values are rounded half-up to 2 decimals (e.g. 10.005 → 10.01, 10.004 → 10.00). Percentages are rounded half-up to 2 decimals.
- **R-AVG:** Average cost of a holding = Σ(quantity × price) over all BUY transactions of the instrument ÷ Σ(quantity) over those BUY transactions (quantity-weighted average). SELL transactions reduce the quantity held but do not change the average cost.
- **R-QTY:** Quantity held = Σ BUY quantities − Σ SELL quantities.
- **R-INV:** Invested value = quantity held × average cost (unrounded average), then rounded.
- **R-CUR:** Current value = quantity held × LTP.
- **R-PNL:** P&L = current value − invested value.
- **R-PCT:** P&L % = P&L ÷ invested value × 100. If invested value is 0, P&L % is 0.00.

## 6. Functional requirements

### FR-1 Health check
`GET /health` returns 200 with `{"status": "ok", "version": "<version>"}`. No authentication.

**Acceptance criteria**
- AC-1.1 Returns HTTP 200 and `status` = `ok`.

### FR-2 Login
`POST /api/login` with `{"username", "password"}` returns a Bearer token.

**Acceptance criteria**
- AC-2.1 Valid credentials (`investor` / `invest123`) return 200 with `access_token` (non-empty string), `token_type` = `bearer` and `username`.
- AC-2.2 A wrong username or password returns 401 with `error` = `unauthorized`.
- AC-2.3 A missing username or password returns 422 with `error` = `validation_error`.
- AC-2.4 All `/api/transactions`, `/api/holdings` and `/api/portfolio/summary` endpoints require the header `Authorization: Bearer <token>`; without a valid token they return 401.

### FR-3 Reset
`POST /api/reset` restores the seed data in section 4. No authentication. Returns 200 with `{"status": "reset", "transactions": 7}`. Existing tokens stay valid.

**Acceptance criteria**
- AC-3.1 After reset, `GET /api/transactions` returns exactly the 7 seed transactions.

### FR-4 Instruments
`GET /api/instruments` returns the 8 instruments in section 3 with `symbol`, `name`, `asset_class` and `ltp`. No authentication.

**Acceptance criteria**
- AC-4.1 Returns 200 and a list of exactly 8 instruments matching section 3.

### FR-5 Add transaction
`POST /api/transactions` with `{"symbol", "type", "quantity", "price", "trade_date"}` creates a transaction and returns 201 with the created transaction (`id`, `symbol`, `name`, `type`, `quantity`, `price`, `amount`, `trade_date`). `amount` = quantity × price, rounded.

Validation rules (each violation returns **422** with `error` = `validation_error`, a clear `message` and the offending `field`):

| Field | Rule |
|---|---|
| symbol | Required; must be one of the 8 instrument symbols (case-insensitive). |
| type | Required; `BUY` or `SELL` (case-insensitive). |
| quantity | Required; whole number from 1 to 10000 inclusive. |
| price | Required; number greater than 0 with at most 2 decimal places. |
| trade_date | Required; valid date in `YYYY-MM-DD` format; must not be later than today (the server's current date). Today is allowed. |

Business rule: a SELL quantity must not exceed the current quantity held of that instrument. A violation returns **409** with `error` = `insufficient_holding`.

**Acceptance criteria**
- AC-5.1 A valid BUY returns 201; the transaction appears in `GET /api/transactions`.
- AC-5.2 Quantity boundaries: 1 and 10000 are accepted; 0, 10001, -1 and 2.5 return 422 (`field` = `quantity`).
- AC-5.3 Price: 0.01 and 100.25 are accepted; 0, -5 and 10.123 return 422 (`field` = `price`).
- AC-5.4 Trade date: today and past dates are accepted; tomorrow or any later date returns 422 (`field` = `trade_date`, message "trade_date cannot be in the future"); an invalid format (e.g. `15-01-2025`) returns 422.
- AC-5.5 An unknown symbol returns 422 (`field` = `symbol`); a type other than BUY/SELL returns 422 (`field` = `type`).
- AC-5.6 SELL boundaries: with 30 units held, SELL 30 is accepted (holding becomes 0 and the instrument disappears from holdings); SELL 31 returns 409 and nothing is stored.
- AC-5.7 SELL of an instrument that is not held returns 409.

**Worked example (FR-5)**
After reset, INFY quantity held = 50 − 20 = 30. `SELL 31 INFY` → 409 `insufficient_holding`. `SELL 30 INFY` → 201, INFY no longer appears in holdings.

### FR-6 List and delete transactions
`GET /api/transactions` returns all transactions sorted by `trade_date`, then `id`. `DELETE /api/transactions/{id}` deletes a transaction and returns 204.

**Acceptance criteria**
- AC-6.1 Deleting an existing transaction returns 204 and it no longer appears in the list.
- AC-6.2 Deleting an unknown id returns 404 with `error` = `not_found`.
- AC-6.3 Deleting a BUY that would make the quantity held negative returns 409 with `error` = `insufficient_holding`.

### FR-7 Holdings
`GET /api/holdings` returns one row per instrument with quantity held > 0: `symbol`, `name`, `asset_class`, `quantity`, `avg_cost`, `invested_value`, `ltp`, `current_value`, `pnl`, `pnl_pct`, calculated with the rules in section 5.

**Acceptance criteria**
- AC-7.1 Average cost is the quantity-weighted average of BUY prices (R-AVG).
- AC-7.2 Invested value, current value and P&L follow R-INV, R-CUR and R-PNL.
- AC-7.3 P&L % = P&L ÷ invested value × 100 (R-PCT).
- AC-7.4 Instruments with quantity 0 are not listed.

**Worked example (FR-7) – average cost**
BUY 10 TCS @ 3500.00 and BUY 30 TCS @ 3800.00:
average cost = (10 × 3500 + 30 × 3800) ÷ (10 + 30) = (35000 + 114000) ÷ 40 = **3725.00**.
Invested value = 40 × 3725.00 = **149000.00**. Current value = 40 × 3920.00 = **156800.00**.
P&L = 156800.00 − 149000.00 = **7800.00**. P&L % = 7800 ÷ 149000 × 100 = 5.2349… → **5.23**.

**Worked example (FR-7) – SELL does not change average cost**
BUY 50 INFY @ 1450.00, SELL 20 INFY @ 1600.00: quantity = 30, average cost = **1450.00**, invested = 30 × 1450 = **43500.00**, current = 30 × 1510.25 = **45307.50**, P&L = **1807.50**, P&L % = 1807.50 ÷ 43500 × 100 = 4.1551… → **4.16**.

**Worked example (FR-7) – loss**
BUY 100 GOLDBEES @ 60.00: current = 100 × 58.35 = 5835.00, invested = 6000.00, P&L = **−165.00**, P&L % = −165 ÷ 6000 × 100 = **−2.75**.

**Expected holdings after reset**

| Symbol | Qty | Avg cost | Invested | Current | P&L | P&L % |
|---|---|---|---|---|---|---|
| TCS | 40 | 3725.00 | 149000.00 | 156800.00 | 7800.00 | 5.23 |
| INFY | 30 | 1450.00 | 43500.00 | 45307.50 | 1807.50 | 4.16 |
| NIFTYBEES | 200 | 230.00 | 46000.00 | 49120.00 | 3120.00 | 6.78 |
| GOLDBEES | 100 | 60.00 | 6000.00 | 5835.00 | -165.00 | -2.75 |
| FLEXICAP | 500 | 70.00 | 35000.00 | 39225.00 | 4225.00 | 12.07 |

### FR-8 Portfolio summary
`GET /api/portfolio/summary` returns `currency` (`INR`), `total_invested`, `total_current_value`, `total_pnl`, `total_pnl_pct`, `holdings_count` and `allocation` – a list of exactly three entries (`equity`, `etf`, `mutual_fund`, in that order) with `current_value` and `percent` of total current value.

**Acceptance criteria**
- AC-8.1 Totals are the sums of the holdings rows; `total_pnl` = `total_current_value` − `total_invested`.
- AC-8.2 `total_pnl_pct` = `total_pnl` ÷ `total_invested` × 100 (R-PCT).
- AC-8.3 Allocation percent = asset-class current value ÷ total current value × 100; an empty portfolio gives 0.00 for every class and all totals 0.

**Worked example (FR-8) – after reset**
total invested = 149000 + 43500 + 46000 + 6000 + 35000 = **279500.00**
total current = 156800 + 45307.50 + 49120 + 5835 + 39225 = **296287.50**
total P&L = **16787.50**; total P&L % = 16787.50 ÷ 279500 × 100 = 6.0062… → **6.01**
allocation: equity 202107.50 → **68.21 %**; etf 54955.00 → **18.55 %**; mutual_fund 39225.00 → **13.24 %**.

### FR-9 Web UI
A single-page UI is served at `/`.

**Acceptance criteria**
- AC-9.1 The login form signs the user in; wrong credentials show "Invalid username or password" in `#login-error`; empty fields show "Username and password are required".
- AC-9.2 After login the summary cards show total invested, current value, total P&L and total P&L % formatted as INR (e.g. ₹2,79,500.00).
- AC-9.3 **Sign styling:** a value ≥ 0 in `#summary-pnl`, `#summary-pnl-pct` and the holdings P&L cells has the CSS class `positive` (green); a negative value has the class `negative` (red).
- AC-9.4 Adding a valid transaction shows a confirmation in `#txn-success` and refreshes the cards, holdings and transactions without a page reload.
- AC-9.5 A rejected transaction shows the API's `message` in `#txn-error`.
- AC-9.6 The holdings table shows one row per holding (`#holding-<SYMBOL>`), and the allocation panel shows three rows.
- AC-9.7 Each transaction row has a Delete button (`#delete-txn-<id>`) that removes it.
- AC-9.8 Log out returns to the login form.

**Worked example (FR-9) – negative total P&L**
After reset, delete transactions 7, 1, 2, 3, 4 and 6, in that order (id 7, the INFY SELL, must go before id 2, or AC-6.3 rejects the delete). Only GOLDBEES BUY 100 @ 60.00 remains: total P&L = **−₹165.00**, total P&L % = **−2.75%**, and both `#summary-pnl` and `#summary-pnl-pct` must have the class `negative`.

## 7. Non-functional requirements

- NFR-1 Responses to every API call within 500 ms on a developer laptop.
- NFR-2 Validation errors return 422 with body `{"error", "message", "field"}`; other errors return `{"error", "message"}`.
- NFR-3 Data is in memory only; restarting the server restores the seed data.
- NFR-4 The UI works in current Chromium, Firefox and Safari without external CDNs.
- NFR-5 `index.html` is served with `Cache-Control: no-cache`.
- NFR-6 The app runs with `python -m uvicorn main:app --host 127.0.0.1 --port 8200`.

## 8. UI element reference

| Element | id / selector | Notes |
|---|---|---|
| Login section | `#login-section` | Hidden after login |
| Login form | `#login-form` | |
| Username input | `#login-username` | |
| Password input | `#login-password` | |
| Sign-in button | `#login-submit` | |
| Login error | `#login-error` | |
| App section | `#app-section` | Visible after login |
| User name | `#user-name` | |
| Log out button | `#logout-btn` | |
| Total invested | `#summary-invested` | Inside `#card-invested` |
| Current value | `#summary-current` | Inside `#card-current` |
| Total P&L | `#summary-pnl` | Class `positive` / `negative` |
| Total P&L % | `#summary-pnl-pct` | Class `positive` / `negative` |
| Transaction form | `#txn-form` | |
| Instrument select | `#txn-symbol` | Option values = symbols |
| Type select | `#txn-type` | `BUY` / `SELL` |
| Quantity input | `#txn-quantity` | |
| Price input | `#txn-price` | |
| Trade date input | `#txn-date` | Defaults to today |
| Add button | `#txn-submit` | |
| Transaction error | `#txn-error` | |
| Transaction success | `#txn-success` | |
| Holdings table | `#holdings-table`, body `#holdings-body` | Row `#holding-<SYMBOL>`; cells `.h-qty`, `.h-avg`, `.h-ltp`, `.h-invested`, `.h-current`, `.h-pnl`, `.h-pnl-pct` |
| Empty holdings message | `#holdings-empty` | |
| Allocation panel | `#allocation-list` | Rows `#alloc-equity`, `#alloc-etf`, `#alloc-mutual_fund`; `.alloc-value`, `.alloc-percent` |
| Transactions table | `#transactions-table`, body `#transactions-body` | Row `#txn-row-<id>` |
| Delete button | `#delete-txn-<id>` | |
