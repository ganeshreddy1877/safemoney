import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, Time, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base, engine

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user") # 'user', 'admin'
    current_balance = Column(Float, default=0.0) # in ₹
    monthly_income = Column(Float, default=0.0) # in ₹
    recurring_expenses = Column(Float, default=0.0) # in ₹
    reserved_amount = Column(Float, default=0.0) # in ₹
    points = Column(Integer, default=0)
    streak_days = Column(Integer, default=0)
    last_login_date = Column(Date, nullable=True)
    financial_health_score = Column(Integer, default=100)
    gift_budget_boost_enabled = Column(Boolean, default=True)
    firebase_uid = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    goals = relationship("SavingsGoal", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    daily_budgets = relationship("DailyBudget", back_populates="user", cascade="all, delete-orphan")
    point_logs = relationship("PointLog", back_populates="user", cascade="all, delete-orphan")
    badges = relationship("Badge", back_populates="user", cascade="all, delete-orphan")
    user_challenges = relationship("UserChallenge", back_populates="user", cascade="all, delete-orphan")
    recommendations = relationship("AIRecommendation", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")

class SavingsGoal(Base):
    __tablename__ = "savings_goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    target_date = Column(Date, nullable=False)
    monthly_contribution = Column(Float, nullable=False)
    status = Column(String, default="active") # 'active', 'completed', 'cancelled'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="goals")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    time = Column(Time, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String, nullable=False)
    payment_method = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False) # 'income', 'expense'
    notes = Column(String, nullable=True)
    income_type = Column(String, nullable=True) # 'Salary', 'Gift', 'Bonus', 'Cashback', 'Reward', 'Refund', 'Investment Return', 'Other'
    sender = Column(String, nullable=True)
    budget_boost_amount = Column(Float, default=0.0)
    updated_balance = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="transactions")

class DailyBudget(Base):
    __tablename__ = "daily_budgets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    allocated_amount = Column(Float, nullable=False) # base daily budget
    spent_amount = Column(Float, default=0.0)
    carried_forward_amount = Column(Float, default=0.0) # from yesterday
    redistributed_amount = Column(Float, default=0.0) # adjustments from past overspends
    final_budget = Column(Float, nullable=False) # allocated + carried_forward - redistributed
    budget_boost = Column(Float, default=0.0)

    user = relationship("User", back_populates="daily_budgets")

class PointLog(Base):
    __tablename__ = "point_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    points_change = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    date = Column(Date, default=lambda: datetime.date.today())

    user = relationship("User", back_populates="point_logs")

class Badge(Base):
    __tablename__ = "badges"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    earned_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="badges")

class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    points_reward = Column(Integer, nullable=False)
    target_type = Column(String, nullable=False) # 'spend_limit', 'no_category', 'daily_savings', 'streak', 'zero_overspend', 'complete_budget'
    target_value = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)

    user_challenges = relationship("UserChallenge", back_populates="challenge", cascade="all, delete-orphan")

class UserChallenge(Base):
    __tablename__ = "user_challenges"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    progress = Column(Float, default=0.0)
    status = Column(String, default="active") # 'active', 'completed', 'failed'
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    user = relationship("User", back_populates="user_challenges")
    challenge = relationship("Challenge", back_populates="user_challenges")

class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category = Column(String, nullable=False)
    suggestion = Column(String, nullable=False)
    impact_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_read = Column(Boolean, default=False)

    user = relationship("User", back_populates="recommendations")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String, nullable=True)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    ip_address = Column(String, nullable=True)
    status = Column(String, nullable=False) # 'success', 'failure', 'warning'

    user = relationship("User", back_populates="audit_logs")

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Lightweight schema migrations to support Smart Gift Budget Boost feature
    from sqlalchemy import text
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN gift_budget_boost_enabled BOOLEAN DEFAULT 1"))
        except Exception:
            pass
            
        try:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN income_type VARCHAR"))
        except Exception:
            pass
            
        try:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN sender VARCHAR"))
        except Exception:
            pass
            
        try:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN budget_boost_amount FLOAT DEFAULT 0.0"))
        except Exception:
            pass
            
        try:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN updated_balance FLOAT"))
        except Exception:
            pass
            
        try:
            conn.execute(text("ALTER TABLE daily_budgets ADD COLUMN budget_boost FLOAT DEFAULT 0.0"))
        except Exception:
            pass

        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN recurring_expenses FLOAT DEFAULT 0.0"))
        except Exception:
            pass

        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN reserved_amount FLOAT DEFAULT 0.0"))
        except Exception:
            pass

        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN firebase_uid VARCHAR"))
        except Exception:
            pass

        try:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_firebase_uid ON users (firebase_uid)"))
        except Exception:
            pass
