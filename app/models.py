# app/models.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Time
from sqlalchemy.orm import relationship
from app.database import Base
import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)  # <-- Changed to 'password' (Consistent with registration)
    is_admin = Column(Boolean, default=False)

class Cabin(Base):
    __tablename__ = "cabins"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    slot_duration = Column(Integer, default=30)
    start_time = Column(Time, default=datetime.time(9, 0))
    end_time = Column(Time, default=datetime.time(19, 0))
    max_bookings_per_day = Column(Integer, default=1)

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    cabin_id = Column(Integer, ForeignKey("cabins.id"))
    slot_time = Column(DateTime)
    duration = Column(Integer)
    status = Column(String, default="Active")
