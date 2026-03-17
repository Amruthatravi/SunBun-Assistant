from fastapi import APIRouter
from pydantic import BaseModel
import session as sess
import database as db

router = APIRouter()

class StartReq(BaseModel):
    session_id: str
    support_type: str

class ContactReq(BaseModel):
    session_id: str
    id_type: str
    contact: str

class OTPReq(BaseModel):
    session_id: str
    otp: str

class SID(BaseModel):
    session_id: str

@router.post("/start")
def start(r: StartReq):
    s = sess.get(r.session_id)
    s["support_type"] = r.support_type
    s["step"] = "auth_choose_id"
    return {"step": "auth_choose_id"}

@router.post("/auth/contact")
def auth_contact(r: ContactReq):
    s = sess.get(r.session_id)
    s["id_type"] = r.id_type
    s["user_contact"] = r.contact.strip()
    cust, pros = db.lookup_user(r.id_type, r.contact)
    s["_cust"] = cust
    s["_pros"] = pros
    otp = db.get_otp(r.id_type, r.contact)
    s["otp_correct"] = otp
    s["otp_attempts"] = 0
    s["step"] = "auth_otp"
    return {"step": "auth_otp", "dev_otp": otp, "message": f"We've sent a one-time code to your {r.id_type}."}

@router.post("/auth/otp")
def auth_otp(r: OTPReq):
    s = sess.get(r.session_id)
    entered = r.otp.strip()
    correct = str(s.get("otp_correct", "")).strip()
    s["otp_attempts"] = s.get("otp_attempts", 0) + 1
    if entered != correct:
        remaining = 3 - s["otp_attempts"]
        if remaining <= 0:
            s["step"] = "auth_locked"
            return {"verified": False, "locked": True, "step": "auth_locked", "message": "3 failed attempts."}
        return {"verified": False, "locked": False, "remaining": remaining, "message": f"Incorrect code. {remaining} attempt(s) remaining."}
    cust = s.get("_cust")
    pros = s.get("_pros")
    if cust:
        s["user"] = cust
        s["in_db"] = True
    elif pros:
        s["user"] = pros
        s["in_db"] = True
    else:
        s["in_db"] = False
        s["user"] = {"customer_id": "NEW", "name": "Valued Customer", "has_proposals": False, "email": s["user_contact"] if s["id_type"] == "email" else "", "phone": s["user_contact"] if s["id_type"] == "phone" else "", "location": "", "site_id": None}
    return _route_after_auth(s)

@router.post("/auth/retry")
def auth_retry(r: SID):
    s = sess.get(r.session_id)
    s["retry_count"] = s.get("retry_count", 0) + 1
    s["otp_attempts"] = 0
    s["otp_correct"] = None
    s["step"] = "auth_choose_id"
    return {"step": "auth_choose_id", "retry_count": s["retry_count"]}

def _route_after_auth(s):
    user = s["user"]
    support = s["support_type"]
    if not s["in_db"]:
        if support == "service":
            s["step"] = "service_not_found"
            return {"verified": True, "in_db": False, "step": "service_not_found", "message": "No system found.", "retry_count": s.get("retry_count", 0)}
        else:
            s["step"] = "sales_new_proposal"
            return {"verified": True, "in_db": False, "step": "sales_new_proposal", "message": "No account found.", "user": user}
    if support == "service":
        raw_site = user.get("site_id")
        try:
            site_id = int(float(str(raw_site))) if raw_site and str(raw_site).strip() not in ("", "nan", "None") else None
        except Exception:
            site_id = None
        mon = db.get_monitoring(site_id)
        s.update({"site_id": site_id, "issue_flag": mon["issue_flag"], "explanation": mon["explanation"], "avg_cloudiness": mon["avg_cloudiness"], "performance_score": mon["performance_score"], "step": "service_diagnosis"})
        return {"verified": True, "in_db": True, "step": "service_diagnosis", "user": user, "monitoring": mon}
    has = db.is_has_proposals(user.get("has_proposals", False))
    past = db.get_past_proposals(user.get("customer_id")) if has else []
    s["step"] = "sales_has_proposals" if has else "sales_new_proposal"
    return {"verified": True, "in_db": True, "step": s["step"], "user": user, "has_proposals": has, "past_proposals": past}
