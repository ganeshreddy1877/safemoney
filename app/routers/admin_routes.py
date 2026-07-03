import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import User, Transaction, Challenge, AuditLog, SavingsGoal
from app.auth import get_current_admin, log_audit, get_password_hash
from app.schemas import PasswordResetRequest

router= APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])

class UserAdminResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    points: int
    streak_days: int
    financial_health_score: int
    current_balance: float
    monthly_income: float

    class Config:
        from_attributes = True

class ChallengeCreate(BaseModel):
    title: str
    description: str
    points_reward: int
    target_type: str
    target_value: float
    duration_days: int

# 1. Statistics Endpoint
@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.monthly_income > 0).count()
    
    # Average Health Score
    users = db.query(User).all()
    avg_health_score = 0
    if users:
        avg_health_score = sum(u.financial_health_score for u in users) / len(users)
        
    # Platform-wide transactions
    total_tx_count = db.query(Transaction).count()
    tx_expenses = db.query(Transaction).filter(Transaction.type == "expense").all()
    total_spent_amt = sum(t.amount for t in tx_expenses)
    
    # Popular categories
    from sqlalchemy import func
    categories = db.query(
        Transaction.category,
        func.count(Transaction.id).label("count"),
        func.sum(Transaction.amount).label("sum")
    ).filter(Transaction.type == "expense").group_by(Transaction.category).order_by(func.count(Transaction.id).desc()).limit(5).all()
    
    popular_categories = []
    for cat in categories:
        popular_categories.append({
            "category": cat[0],
            "count": cat[1],
            "total_spent": float(cat[2]) if cat[2] else 0.0
        })
        
    # Average savings rate (savings / income)
    savings_rates = []
    for u in users:
        if u.monthly_income > 0:
            user_txs = db.query(Transaction).filter(Transaction.user_id == u.id).all()
            inc = sum(t.amount for t in user_txs if t.type == "income") or u.monthly_income
            exp = sum(t.amount for t in user_txs if t.type == "expense")
            saved = max(0.0, inc - exp)
            savings_rates.append(saved / inc)
    avg_savings_rate = (sum(savings_rates) / len(savings_rates) * 100) if savings_rates else 0.0
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "avg_health_score": int(avg_health_score),
        "total_transactions": total_tx_count,
        "total_platform_spent": total_spent_amt,
        "popular_categories": popular_categories,
        "avg_savings_rate": round(avg_savings_rate, 2)
    }

# 2. User Management
@router.get("/users", response_model=List[UserAdminResponse])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@router.post("/users/{user_id}/status")
def toggle_user_role(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Toggle role between 'user' and 'admin' as a deactivation placeholder or configuration
    user.role = "admin" if user.role == "user" else "user"
    db.commit()
    log_audit(db, None, "Admin", f"Toggled role for User ID {user_id} to {user.role}", None, "success")
    return {"message": f"User role successfully updated to {user.role}"}

@router.post("/users/{user_id}/reset-password")
def admin_reset_password(user_id: int, payload: PasswordResetRequest, current_admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.hashed_password = get_password_hash(payload.temp_pass)
    db.commit()
    log_audit(db, None, "Admin", f"Reset password for User ID {user_id}", None, "success")
    return {"message": "Password reset successfully"}

# 3. Challenge Management
@router.post("/challenges")
def create_challenge(chall: ChallengeCreate, db: Session = Depends(get_db)):
    db_chall = Challenge(
        title=chall.title,
        description=chall.description,
        points_reward=chall.points_reward,
        target_type=chall.target_type,
        target_value=chall.target_value,
        duration_days=chall.duration_days,
        is_active=True
    )
    db.add(db_chall)
    db.commit()
    log_audit(db, None, "Admin", f"Created Challenge: {chall.title}", None, "success")
    return {"message": "Challenge created successfully", "id": db_chall.id}

@router.delete("/challenges/{challenge_id}")
def delete_challenge(challenge_id: int, db: Session = Depends(get_db)):
    chall = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not chall:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    db.delete(chall)
    db.commit()
    log_audit(db, None, "Admin", f"Deleted Challenge ID: {challenge_id}", None, "success")
    return {"message": "Challenge deleted successfully"}

# 4. System & Security Auditing
@router.get("/logs", response_model=List[dict])
def get_audit_logs(db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
    return [
        {
            "id": l.id,
            "username": l.username,
            "action": l.action,
            "timestamp": l.timestamp.isoformat(),
            "ip_address": l.ip_address,
            "status": l.status
        } for l in logs
    ]

# 5. Database Health Check
@router.get("/database")
def get_database_health():
    db_file = "./safemoney.db"
    size_bytes = 0
    if os.path.exists(db_file):
        size_bytes = os.path.getsize(db_file)
        
    return {
        "status": "healthy",
        "database_type": "SQLite",
        "filepath": os.path.abspath(db_file),
        "size_kb": round(size_bytes / 1024, 2),
        "connection_pool": "SQLAlchemy QueuePool"
    }
