from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from datetime import date
import session as sess
import database as db

router = APIRouter(prefix="/service")

class ResolutionReq(BaseModel):
    session_id: str
    happy: bool

class NPSReq(BaseModel):
    session_id: str
    rating: int
    feedback: str = ""

class EscalationReq(BaseModel):
    session_id: str
    category: str
    description: str
    attachments: List[str] = []

class HandoffReq(BaseModel):
    session_id: str
    start_chat: bool

class ExtServiceReq(BaseModel):
    session_id: str
    size: str = ""
    brand: str = ""
    year: str = ""
    monitoring: str = ""
    installer: str = ""
    category: str
    description: str
    attachments: List[str] = []

class SID(BaseModel):
    session_id: str

@router.post("/resolution")
def resolution(r: ResolutionReq):
    s = sess.get(r.session_id)
    s["step"] = "service_nps" if r.happy else "service_escalation"
    return {"step": s["step"]}

@router.post("/nps")
def nps(r: NPSReq):
    s = sess.get(r.session_id)
    s["nps_score"] = r.rating
    s["step"] = "ended"
    return {"step": "ended", "message": "Thank you for your feedback. Have a great day!"}

@router.post("/escalation")
def escalation(r: EscalationReq):
    s = sess.get(r.session_id)
    s["issue_category"] = r.category
    s["issue_description"] = r.description
    s["attachments"] = r.attachments
    agent = db.get_online_agent("Service")
    s["agent_name"] = agent
    if agent:
        s["step"] = "service_agent_offer"
        return {"step": "service_agent_offer", "agent_available": True, "agent_name": agent, "message": f"We have {agent} available right now. Would you like to start a live chat?"}
    return _create_ticket(s)

@router.post("/agent_handoff")
def agent_handoff(r: HandoffReq):
    s = sess.get(r.session_id)
    if r.start_chat:
        from llm import get_agent_reply
        user = s.get("user", {})
        ctx = f"Customer: {user.get('name','Unknown')}. Site ID: {s.get('site_id','N/A')}. Issue: {s.get('issue_category','N/A')}. Description: {s.get('issue_description','N/A')}."
        s["agent_context"] = ctx
        s["in_agent_chat"] = True
        s["agent_chat_history"] = []
        s["step"] = "agent_chat"
        opening = get_agent_reply(s["agent_name"], ctx, [])
        s["agent_chat_history"].append({"role": "assistant", "content": opening})
        return {"step": "agent_chat", "agent_name": s["agent_name"], "opening_message": opening}
    return _create_ticket(s)

@router.post("/external")
def external(r: ExtServiceReq):
    s = sess.get(r.session_id)
    s["ext_data"] = r.dict()
    s["issue_category"] = r.category
    s["issue_description"] = r.description
    s["attachments"] = r.attachments
    agent = db.get_online_agent("Service")
    s["agent_name"] = agent
    if agent:
        s["step"] = "service_agent_offer"
        return {"step": "service_agent_offer", "agent_available": True, "agent_name": agent, "message": f"We have {agent} available right now. Would you like to start a live chat?"}
    return _create_ticket(s)

def _create_ticket(s):
    user = s.get("user", {})
    ticket_id = db.next_ticket_id()
    s["ticket_id"] = ticket_id
    ticket = {"ticket_id": ticket_id, "customer_id": user.get("customer_id", "EXTERNAL"), "site_id": s.get("site_id", ""), "issue_category": s.get("issue_category", ""), "description": s.get("issue_description", ""), "attachments": ", ".join(s.get("attachments", [])), "status": "Open", "date_created": str(date.today())}
    if s.get("ext_data"):
        ext = s["ext_data"]
        ticket.update({"ext_size": ext.get("size",""), "ext_brand": ext.get("brand",""), "ext_year": ext.get("year",""), "ext_installer": ext.get("installer","")})
    db.save_new_ticket(ticket)
    s["step"] = "ended"
    return {"step": "ended", "ticket_id": ticket_id, "message": f"Ticket #{ticket_id} created. Our team will reach out shortly."}
