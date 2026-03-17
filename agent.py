from fastapi import APIRouter
from pydantic import BaseModel
import session as sess

router = APIRouter(prefix="/agent")

class AgentMsgReq(BaseModel):
    session_id: str
    message: str

@router.post("/chat")
def agent_chat(r: AgentMsgReq):
    s = sess.get(r.session_id)
    if not s.get("in_agent_chat"):
        return {"error": "No active agent chat."}
    from llm import get_agent_reply
    history = s["agent_chat_history"]
    history.append({"role": "user", "content": r.message})
    reply = get_agent_reply(s.get("agent_name", "Agent"), s.get("agent_context", ""), history)
    history.append({"role": "assistant", "content": reply})
    s["agent_chat_history"] = history
    return {"reply": reply, "agent_name": s.get("agent_name")}