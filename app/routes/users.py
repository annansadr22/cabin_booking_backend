# app/routes/users.py
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from app import models, schemas, database, auth

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

# ✅ User Registration (Normal User)
@router.post("/register")
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(
        username=user.username,
        email=user.email,
        password=hashed_password,
        is_admin=False  # Normal User by Default
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully"}

# ✅ Admin Registration (Admin Only - Protected)
@router.post("/admin/register", dependencies=[Depends(auth.verify_admin_user)])
def register_admin(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = auth.get_password_hash(user.password)
    new_admin = models.User(
        username=user.username,
        email=user.email,
        password=hashed_password,
        is_admin=True  # Automatically set as Admin
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    return {"message": f"Admin {new_admin.email} registered successfully"}

# ✅ User Login (Regular User - JWT)
@router.post("/login")
def login_user(user: schemas.UserLogin, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not auth.verify_password(user.password, db_user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Create JWT token with admin status (Ensure is_admin is included)
    access_token = auth.create_access_token(data={
        "sub": db_user.email,
        "is_admin": db_user.is_admin  # Include is_admin flag in the token
    })
    return {"access_token": access_token, "token_type": "bearer"}

# ✅ Admin Login (Secure and Detailed Error Handling)
@router.post("/admin-login")
def admin_login(user: schemas.UserLogin, db: Session = Depends(database.get_db)):
    # ✅ Check if the user exists
    db_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid credentials. Please check your email and password."
        )

    # ✅ Ensure the user is an admin
    if not db_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access denied. Only admins can log in here."
        )

    # ✅ Verify password
    if not auth.verify_password(user.password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid credentials. Please check your email and password."
        )

    # ✅ Generate JWT Token
    access_token = auth.create_access_token(data={
        "sub": db_user.email,
        "is_admin": db_user.is_admin  # Include is_admin flag in the token
    })

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": db_user.username,
        "email": db_user.email
    }
