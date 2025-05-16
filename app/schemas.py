# app/schemas.py
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import time, datetime

class UserCreate(BaseModel):
    username: str
    employee_id: str
    email: EmailStr
    password: str
    employee_id: str

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
    restricted_times: Optional[List[str]] = []  # New

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

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    new_password: str