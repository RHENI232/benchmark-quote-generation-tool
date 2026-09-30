from fastapi import FastAPI
from backend.app.api.routers import auth, users, solutions, catalog

app = FastAPI(title="Benchmark Quote Generation API")

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(solutions.router, prefix="/api/solutions", tags=["Solutions"])
app.include_router(catalog.router, prefix="/api/catalog", tags=["Catalog"])
