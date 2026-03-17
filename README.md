# SunBun Solar Assistant

A stateful solar sales and service assistant built with FastAPI, CSV-based data, and a live agent chat powered by Groq LLM.

---

## Video Walkthrough

▶️ [Watch the full demo on Google Drive](https://drive.google.com/file/d/1NL8YsvbnXySuDmA0-lyEfPMtGANoPqa0/view?usp=sharing)

---

## Screenshots

### 1. Landing Page
![Landing Page](https://drive.google.com/uc?export=view&id=1hKKgv8PBJANk5_BYvMNlWxQQ9L0Yz0GK)

### 2. Authentication (OTP)
![Authentication](https://drive.google.com/uc?export=view&id=1TwsMq3X8nDSOlJsdLxe465J2h0AI0LQc)

### 3. Sales Support
![Sales Support](https://drive.google.com/uc?export=view&id=1hCUKpkABBEfLcHM5MOgAK0i1P760m_Q-)

### 4. Connect to Call
![Connect to Call](https://drive.google.com/uc?export=view&id=1-4UoMa22btP5yUZyvGpfoqJeNxv1YuvV)

### 5. Service Support
![Service Support](https://drive.google.com/uc?export=view&id=1F3GoOLWXBgKkiVsqdavT-0O30NRQwttD)

### 6. Live Agent Chatbot
![Chatbot](https://drive.google.com/uc?export=view&id=1RcEoyrfYKx7GWlcm_t9SoP-KYa2lShgC)

---

## Project Structure

```
sunbun_llm/
├── main.py               ← FastAPI entry point
├── config.py             ← API keys, constants
├── database.py           ← All CSV loading + data helpers
├── session.py            ← In-memory session store
├── llm.py                ← Groq LLM (live agent chat only)
├── routers/
│   ├── __init__.py
│   ├── auth.py           ← /start  /auth/contact  /auth/otp  /auth/retry
│   ├── service.py        ← /service/*
│   ├── sales.py          ← /sales/*
│   └── agent.py          ← /agent/chat  (LLM)
├── data/                 ← All 14 CSV files
│   ├── customers.csv
│   ├── prospects.csv
│   ├── email_otp.csv
│   ├── sms_otp.csv
│   ├── sites.csv
│   ├── site_issues.csv
│   ├── weekly_metrics.csv
│   ├── proposals.csv
│   ├── service_tickets.csv
│   ├── agent_availability.csv
│   ├── component_info.csv
│   ├── crm_opportunities.csv
│   ├── proposal_template__1_.csv
│   └── external_tickets.csv
└── sunbun_ui.html        ← Frontend
```

---

## Run

```bash
pip install fastapi uvicorn langchain-groq langchain-core pandas python-dotenv

# Terminal 1 — backend
cd sunbun_llm
python -m uvicorn main:app --port 8000

# Terminal 2 — frontend
cd sunbun_llm
python -m http.server 3000
```

Then open: **http://127.0.0.1:3000/sunbun_ui.html**

---

## Architecture

- **Backend**: FastAPI with modular routers — fully deterministic state machine, no LLM used except for live agent chat
- **Frontend**: Single-file HTML/CSS/JS — no framework, no build step
- **Data**: 14 CSV files loaded at startup via pandas
- **LLM**: Groq (llama-3.3-70b) used only for live agent chat, lazy-imported so app starts without it
- **Session**: In-memory dict store keyed by session_id generated in the browser

---

## Test Credentials

| Email                       | OTP    | In DB | Has Proposals     |
|-----------------------------|--------|-------|-------------------|
| john.doe@example.com        | 123456 | ✅    | ✅ (301, 307)     |
| jane.smith@example.com      | 654321 | ✅    | ✅ (302, 308)     |
| peter.jones@example.com     | 112233 | ✅    | ❌                |
| mary.williams@example.com   | 445566 | ✅    | ✅ (303, 309)     |
| david.brown@example.com     | 778899 | ✅    | ❌                |
| susan.miller@example.com    | 998877 | ✅    | ✅ (304, 310)     |
| laura.chen@example.com      | 121212 | ✅ prospect | ✅          |
| atr@gmail.com               | —      | ❌    | New prospect      |

| Phone     | OTP    |
|-----------|--------|
| 555-0101  | 123456 |
| 555-0102  | 654321 |
| 555-0103  | 112233 |

---

## Sites with Active Issues (Service Support)

| Customer         | Site | Issue                        |
|------------------|------|------------------------------|
| jane.smith       | 102  | Inverter communication issue |
| david.brown      | 105  | Low production / dust        |
| robert.rodriguez | 109  | System shutdown              |

---

## Admin Endpoints

Once backend is running, view all saved data at:

| URL | Description |
|-----|-------------|
| http://127.0.0.1:8000/docs | Interactive API docs |
| http://127.0.0.1:8000/admin/tickets | All service tickets created |
| http://127.0.0.1:8000/admin/prospects | New users who signed up |
| http://127.0.0.1:8000/admin/crm | Proposal selections |

---

## Bugs Fixed

1. OTP locked state now shows dedicated screen with Retry / Exit options
2. `generate_proposals` is fully deterministic (md5 hash, no `random`)
3. `select_new` returns proper error if proposal ID doesn't match — never crashes
4. `select_old` returns proper error instead of silently failing
5. `site_id` safe conversion handles NaN/None from CSV
6. `_normalize_proposal` cleans all NaN values and always produces `approx_price`
7. `otp_attempts` resets correctly on retry
8. Prospects normalised to customer-like shape so all downstream code works
9. Lazy LLM imports so app starts without langchain installed
10. Home button added to agent chat screen
11. Encoding corruption in router files fixed (ASCII rewrite)
12. All routers register correctly on startup
