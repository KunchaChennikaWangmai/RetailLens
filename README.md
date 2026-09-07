# Retail Lens

Retail Lens is an AI-powered retail analytics and operations app for
shopkeepers, built with **React + TypeScript + Vite**, **FastAPI**,
**Google ADK**, **Gemini** and **BigQuery** (via MCP Toolbox).

It covers Home, AI Chat, Analytics, Inventory, Employees, Customers,
Profitability and Data — designed to be simple, action-oriented and honest
about what the data does and does not contain.

---

## Architecture

Two paths, by design:

```
AI Chat (natural language):
  Frontend → POST /api/chat → FastAPI → ADK root orchestrator (Gemini)
           → sub-agents (sales / inventory / workforce / customer)
           → MCP Toolbox → BigQuery → Gemini → markdown answer

Structured page data (deterministic):
  Frontend → GET /api/... → FastAPI query layer → BigQuery
```

Page APIs never pass through the LLM, so dashboards always show real,
reproducible numbers. Chat is for open-ended questions and business
summaries.

### BigQuery dataset: `retail_lens_patchamomma`

| Table | Contents |
|---|---|
| `sales_transactions` | Bill lines: product, quantity, prices, bill, timestamp |
| `customer_bills` | Bills linked to customers (id, name, phone) |
| `inventory_stock` | Stock on hand + reorder level per product |
| `inventory_supply` | Incoming supply: supplier, qty, lead time, delivery date |
| `inventory_metadata` | Product master: category, cost, retail, essentiality, shelf life |
| `workforce_shifts` | Shifts: employee, timing, rostered hours, wage, check-in/out |

> **Demo data:** all rows are synthetic but follow realistic retail patterns.
> Sales span May–August 2026; bills, shifts, stock and supply cover August 2026.
> Date windows are anchored to the latest date that actually has data.

> **Gross vs net profit:** the system reports **gross profit only**
> (revenue − COGS). Operating expenses are not in the dataset; net profit is
> not available and is never shown or implied.

---

## Directory Structure

```
retail-lens/
├── app/
│   ├── main.py                  # Milestone-1 connectivity check script
│   ├── api.py                   # FastAPI: /api/chat + structured endpoints
│   ├── agents/                  # ADK orchestrator + sub-agents + prompts
│   ├── tools/
│   │   ├── bigquery_client.py   # BigQuery client + dry-run cost guard
│   │   ├── mcp_toolbox.py       # MCP Toolbox integration point
│   │   ├── query_runner.py      # Shared SQL execution helper
│   │   └── sales/inventory/workforce/customer_tools.py
│   └── schemas/                 # Pydantic response models
├── frontend/
│   └── src/
│       ├── App.tsx              # Layout + routing
│       ├── Home.tsx             # Real KPIs + 30-day trend + chat handoff
│       ├── Chat.tsx             # Markdown AI chat
│       ├── Inventory.tsx / Employees.tsx / Customers.tsx
│       ├── Profitability.tsx / Analytics.tsx / Data.tsx
│       ├── services/api.ts      # Typed API client
│       └── utils/format.ts      # INR/date formatting
├── tests/                       # Deterministic milestone tests (M1–M23)
├── tools.yaml                   # MCP Toolbox SQL definitions (source of truth)
├── Dockerfile                   # uvicorn app.api:app
└── requirements.txt
```

---

## API Reference

### Chat

| Method | Path | Description |
|---|---|---|
| POST | `/api/chat` | Natural-language question → ADK agents → markdown answer. 503 when Gemini is busy, 504 on timeout (`CHAT_TIMEOUT_SECONDS`, default 120). |
| GET | `/api/health` | Liveness + configuration probe. |

### Structured (BigQuery-backed)

| Method | Path | Params | Description |
|---|---|---|---|
| GET | `/api/home/summary` | `date` (optional) | One-day revenue, bills, units, average bill |
| GET | `/api/home/sales-trend` | `days` (default 30) | Daily revenue/bills/units |
| GET | `/api/inventory/replenishment-risk` | `days` | Stock, incoming supply, coverage days |
| GET | `/api/inventory/stock` | — | Current stock levels |
| GET | `/api/inventory/supply` | — | Incoming supply orders |
| GET | `/api/employees/summary` | `days` | Labour cost, shifts, hours, late/early/overtime |
| GET | `/api/customers/behavior` | `days` | Unique/repeat customers, spend ranking |
| GET | `/api/profitability/products` | `days` | Gross profit and margin by product |

Without a `date`/window anchor, endpoints use the most recent dates that
actually contain data, so the demo dataset always renders meaningfully.

---

## Local Setup

```bash
# 1. Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in GEMINI_API_KEY, GOOGLE_CLOUD_PROJECT

# 2. Start MCP Toolbox (serves tools.yaml on :5000)
npx -y toolbox-tools serve --tools-file tools.yaml --port 5000

# 3. Start the API (serves frontend /api proxy target)
uvicorn app.api:app --host 127.0.0.1 --port 8000

# 4. Frontend (separate shell)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`.

### Tests

```bash
python tests/test_m15_structured_api.py     # also runs live BigQuery checks
python tests/test_m16_home_integration.py
python tests/test_m17_inventory_page.py
python tests/test_m18_employees_page.py
python tests/test_m19_customers_page.py
python tests/test_m20_profitability_page.py
python tests/test_m21_analytics_page.py
python tests/test_m22_data_page.py
python tests/test_m23_final_integration.py
cd frontend && npx tsc --noEmit && npm run build
```

---

## Docker

```bash
docker build -t retail-lens .
docker run --env-file .env -p 8000:8000 retail-lens
# Serves the API (and chat) on http://localhost:8000 — UI is run separately.
```

Never bake credentials into the image; env vars are supplied at runtime.