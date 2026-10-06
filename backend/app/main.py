from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.routers import auth, users, solutions, catalog, quotes, regions

app = FastAPI(title="Benchmark Quote Generation API")

# Configure CORS
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(solutions.router, prefix="/api/solutions", tags=["Solutions"])
app.include_router(catalog.router, prefix="/api/catalog", tags=["Catalog"])
app.include_router(regions.router, prefix="/api/regions", tags=["Regions"])
app.include_router(quotes.router, prefix="/api", tags=["Quotes"])
