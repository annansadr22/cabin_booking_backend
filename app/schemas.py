# app/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import time, datetime

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class CabinCreate(BaseModel):
    name: str
    description: str
    slot_duration: int
    start_time: time = time(9, 0)  # Default to 9:00 AM
    end_time: time = time(19, 0)  # Default to 7:00 PM
    max_bookings_per_day: int

class BookingCreate(BaseModel):
    cabin_id: int
    slot_time: datetime
    duration: int


class BookingResponse(BaseModel):
    id: int
    user_id: int
    cabin_id: int
    slot_time: datetime
    duration: int
    status: str