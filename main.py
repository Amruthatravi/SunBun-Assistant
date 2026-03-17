from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import session as sess

app = FastAPI(title="SunBun Solar Assistant API", version="4.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

try:
    from routers import auth, service, sales, agent
    app.include_router(auth.router)
    app.include_router(service.router)
    app.include_router(sales.router)
    app.include_router(agent.router)
    print("[OK] All routers registered")
except Exception as e:
    print(f"[ERROR] Failed to load routers: {e}")
    raise

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/routes")
def list_routes():
    return [{"path": r.path, "methods": list(r.methods)} for r in app.routes]

class SID(BaseModel):
    session_id: str

@app.post("/reset")
def reset(r: SID):
    sess.reset(r.session_id)
    return {"status": "reset"}