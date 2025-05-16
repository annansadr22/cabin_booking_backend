# app/routes/bookings.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time
from app import models, database, schemas, auth
from app.dependencies import get_current_user
from sqlalchemy import func

router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"]
)

# ✅ Utility Function: Get IST Time (Display Only)
def get_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# ✅ Parse and build available time windows
def parse_restricted_windows(restricted):
    return sorted([
        (
            datetime.strptime(start.strip(), "%H:%M").time(),
            datetime.strptime(end.strip(), "%H:%M").time()
        )
        for slot in restricted
        for start, end in [slot.split("-")]
    ])

def build_allowed_ranges(start: time, end: time, blocked):
    allowed = []
    current = start

    for b_start, b_end in blocked:
        if current < b_start:
            allowed.append((current, b_start))
        current = max(current, b_end)

    if current < end:
        allowed.append((current, end))

    return allowed

# ✅ Generate slots from allowed time windows (respecting slot duration but allowing smaller)
def generate_slots(day, allowed_ranges, duration):
    slots = []
    for start_time, end_time in allowed_ranges:
        current = datetime.combine(day, start_time)
        end = datetime.combine(day, end_time)

        while current < end:
            slot_end = current + timedelta(minutes=duration)
            if slot_end <= end:
                slots.append((current, duration))
                current = slot_end
            else:
                # Add remaining as a partial slot
                remaining = int((end - current).total_seconds() // 60)
                if remaining > 0:
                    slots.append((current, remaining))
                break
    return slots

# ✅ List Available Slots for a Cabin (Today and Tomorrow - Only Future Slots)
@router.get("/{cabin_id}/available-slots")
def list_available_slots(cabin_id: int, db: Session = Depends(database.get_db)):
    cabin = db.query(models.Cabin).filter(models.Cabin.id == cabin_id).first()
    if not cabin:
        raise HTTPException(status_code=404, detail="Cabin not found")

    active_bookings = db.query(models.Booking).filter(
        models.Booking.cabin_id == cabin_id,
        models.Booking.status == "Active"
    ).all()

    booked_slots_info = {}
    for booking in active_bookings:
        slot_key = booking.slot_time.strftime("%Y-%m-%d %H:%M")
        booked_slots_info[slot_key] = {
            "username": booking.user.username,
            "employee_id": booking.user.employee_id
        }

    now = get_ist_time()
    restricted = parse_restricted_windows(cabin.restricted_times or [])
    available_slots = {}
    restricted_slots = {}

    for offset in range(2):
        day = (now + timedelta(days=offset)).date()
        allowed_ranges = build_allowed_ranges(cabin.start_time, cabin.end_time, restricted)
        slots = generate_slots(day, allowed_ranges, cabin.slot_duration)

        # ✅ Build daily available slot list
        daily_slots = []
        for start_time, actual_duration in slots:
            slot_str = start_time.strftime("%Y-%m-%d %H:%M")
            if slot_str in booked_slots_info:
                daily_slots.append(f"{slot_str} (Booked)")
            elif start_time < now:
                daily_slots.append(f"{slot_str} (Past)")
            else:
                daily_slots.append(f"{slot_str} ({actual_duration} min)")

        available_slots[day.strftime("%Y-%m-%d")] = daily_slots

        # ✅ Build restricted slot start-times (e.g., 13:30)
        # Build actual restricted ranges per day (for frontend display)
        restricted_ranges = [
            (
                datetime.combine(day, start).strftime("%Y-%m-%d %H:%M"),
                datetime.combine(day, end).strftime("%Y-%m-%d %H:%M")
            )
            for start, end in restricted
        ]
        restricted_slots[day.strftime("%Y-%m-%d")] = restricted_ranges

    print(restricted_slots)


    return {
    "cabin_name": cabin.name,
    "available_slots": available_slots,
    "booked_slots_info": booked_slots_info,
    "restricted_slots": restricted_slots,  # ✅ NEW
    "slot_duration": cabin.slot_duration  # ✅ ADD THIS
    }


# ✅ Book a Selected Available Slot (in UTC)
@router.post("/{cabin_id}/book-selected-slot")
def book_selected_slot(
    cabin_id: int,
    booking_data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    selected_slot = booking_data.get("selected_slot")
    duration = booking_data.get("duration")

    if not selected_slot or not isinstance(duration, int) or duration <= 0:
        raise HTTPException(status_code=400, detail="Valid duration must be a positive number")


    cabin = db.query(models.Cabin).filter(models.Cabin.id == cabin_id).first()
    if not cabin:
        raise HTTPException(status_code=404, detail="Cabin not found")

    try:
        slot_time = datetime.strptime(selected_slot, "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid slot time format. Use 'YYYY-MM-DD HH:MM'")

    slot_date = slot_time.date()
    start_of_day = datetime.combine(slot_date, datetime.min.time())
    end_of_day = datetime.combine(slot_date, datetime.max.time())

    user_bookings_today = db.query(models.Booking).filter(
        models.Booking.user_id == current_user.id,
        models.Booking.status == "Active",
        models.Booking.slot_time >= start_of_day,
        models.Booking.slot_time <= end_of_day
    ).count()

    if user_bookings_today >= 1:
        raise HTTPException(status_code=403, detail="Booking limit reached: You can only book 1 slot per day.")

    existing_booking = db.query(models.Booking).filter(
        models.Booking.cabin_id == cabin_id,
        models.Booking.slot_time == slot_time,
        models.Booking.status == "Active"
    ).first()

    if existing_booking:
        raise HTTPException(status_code=400, detail="Selected slot is already booked")

    new_booking = models.Booking(
        user_id=current_user.id,
        cabin_id=cabin_id,
        slot_time=slot_time,
        duration=duration,
        status="Active"
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    return {
        "message": "Selected slot booked successfully",
        "booking_details": {
            "cabin": cabin.name,
            "slot_time": slot_time,
            "duration": duration
        }
    }

# ✅ List User Bookings (Active and Past with Cabin Names)
@router.get("/my-bookings")
def list_user_bookings(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    now = get_ist_time()

    active_bookings = db.query(
        models.Booking.id,
        models.Booking.cabin_id,
        models.Booking.user_id,
        models.Booking.slot_time,
        models.Booking.duration,
        models.Booking.status,
        models.Cabin.name.label("cabin_name")
    ).join(models.Cabin, models.Booking.cabin_id == models.Cabin.id).filter(
        models.Booking.user_id == current_user.id,
        models.Booking.status == "Active",
        models.Booking.slot_time >= now
    ).all()

    past_bookings = db.query(
        models.Booking.id,
        models.Booking.cabin_id,
        models.Booking.user_id,
        models.Booking.slot_time,
        models.Booking.duration,
        models.Booking.status,
        models.Cabin.name.label("cabin_name")
    ).join(models.Cabin, models.Booking.cabin_id == models.Cabin.id).filter(
        models.Booking.user_id == current_user.id,
        models.Booking.slot_time < now
    ).all()

    def format_bookings(bookings):
        return [
            {
                "id": booking.id,
                "cabin_id": booking.cabin_id,
                "user_id": booking.user_id,
                "slot_time": booking.slot_time,
                "duration": booking.duration,
                "status": booking.status,
                "cabin_name": booking.cabin_name
            }
            for booking in bookings
        ]

    return {
        "user": current_user.username,
        "active_bookings": format_bookings(active_bookings),
        "past_bookings": format_bookings(past_bookings)
    }

# ✅ Cancel User Booking (Active Only)
@router.delete("/{booking_id}/cancel")
def cancel_user_booking(
    booking_id: int, 
    db: Session = Depends(database.get_db), 
    current_user: models.User = Depends(get_current_user)
):
    booking = db.query(models.Booking).filter(
        models.Booking.id == booking_id,
        models.Booking.user_id == current_user.id,
        models.Booking.status == "Active"
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found or already cancelled")

    booking.status = "Cancelled"
    db.commit()
    return {"message": "Your booking has been cancelled successfully"}

# ✅ Admin - List All Bookings
@router.get("/admin/all-bookings", dependencies=[Depends(auth.verify_admin_user)])
def list_all_bookings(
    user_id: int = None,
    cabin_id: int = None,
    status: str = None,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(database.get_db)
):
    query = db.query(
        models.Booking.id,
        models.Booking.user_id,
        models.Booking.cabin_id,
        models.Booking.slot_time,
        models.Booking.duration,
        models.Booking.status,
        models.User.username.label("user_name"),
        models.Cabin.name.label("cabin_name")
    ).join(models.User, models.Booking.user_id == models.User.id)\
     .join(models.Cabin, models.Booking.cabin_id == models.Cabin.id)

    if user_id:
        query = query.filter(models.Booking.user_id == user_id)
    if cabin_id:
        query = query.filter(models.Booking.cabin_id == cabin_id)
    if status:
        query = query.filter(models.Booking.status == status)
    if start_date:
        query = query.filter(models.Booking.slot_time >= start_date)
    if end_date:
        query = query.filter(models.Booking.slot_time <= end_date)

    bookings = query.all()

    bookings_data = [
        {
            "id": booking.id,
            "user_id": booking.user_id,
            "user_name": booking.user_name,
            "cabin_id": booking.cabin_id,
            "cabin_name": booking.cabin_name,
            "slot_time": booking.slot_time,
            "duration": booking.duration,
            "status": booking.status,
        }
        for booking in bookings
    ]

    return {"all_bookings": bookings_data}

# ✅ Admin - Delete Any Booking
@router.delete("/admin/{booking_id}/delete", dependencies=[Depends(auth.verify_admin_user)])
def admin_delete_booking(
    booking_id: int, 
    db: Session = Depends(database.get_db)
):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    db.delete(booking)
    db.commit()
    return {"message": "Booking deleted successfully by Admin"}