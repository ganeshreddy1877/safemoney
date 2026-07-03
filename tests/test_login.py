import datetime
from app.database import SessionLocal
from app.models import init_db
from app.models import User, PointLog
from app.auth import verify_password, create_access_token, log_audit

db= SessionLocal()

try:
    print("Fetching test user...")
    db_user = db.query(User).filter(User.username == "api_test_user").first()
    if not db_user:
        print("Test user not found in database!")
    else:
        print("User found. Hashed password:", db_user.hashed_password)
        
        # Test verify password
        print("Verifying password...")
        match = verify_password("testpassword123", db_user.hashed_password)
        print("Password match:", match)
        
        # Test update streak/points
        print("Testing point log and commit...")
        today = datetime.date.today()
        if db_user.last_login_date != today:
            db_user.points += 5
            db_user.last_login_date = today
            db.add(PointLog(user_id=db_user.id, points_change=5, reason="Daily Login Reward"))
            db.commit()
            print("Database commit successful.")
            
        # Test token creation
        print("Creating access token...")
        token = create_access_token(
            data={"sub": db_user.username, "role": db_user.role, "user_id": db_user.id}
        )
        print("Token created successfully:", token)
        
        # Test audit log
        print("Writing login audit log...")
        log_audit(db, db_user.id, db_user.username, "Successful Login", None, "success")
        print("Audit log committed.")

except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
