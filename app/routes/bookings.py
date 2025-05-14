# app/routes/bookings.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app import models, database, schemas, auth
from app.dependencies import get_current_user

router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"]
)

# ✅ Utility Function: Get IST Time (Display Only)
def get_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# ✅ List Available Slots for a Cabin (Today and Tomorrow - Only Future Slots)
@router.get("/{cabin_id}/available-slots")
def list_available_slots(cabin_id: int, db: Session = Depends(database.get_db)):
    cabin = db.query(models.Cabin).filter(models.Cabin.id == cabin_id).first()
    if not cabin:
        raise HTTPException(status_code=404, detail="Cabin not found")

    # ✅ Get all active bookings for this cabin with related user info
    active_bookings = db.query(models.Booking).filter(
        models.Booking.cabin_id == cabin_id,
        models.Booking.status == "Active"
    ).all()

    # ✅ Build map: slot time (string) → user info
    booked_slots_info = {}
    for booking in active_bookings:
        slot_key = booking.slot_time.strftime("%Y-%m-%d %H:%M")
        booked_slots_info[slot_key] = {
            "username": booking.user.username,
            "employee_id": booking.user.employee_id
        }

    # ✅ Prepare display slot structure (Today & Tomorrow)
    available_slots = {}
    now = get_ist_time()

    for day_offset in range(2):  # today and tomorrow
        day = (now + timedelta(days=day_offset)).date()
        current_time = datetime.combine(day, cabin.start_time)
        end_time = datetime.combine(day, cabin.end_time)
        daily_slots = []

        while current_time < end_time:
            slot_str = current_time.strftime("%Y-%m-%d %H:%M")

            if slot_str in booked_slots_info:
                daily_slots.append(f"{slot_str} (Booked)")
            elif current_time < now:
                daily_slots.append(f"{slot_str} (Past)")
            else:
                daily_slots.append(slot_str)

            current_time += timedelta(minutes=cabin.slot_duration)

        available_slots[day.strftime("%Y-%m-%d")] = daily_slots

    return {
        "cabin_name": cabin.name,
        "available_slots": available_slots,
        "booked_slots_info": booked_slots_info  # ✅ new: contains user info
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
    
    if not selected_slot:
        raise HTTPException(status_code=400, detail="Selected slot is required")

    # Validate Cabin
    cabin = db.query(models.Cabin).filter(models.Cabin.id == cabin_id).first()
    if not cabin:
        raise HTTPException(status_code=404, detail="Cabin not found")

    # Convert selected_slot to UTC (remove IST handling)
    try:
        slot_time = datetime.strptime(selected_slot, "%Y-%m-%d %H:%M")  # This is in UTC
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid slot time format. Use 'YYYY-MM-DD HH:MM'")

    # Check if slot is already booked
    existing_booking = db.query(models.Booking).filter(
        models.Booking.cabin_id == cabin_id,
        models.Booking.slot_time == slot_time,
        models.Booking.status == "Active"
    ).first()

    if existing_booking:
        raise HTTPException(status_code=400, detail="Selected slot is already booked")

    # Book the Selected Slot
    new_booking = models.Booking(
        user_id=current_user.id,
        cabin_id=cabin_id,
        slot_time=slot_time,  # Storing in UTC
        duration=cabin.slot_duration,
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
            "duration": cabin.slot_duration
        }
    }

# ✅ List User Bookings (Active and Past with Cabin Names)
@router.get("/my-bookings")
def list_user_bookings(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    now = get_ist_time()  # Current IST time

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

    # Formatting the response to include cabin_name
    def format_bookings(bookings):
        return [
            {
                "id": booking.id,
                "cabin_id": booking.cabin_id,
                "user_id": booking.user_id,
                "slot_time": booking.slot_time,
                "duration": booking.duration,
                "status": booking.status,
                "cabin_name": booking.cabin_name  # Include cabin name
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

    # Mark the booking as cancelled
    booking.status = "Cancelled"
    db.commit()
    return {"message": "Your booking has been cancelled successfully"}



######
#Admin
# ✅ List All Bookings (Admin Only - with User and Cabin Names)
@router.get("/admin/all-bookings", dependencies=[Depends(auth.verify_admin_user)])
def list_all_bookings(
    user_id: int = None,
    cabin_id: int = None,
    status: str = None,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(database.get_db)
):
    # Start with the base query
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

    # Apply filters dynamically
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
    
    # Convert to a list of dicts for JSON serialization
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