# routers/sales.py — /sales/*

from fastapi import APIRouter
from pydantic import BaseModel

import session as sess
import database as db

router = APIRouter(prefix="/sales")


class ProposalReq(BaseModel):
    session_id:  str
    name:        str  = ""
    postal_code: str  = ""
    city:        str  = ""
    email:       str  = ""
    phone:       str  = ""
    segment:     str
    bill:        float
    increase:    float = 0.0
    num_options: int   = 1
    brand_pref:  str  = ""
    tier_pref:   str  = ""

class SelectReq(BaseModel):
    session_id:  str
    proposal_id: int

class ContactPrefReq(BaseModel):
    session_id: str
    pref:       str    # "chat" | "call" | "offline"


# ── Routes ────────────────────────────────────

@router.post("/proposal")
def new_proposal(r: ProposalReq):
    """Collect sales info and generate deterministic proposals."""
    s    = sess.get(r.session_id)
    user = s.get("user", {})

    bill = max(float(r.bill), 1.0)
    inc  = float(r.increase) if r.increase else 0.0
    num  = max(1, min(3, r.num_options))

    proposals = db.generate_proposals(
        r.city, r.segment, bill, inc, num, r.brand_pref, r.tier_pref
    )
    s["proposals"] = proposals
    s["step"]      = "sales_show_proposals"

    # Update user contact info if new prospect
    if user.get("customer_id") == "NEW":
        if r.name:  user["name"]  = r.name
        if r.email: user["email"] = r.email
        if r.phone: user["phone"] = r.phone

    return {"step": "sales_show_proposals", "proposals": proposals}


@router.post("/select_old")
def select_old_proposal(r: SelectReq):
    """User picks one of their existing proposals from the DB."""
    s    = sess.get(r.session_id)
    prop = db.get_proposal_by_id(r.proposal_id)

    if not prop:
        return {"error": f"Proposal ID {r.proposal_id} not found in database."}

    s["selected_proposal"] = prop
    agent = db.get_online_agent("Sales")
    s["agent_name"] = agent
    s["step"]       = "sales_confirm"

    return {
        "step":              "sales_confirm",
        "selected_proposal": prop,
        "agent_available":   agent is not None,
        "agent_name":        agent,
    }


@router.post("/select_new")
def select_new_proposal(r: SelectReq):
    """User picks one of the freshly generated proposals."""
    s    = sess.get(r.session_id)
    prop = next(
        (p for p in s.get("proposals", []) if p["proposal_id"] == r.proposal_id),
        None
    )

    if not prop:
        valid = [p["proposal_id"] for p in s.get("proposals", [])]
        return {"error": f"Proposal ID {r.proposal_id} not found. Valid IDs: {valid}"}

    s["selected_proposal"] = prop
    agent = db.get_online_agent("Sales")
    s["agent_name"] = agent
    s["step"]       = "sales_confirm"

    return {
        "step":              "sales_confirm",
        "selected_proposal": prop,
        "agent_available":   agent is not None,
        "agent_name":        agent,
    }


@router.post("/contact_pref")
def contact_pref(r: ContactPrefReq):
    """
    User chose Call / Chat / Offline after selecting proposal.
    Chat → opens LLM live chat.
    Call / Offline → log and end session.
    """
    from llm import get_agent_reply

    s     = sess.get(r.session_id)
    user  = s.get("user", {})
    prop  = s.get("selected_proposal", {})
    agent = s.get("agent_name")

    if r.pref == "chat" and agent:
        ctx = (
            f"Customer: {user.get('name', 'Customer')}. "
            f"Interested in: {prop.get('proposal_name', 'N/A')}. "
            f"System size: {prop.get('system_size_kw', 'N/A')} kW. "
            f"Price: {prop.get('approx_price', 'N/A')}. "
            f"Monthly savings: ${prop.get('monthly_savings', 0)}."
        )
        s["agent_context"]      = ctx
        s["in_agent_chat"]      = True
        s["agent_chat_history"] = []
        s["step"]               = "agent_chat"

        opening = get_agent_reply(agent, ctx, [])
        s["agent_chat_history"].append({"role": "assistant", "content": opening})

        return {
            "step":            "agent_chat",
            "agent_name":      agent,
            "opening_message": opening,
        }

    # Call or offline
    s["step"] = "ended"
    prop_name = prop.get("proposal_name", "your proposal")
    if r.pref == "call":
        msg = (
            f"A task has been created for {agent or 'our team'} to call you about "
            f"'{prop_name}' within 1 hour."
        )
    else:
        msg = (
            f"We've logged your interest in '{prop_name}'. "
            f"Our team will be in touch soon."
        )

    return {"step": "ended", "message": msg}
