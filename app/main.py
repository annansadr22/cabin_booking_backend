# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import users, cabins, bookings

# Create the database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Cabin Booking System",
    description="An internal cabin booking system for efficient usage",
    version="1.0.0"
)

# CORS Middleware (Adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registering Routers
app.include_router(users.router)
app.include_router(cabins.router)
app.include_router(bookings.router)

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to the Cabin Booking System"}
