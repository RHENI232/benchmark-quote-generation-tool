from fastapi import FastAPI
from backend.app.api.routers import auth, users

app = FastAPI(title="Benchmark Quote Generation API")

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
