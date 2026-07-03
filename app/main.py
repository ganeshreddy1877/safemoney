import os
import datetime
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import User, Challenge, PointLog, init_db
from app.auth import get_password_hash, create_access_token, verify_password, log_audit
from app.schemas import UserRegister, UserLogin, Token
from app.routers import user_routes
from app.routers import admin_routes

# Initialize Database Schema
init_db()

app = FastAPI(title="SafeMoney API", description="Secure Personal Finance Management System API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup Seeding Logic
@app.on_event("startup")
def seed_data():
    db = SessionLocal()
    try:
        # 1. Seed Admin User if not exists
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@safemoney.com",
                hashed_password=get_password_hash("adminpassword"),
                role="admin",
                current_balance=0.0,
                monthly_income=0.0,
                points=1000,
                streak_days=0,
                financial_health_score=100
            )
            db.add(admin_user)
            db.commit()
            print("Admin user seeded: admin / adminpassword")

        # 2. Seed Default Challenges if not exists
        default_challenges = [
            {
                "title": "No Online Shopping Week",
                "description": "Keep online shopping expenses at ₹0 for 7 consecutive days.",
                "points_reward": 100,
                "target_type": "no_category",
                "target_value": 0.0,
                "duration_days": 7
            },
            {
                "title": "Zero Overspending Challenge",
                "description": "Stay strictly within your daily budgets for 14 consecutive days.",
                "points_reward": 150,
                "target_type": "zero_overspend",
                "target_value": 0.0,
                "duration_days": 14
            },
            {
                "title": "Frugal Living Challenge",
                "description": "Spend less than ₹500 per day on average for a week.",
                "points_reward": 100,
                "target_type": "spend_limit",
                "target_value": 500.0,
                "duration_days": 7
            },
            {
                "title": "Save ₹100 Every Day",
                "description": "Maintain a daily budget surplus of at least ₹100 for 7 consecutive days.",
                "points_reward": 100,
                "target_type": "daily_savings",
                "target_value": 100.0,
                "duration_days": 7
            }
        ]

        for dc in default_challenges:
            exists = db.query(Challenge).filter(Challenge.title == dc["title"]).first()
            if not exists:
                chall = Challenge(
                    title=dc["title"],
                    description=dc["description"],
                    points_reward=dc["points_reward"],
                    target_type=dc["target_type"],
                    target_value=dc["target_value"],
                    duration_days=dc["duration_days"],
                    is_active=True
                )
                db.add(chall)
        db.commit()
    except Exception as e:
        print("Startup seeding failed:", e)
    finally:
        db.close()

# Include Routers
app.include_router(user_routes.router)
app.include_router(admin_routes.router)

# Authentication Endpoints
@app.post("/auth/register")
def register(user: UserRegister, db: Session = Depends(get_db)):
    # Check if username or email exists
    exist_username = db.query(User).filter(User.username == user.username).first()
    if exist_username:
        raise HTTPException(status_code=400, detail="Username already registered")
        
    exist_email = db.query(User).filter(User.email == user.email).first()
    if exist_email:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=get_password_hash(user.password),
        role="user",
        current_balance=0.0,
        monthly_income=0.0,
        points=50, # starting bonus points
        streak_days=0,
        financial_health_score=100
    )
    db.add(db_user)
    db.commit()
    
    # Audit log
    log_audit(db, db_user.id, db_user.username, "Account Registered", None, "success")
    return {"message": "User registered successfully"}

from fastapi import Request

@app.post("/auth/login", response_model=Token)
async def login(request: Request, db: Session = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")
    else:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        
    db_user = db.query(User).filter(User.username == username).first()
    if not db_user or not verify_password(password, db_user.hashed_password):
        log_audit(db, None, username, "Failed Login Attempt", None, "failure")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Update last login and login streak reward
    today = datetime.date.today()
    if db_user.last_login_date != today:
        db_user.points += 5 # 5 points login reward
        db_user.last_login_date = today
        db.add(PointLog(user_id=db_user.id, points_change=5, reason="Daily Login Reward"))
        db.commit()
        
    access_token = create_access_token(
        data={"sub": db_user.username, "role": db_user.role, "user_id": db_user.id}
    )
    
    log_audit(db, db_user.id, db_user.username, "Successful Login", None, "success")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": db_user.username,
        "role": db_user.role
    }

# Serve SPA Frontend
@app.get("/")
def read_index():
    return FileResponse("static/index.html")

# Mount Static Files (after general routes to prevent hijacking)
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
