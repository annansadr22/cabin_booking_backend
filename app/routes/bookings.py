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

# User - Book a Cabin
@router.post("/")
def book_cabin(booking: schemas.BookingCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    # Check if cabin exists
    cabin = db.query(models.Cabin).filter(models.Cabin.id == booking.cabin_id).first()
    if not cabin:
        raise HTTPException(status_code=404, detail="Cabin not found")

    # Restrict to 7 days
    if booking.slot_time.date() > (datetime.now() + timedelta(days=7)).date():
        raise HTTPException(status_code=400, detail="You can only book for the next 7 days")

    # Check existing bookings for the same time slot
    overlapping_bookings = db.query(models.Booking).filter(
        models.Booking.cabin_id == booking.cabin_id,
        models.Booking.slot_time == booking.slot_time,
        models.Booking.status == "Active"
    ).count()

    if overlapping_bookings >= cabin.max_bookings_per_day:
        raise HTTPException(status_code=403, detail="This cabin is fully booked for the selected slot")

    # Create the booking
    new_booking = models.Booking(
        user_id=current_user.id,
        cabin_id=booking.cabin_id,
        slot_time=booking.slot_time,
        duration=booking.duration,
        status="Active"
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    return new_booking

# User - List User Bookings (Active and Past)
@router.get("/")
def list_user_bookings(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    active_bookings = db.query(models.Booking).filter(
        models.Booking.user_id == current_user.id,
        models.Booking.status == "Active",
        models.Booking.slot_time >= datetime.now()
    ).all()

    past_bookings = db.query(models.Booking).filter(
        models.Booking.user_id == current_user.id,
        models.Booking.slot_time < datetime.now()
    ).all()

    return {
        "active_bookings": active_bookings,
        "past_bookings": past_bookings
    }


# ✅ List Available Slots for a Cabin (Today and Tomorrow - Only Future Slots)
@router.get("/{cabin_id}/available-slots")
def list_available_slots(cabin_id: int, db: Session = Depends(database.get_db)):
    cabin = db.query(models.Cabin).filter(models.Cabin.id == cabin_id).first()
    if not cabin:
        raise HTTPException(status_code=404, detail="Cabin not found")

    # Get all active bookings for this cabin (Today and Tomorrow)
    active_bookings = db.query(models.Booking).filter(
        models.Booking.cabin_id == cabin_id,
        models.Booking.status == "Active",
        models.Booking.slot_time >= datetime.now(),
        models.Booking.slot_time <= (datetime.now() + timedelta(days=1))
    ).all()
    
    # Calculate available slots for today and tomorrow
    available_slots = {}
    now = datetime.now()  # Current time to avoid past time slots
    for day_offset in range(2):  # For today and tomorrow
        day = (now + timedelta(days=day_offset)).date()
        current_time = datetime.combine(day, cabin.start_time)
        end_time = datetime.combine(day, cabin.end_time)
        daily_slots = []

        while current_time < end_time:
            # Skip past slots for today
            if day == now.date() and current_time <= now:
                current_time += timedelta(minutes=cabin.slot_duration)
                continue

            # Check if the slot is already booked
            slot_available = True
            for booking in active_bookings:
                if booking.slot_time == current_time:
                    slot_available = False
                    break
            
            if slot_available:
                daily_slots.append(current_time.strftime("%Y-%m-%d %H:%M"))

            current_time += timedelta(minutes=cabin.slot_duration)

        # Add the date to available slots even if empty
        available_slots[day.strftime("%Y-%m-%d")] = daily_slots if daily_slots else []

    return {
        "cabin_name": cabin.name,
        "available_slots": available_slots
    }



# ✅ Book a Selected Available Slot (Today and Tomorrow Only)
@router.post("/{cabin_id}/book-selected-slot")
def book_selected_slot(
    cabin_id: int, 
    booking_data: dict,  # JSON payload for slot selection
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

    # Convert selected_slot to datetime object
    try:
        slot_time = datetime.strptime(selected_slot, "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid slot time format. Use 'YYYY-MM-DD HH:MM'")

    # Ensure the slot is within today and tomorrow
    now = datetime.now()
    if not (now.date() <= slot_time.date() <= (now + timedelta(days=1)).date()):
        raise HTTPException(status_code=400, detail="You can only book slots for today or tomorrow")

    # Ensure slot is within the cabin's active hours
    if slot_time.time() < cabin.start_time or slot_time.time() >= cabin.end_time:
        raise HTTPException(status_code=400, detail="Slot time must be within cabin's active hours")

    # Ensure slot is one of the available slots
    available_slots = list_available_slots(cabin_id, db)["available_slots"]
    selected_day = slot_time.strftime("%Y-%m-%d")

    if selected_day not in available_slots or selected_slot not in available_slots[selected_day]:
        raise HTTPException(status_code=400, detail="Selected slot is not available")

    # Book the Selected Slot with Fixed Duration
    new_booking = models.Booking(
        user_id=current_user.id,
        cabin_id=cabin_id,
        slot_time=slot_time,
        duration=cabin.slot_duration,  # Automatically use cabin's fixed duration
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
        models.Booking.slot_time >= datetime.now()
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
        models.Booking.slot_time < datetime.now()
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