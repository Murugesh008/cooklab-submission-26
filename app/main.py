from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db.database import Base, engine
from app.routers import auth, health

# Hackathon-speed schema setup: create tables directly from models on
# startup. No Alembic migrations - fine because there's no real prod data
# to preserve across schema changes during a 16-hour build.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Hackathon API")

# Wide open CORS for hackathon speed. Fine for a demo; tighten if you
# actually ship this somewhere real later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Makes sure a bug returns JSON, not FastAPI/Starlette's default HTML
    # error page - matters if a judge opens dev tools mid-demo.
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health.router)
app.include_router(auth.router)


@app.get("/")
def root():
    return {"message": "API is running. See /docs for interactive API docs."}
