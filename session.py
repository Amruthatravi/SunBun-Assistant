# session.py — in-memory session store

_store: dict = {}


def new_session() -> dict:
    return {
        "step":              "landing",
        "support_type":      None,
        "id_type":           None,
        "user_contact":      None,
        "otp_correct":       None,
        "otp_attempts":      0,
        "retry_count":       0,
        "in_db":             False,
        "user":              None,
        "_cust":             None,
        "_pros":             None,
        # ── service ──────────────────────────────────
        "site_id":           None,
        "issue_flag":        False,
        "explanation":       "",
        "avg_cloudiness":    0,
        "performance_score": 0,
        "issue_category":    None,
        "issue_description": None,
        "attachments":       [],
        # ── sales ─────────────────────────────────────
        "proposals":         [],
        "selected_proposal": None,
        # ── agent chat ────────────────────────────────
        "in_agent_chat":       False,
        "agent_name":          None,
        "agent_context":       "",
        "agent_chat_history":  [],
        # ── ticket ────────────────────────────────────
        "ticket_id":         None,
        "ext_data":          {},
    }


def get(session_id: str) -> dict:
    if session_id not in _store:
        _store[session_id] = new_session()
    return _store[session_id]


def reset(session_id: str):
    _store[session_id] = new_session()
