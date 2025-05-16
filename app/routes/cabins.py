# app/routes/cabins.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import time
from app import models, database, schemas, auth

router = APIRouter(
    prefix="/cabins",
    tags=["Cabins"]
)

# Admin Only - Create a Cabin
@router.post("/", response_model=schemas.CabinCreate, dependencies=[Depends(auth.verify_admin_user)])
def create_cabin(cabin: schemas.CabinCreate, db: Session = Depends(database.get_db)):
    existing_cabin = db.query(models.Cabin).filter(models.Cabin.name == cabin.name).first()
    if existing_cabin:
        raise HTTPException(status_code=400, detail="Cabin with this name already exists.")

    new_cabin = models.Cabin(
        name=cabin.name,
        description=cabin.description,
        slot_duration=cabin.slot_duration,
        start_time=cabin.start_time,
        end_time=cabin.end_time,
        max_bookings_per_day=cabin.max_bookings_per_day,
        restricted_times=cabin.restricted_times  # ✅ Added this line
    )
    db.add(new_cabin)
    db.commit()
    db.refresh(new_cabin)
    return new_cabin

# Public - List All Cabins
@router.get("/")
def list_cabins(db: Session = Depends(database.get_db)):
    cabins = db.query(models.Cabin).all()
    return cabins

# Admin Only - Update a Cabin
@router.put("/{cabin_id}", dependencies=[Depends(auth.verify_admin_user)])
def update_cabin(cabin_id: int, cabin: schemas.CabinCreate, db: Session = Depends(database.get_db)):
    cabin_to_update = db.query(models.Cabin).filter(models.Cabin.id == cabin_id).first()
    if not cabin_to_update:
        raise HTTPException(status_code=404, detail="Cabin not found")

    cabin_to_update.name = cabin.name
    cabin_to_update.description = cabin.description
    cabin_to_update.slot_duration = cabin.slot_duration
    cabin_to_update.start_time = cabin.start_time or time(9, 0)
    cabin_to_update.end_time = cabin.end_time or time(19, 0)
    cabin_to_update.max_bookings_per_day = cabin.max_bookings_per_day
    cabin_to_update.restricted_times = cabin.restricted_times  # ✅ Added this line

    db.commit()
    db.refresh(cabin_to_update)
    return {"message": "Cabin updated successfully", "cabin": cabin_to_update}

# Admin Only - Delete a Cabin
@router.delete("/{cabin_id}", dependencies=[Depends(auth.verify_admin_user)])
def delete_cabin(cabin_id: int, db: Session = Depends(database.get_db)):
    cabin_to_delete = db.query(models.Cabin).filter(models.Cabin.id == cabin_id).first()
    if not cabin_to_delete:
        raise HTTPException(status_code=404, detail="Cabin not found")

    db.delete(cabin_to_delete)
    db.commit()
    return {"message": "Cabin deleted successfully"}
