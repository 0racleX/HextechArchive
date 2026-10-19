from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.controllers import chat, documents, history, me

app = FastAPI(title="Hextech Archive API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(me.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(history.router)


@app.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "auth_configured": bool(settings.supabase_jwks_url or settings.supabase_jwt_secret)}
