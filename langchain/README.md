# SunBun Solar Assistant — Week 1 LangGraph Implementation

## Project Description

A fully **deterministic state-machine** backend for SunBun's Sales and Service assistant, built with **LangGraph**. Every user interaction is represented as a node; every branching decision is a conditional edge. No LLM is used in Week 1 — all logic is rule-based and CSV-driven.

---

## Architecture

```
sunbun/
├── state.py          ← Typed state dict (single source of truth)
├── data_loader.py    ← Loads all CSVs once at startup
├── nodes.py          ← All graph nodes (deterministic, interrupt-driven)
├── routers.py        ← All conditional edge functions
├── graph.py          ← Assembles & compiles the full LangGraph
├── main.py           ← Interactive terminal runner
├── requirements.txt
└── data/
    ├── customers.csv
    ├── email_otp.csv
    ├── sms_otp.csv
    ├── sites.csv
    ├── site_issues.csv
    ├── weekly_metrics.csv
    ├── service_tickets.csv
    ├── agent_availability.csv
    └── proposals.csv
```

---

## Graph Topology

```
START
  │
  ▼
entry_node          ← Greet + capture support_type (Sales/Service)
  │
  ▼
auth_collect_contact  ← Choose email/phone; enter identifier
  │
  ▼
auth_send_otp         ← Simulate OTP dispatch
  │
  ▼
auth_verify_otp ◄─────────────────────────────────┐
  │                                                │
  ├─ correct OTP ──► customer_lookup               │
  ├─ wrong (< 3 attempts) ──────────────────────► (loop)
  ├─ 3 fails → Retry ──► auth_collect_contact
  └─ 3 fails → Exit  ──► auth_exit_node ──► END

customer_lookup
  ├─ in_db=True, service  ──► service_greet ──► service_status_check
  │                                │
  │                    ┌───────────┴──────────────────┐
  │              needs help?                      resolved?
  │                    │                               │
  │         service_issue_capture         service_nps_and_close ──► END
  │                    │
  │         service_ticket_create ──► END
  │
  ├─ in_db=True, sales  ──► sales_check_proposals
  │                              │
  │                 has_proposals?    or new?
  │                    │                  │
  │         sales_review_proposals    sales_info_capture
  │                    │                  │
  │                chose old?   sales_proposal_generate
  │             yes ──► sales_proposal_confirm ──► END
  │             no  ──► sales_info_capture
  │
  ├─ in_db=False, service ──► service_external_collect
  │                               │
  │                    service_external_ticket ──► END
  │
  ├─ in_db=False, sales ──► sales_not_in_db_intro
  │                               │
  │                        sales_info_capture ──► ... ──► END
  │
  └─ in_db=None (retry) ──► auth_collect_contact
```

---

## Flows Implemented

### Authentication (Shared by Sales + Service)
| Step | What happens |
|------|-------------|
| 1 | User picks email or phone |
| 2 | Enters identifier |
| 3 | OTP simulated (checked against CSV) |
| 4 | Up to 3 attempts; on failure → Retry or Exit |

### Service Support — Existing Customer
| Step | What happens |
|------|-------------|
| 1 | System check: `site_issues.csv` → active issue? |
| 2A | Issue found → show `issue_text` + `recommended_action_text` |
| 2B | No issue → compute avg cloudiness & production from `weekly_metrics.csv` |
| 3 | Ask: happy or need help? |
| 4a | Happy → NPS + feedback → close |
| 4b | Need help → collect category + description + photos → check agent online → ticket |

### Service Support — Not in DB
| Step | What happens |
|------|-------------|
| 1 | Collect system info (size, inverter, year, monitoring, installer) |
| 2 | Collect issue type + description + photos |
| 3 | Check agent online → live chat or external ticket |

### Sales Support — Existing Customer
| Step | What happens |
|------|-------------|
| 1 | Check `proposals.csv` for prior proposals |
| 2a | Review old proposals → pick one → confirm |
| 2b | Generate new → collect profile → deterministic sizing → confirm |
| 3 | Inside Sales handoff (call or chat) |

### Sales Support — New Prospect
- Skips DB lookup, collects all info from scratch, runs same proposal generation.

---

## Key Design Choices

### Why `interrupt()` instead of multiple `graph.invoke()` calls?
`graph.invoke()` runs the entire graph to `END` in one call. Using `interrupt()` inside each node lets the graph **pause at any point**, save a checkpoint, and resume with `Command(resume=answer)` — enabling multi-turn conversations without recursion errors.

### Deterministic Proposal Generation
- Monthly bill → kWh estimate → system size (kW) via fixed tariff (₹8/unit)
- Tier (Premium/Standard/Budget) → fixed component + price-per-kW lookup
- Same inputs always produce same outputs (no randomness, no LLM)

### State as Single Source of Truth
- All state lives in `SunBunState` (TypedDict)
- No globals, no hidden variables
- Every node reads from state and returns only the keys it changed
- LangGraph merges partial updates automatically

### CSV-First Data Access
- All DataFrames loaded once at module import (`data_loader.py`)
- Nodes never reload CSVs mid-session
- Optional MongoDB integration can replace `_load()` calls

---

## How to Run

```bash
# Install dependencies
pip install langgraph langchain-core pandas

# Run the assistant
cd sunbun/
python main.py
```

### Test Credentials (from sample CSVs)

| Identifier | OTP |
|-----------|-----|
| `arjun@example.com` | `123456` |
| `priya@example.com` | `234567` |
| `9876543210` | `111111` |
| `9123456789` | `222222` |

> **Tip:** Use phone `9876543210` with OTP `111111` for the Service Support path with a **known active issue** (site 2 / Priya Sharma has `issue_flag=True`).

---

## Evaluation Checklist

| Criterion | Status |
|-----------|--------|
| OTP loop (3 attempts, retry/exit) | ✅ |
| DB lookup + first-fail retry | ✅ |
| Service: issue flag → direct message | ✅ |
| Service: no issue → weekly metrics analysis | ✅ |
| Service: happy path (NPS + close) | ✅ |
| Service: escalation path (ticket + agent check) | ✅ |
| Service: non-DB external path | ✅ |
| Sales: existing proposals review | ✅ |
| Sales: new proposal generation (deterministic) | ✅ |
| Sales: Inside Sales handoff (call/chat) | ✅ |
| Sales: new prospect path | ✅ |
| Single typed state dict | ✅ |
| No LLM in Week 1 | ✅ |
| Same inputs → same outputs | ✅ |

---

## Limitations & Week 2 Notes
- OTP dispatch is simulated (no real SMS/email gateway)
- Ticket creation is in-memory (not persisted to CSV/DB) — extend `service_ticket_create` to append to `service_tickets.csv`
- CRM opportunity creation is logged to console only
- Week 2: expose graph as Agent Protocol HTTP agent on `/ap/v1/agent/tasks` and `/steps`
