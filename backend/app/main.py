from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.controllers import me

app = FastAPI(title="Hextech Archive API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(me.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
