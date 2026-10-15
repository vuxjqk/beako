from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.v1.router import api_router
from src.models import get_db
from src.storage import get_storage

app = FastAPI(title="Beako API")

app.include_router(api_router, prefix="/api/v1")

# Serves files saved by LocalStorage; remove when switching to an external storage
app.mount("/media", StaticFiles(directory=get_storage().root), name="media")


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
