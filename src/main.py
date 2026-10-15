from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.v1.router import api_router
from src.models import get_db

app = FastAPI(title="Beako API")

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
