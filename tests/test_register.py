from app.database import SessionLocal
from app.models import init_db
from app.models import User
from app.auth import get_password_hash, log_audit

init_db()
db = SessionLocal()

try:
    # Clean previous
    db.query(User).filter(User.username == "api_test_user").delete()
    db.commit()
    
    print("Attempting to hash password...")
    password_hash = get_password_hash("testpassword123")
    print("Hashed password:", password_hash)
    
    db_user = User(
        username="api_test_user",
        email="api_test@safemoney.com",
        hashed_password=password_hash,
        role="user",
        current_balance=0.0,
        monthly_income=0.0,
        points=50,
        streak_days=0,
        financial_health_score=100
    )
    db.add(db_user)
    db.commit()
    print("User registered successfully. ID:", db_user.id)
    
    log_audit(db, db_user.id, db_user.username, "Account Registered", None, "success")
    print("Audit log written.")
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
