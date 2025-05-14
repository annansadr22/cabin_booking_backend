# app/routes/users.py
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from app import models, schemas, database, auth
from datetime import datetime, timedelta
from jose import jwt, JWTError, ExpiredSignatureError
from app.config import settings
import smtplib
from email.message import EmailMessage
from app.schemas import ForgotPasswordRequest
from app.database import get_db
from app.schemas import ResetPasswordRequest


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

# ✅ Function to generate verification token
def generate_verification_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=30)
    payload = {"sub": email, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def send_email(to_email: str, verification_url: str):
    msg = EmailMessage()
    msg["Subject"] = "Verify Your Email - Cabin Booking System"
    msg["From"] = settings.SMTP_EMAIL
    msg["To"] = to_email
    msg.set_content(f"Hello!\n\nClick the link to verify your email:\n{verification_url}\n\nIf you didn’t sign up, ignore this email.")

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
        print(f"✅ Verification email sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")




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
        employee_id=user.employee_id,
        is_admin=False  # Normal User by Default
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 🔗 Send verification link
    token = generate_verification_token(user.email)
    verify_url = f"{settings.FRONTEND_BASE_URL}/user/verify-email?token={token}"
    send_email(user.email, verify_url)

    return {"message": "User registered. Please verify your email."}

# ✅ Email Verification Route
@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(database.get_db)):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        email = payload.get("sub")
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_verified = True
        db.commit()
        return {"message": "✅ Email verified successfully!"}
    except ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid token")

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

    # 🚫 Block unverified users
    if not db_user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified. Please check your inbox.")

    access_token = auth.create_access_token(data={
        "sub": db_user.email,
        "is_admin": db_user.is_admin
    })
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": db_user.username,
        "email": db_user.email
    }

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


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = payload.email
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = auth.generate_reset_token(email)
    reset_url = f"{settings.FRONTEND_BASE_URL}/user/reset-password?token={token}"
    auth.send_reset_email(email, reset_url)

    return {"message": "Password reset link sent to your email"}


@router.post("/reset-password")
def reset_password(
    token: str,
    payload: ResetPasswordRequest,
    db: Session = Depends(database.get_db)
):
    try:
        payload_data = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        email = payload_data.get("sub")
        if not email:
            raise HTTPException(status_code=400, detail="Invalid token")

        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.password = auth.get_password_hash(payload.new_password)
        db.commit()
        return {"message": "Password reset successful"}

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=400, detail="Invalid token")