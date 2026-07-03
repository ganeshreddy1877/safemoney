import datetime
import calendar
import os
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Optional

from app.database import get_db
from app.models import User, Transaction, SavingsGoal, DailyBudget, PointLog, Badge, Challenge, UserChallenge, AIRecommendation
from app.schemas import UserProfileResponse, TransactionCreate, TransactionResponse, GoalCreate, GoalResponse, FinancialSetup, WhatIfSimulationInput, WhatIfSimulationResponse, DailyBudgetResponse, ChallengeResponse, UserChallengeResponse, ProfileUpdateInput
from app.auth import get_current_user, log_audit
from app.services.budget_engine import calculate_monthly_budgets, sync_daily_budgets_to_db, calculate_financial_health_score, generate_ai_recommendations
from app.services.pdf_generator import generate_monthly_pdf

router= APIRouter(prefix="/api", tags=["user"])

# 1. Profile & Setup Endpoints

@router.get("/profile", response_model=UserProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/settings")
def update_settings(settings: Dict[str, bool], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if "gift_budget_boost_enabled" in settings:
        current_user.gift_budget_boost_enabled = settings["gift_budget_boost_enabled"]
        db.commit()
        # Trigger daily budget recalculation for the current month after setting changes
        sync_daily_budgets_to_db(db, current_user.id, datetime.date.today())
        return {"message": "Settings updated successfully", "gift_budget_boost_enabled": current_user.gift_budget_boost_enabled}
    raise HTTPException(status_code=400, detail="Invalid settings key")

@router.post("/setup")
def setup_financial_profile(setup_data: FinancialSetup, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.monthly_income > 0:
        log_audit(db, current_user.id, current_user.username, "Profile Setup Re-run Attempted", None, "warning")
        
    current_user.current_balance = setup_data.current_balance
    current_user.monthly_income = setup_data.monthly_income
    current_user.recurring_expenses = setup_data.recurring_expenses or 0.0
    current_user.reserved_amount = setup_data.reserved_amount or 0.0
    
    # Remove existing goals and budgets for clean setup
    db.query(SavingsGoal).filter(SavingsGoal.user_id == current_user.id).delete()
    db.query(DailyBudget).filter(DailyBudget.user_id == current_user.id).delete()
    
    # Save new goals
    for g in setup_data.goals:
        goal = SavingsGoal(
            user_id=current_user.id,
            title=g.title,
            purpose=g.purpose,
            target_amount=g.target_amount,
            current_amount=0.0,
            target_date=g.target_date,
            monthly_contribution=g.monthly_contribution,
            status="active"
        )
        db.add(goal)
    
    db.commit()
    
    # Initialize daily budgets for current month
    today = datetime.date.today()
    sync_daily_budgets_to_db(db, current_user.id, today)
    calculate_financial_health_score(db, current_user.id)
    generate_ai_recommendations(db, current_user.id)
    
    # Award setup bonus points
    points_award = 100
    current_user.points += points_award
    db.add(PointLog(user_id=current_user.id, points_change=points_award, reason="Financial Profile Setup Completed"))
    
    # Award "Budget Beginner" badge
    badge = Badge(user_id=current_user.id, name="Budget Beginner", description="Completed initial financial profile and savings goals setup")
    db.add(badge)
    
    db.commit()
    
    log_audit(db, current_user.id, current_user.username, "Completed Financial Profile Setup", None, "success")
    return {"message": "Financial setup completed successfully", "health_score": current_user.financial_health_score}

@router.post("/profile/update")
def update_profile_parameters(data: ProfileUpdateInput, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.monthly_income = data.monthly_income
    current_user.recurring_expenses = data.recurring_expenses
    current_user.reserved_amount = data.reserved_amount
    if data.current_balance is not None:
        current_user.current_balance = data.current_balance
        
    db.commit()
    
    # Recalculate and sync budget, health score, and AI insights
    sync_daily_budgets_to_db(db, current_user.id, datetime.date.today())
    calculate_financial_health_score(db, current_user.id)
    generate_ai_recommendations(db, current_user.id)
    
    log_audit(db, current_user.id, current_user.username, "Updated Financial Profile Parameters", None, "success")
    return {
        "message": "Financial parameters updated successfully",
        "monthly_income": current_user.monthly_income,
        "recurring_expenses": current_user.recurring_expenses,
        "reserved_amount": current_user.reserved_amount,
        "current_balance": current_user.current_balance
    }

# 2. Transaction Endpoints

@router.post("/transactions", response_model=TransactionResponse)
def create_transaction(tx: TransactionCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check if category keywords match any predefined mapping
    category = tx.category.strip().capitalize()
    
    # Adjust balance
    if tx.type == "income":
        current_user.current_balance += tx.amount
    elif tx.type == "expense":
        current_user.current_balance -= tx.amount
        
    # Calculate budget boost amount
    boost_amount = 0.0
    if tx.type == "income" and current_user.gift_budget_boost_enabled and tx.income_type in ["Gift", "Bonus", "Cashback", "Reward"]:
        boost_amount = tx.amount

    # Create transaction
    db_tx = Transaction(
        user_id=current_user.id,
        date=tx.date,
        time=tx.time,
        category=category,
        description=tx.description,
        payment_method=tx.payment_method,
        amount=tx.amount,
        type=tx.type,
        notes=tx.notes,
        income_type=tx.income_type,
        sender=tx.sender,
        budget_boost_amount=boost_amount,
        updated_balance=current_user.current_balance
    )
    db.add(db_tx)
    db.commit()
    
    # Recalculate rolling daily budget
    sync_daily_budgets_to_db(db, current_user.id, tx.date)
    
    # Fetch today's budget summary
    today_budget = db.query(DailyBudget).filter(
        DailyBudget.user_id == current_user.id,
        DailyBudget.date == tx.date
    ).first()
    
    # Gamification and rewards checks
    points_change = 0
    reasons = []
    
    if tx.type == "expense":
        # Check if transaction is an entry reward
        points_change += 2
        reasons.append("Logged transaction entry")
        
        # Check daily overspending limit
        if today_budget and today_budget.spent_amount > today_budget.final_budget:
            # Check if user already got deducted points for overspending today
            already_deducted = db.query(PointLog).filter(
                PointLog.user_id == current_user.id,
                PointLog.date == tx.date,
                PointLog.points_change < 0
            ).first()
            if not already_deducted:
                points_change -= 10
                reasons.append("Exceeded today's daily budget limit")
                
        # Check category limit alert (80% of daily budget or absolute limit e.g. ₹5,000 for shopping)
        if category == "Shopping" and tx.amount > 5000:
            badge_exist = db.query(Badge).filter(Badge.user_id == current_user.id, Badge.name == "High Spender Alert").first()
            if not badge_exist:
                db.add(Badge(user_id=current_user.id, name="High Spender Alert", description="Recorded a single shopping transaction exceeding ₹5,000"))
                
    elif tx.type == "income":
        points_change += 5
        reasons.append("Recorded additional income")
        
    if points_change != 0:
        current_user.points += points_change
        db.add(PointLog(
            user_id=current_user.id,
            points_change=points_change,
            reason="; ".join(reasons),
            date=tx.date
        ))
        
    # Check streak update
    # If this is the only transaction logged today, check if yesterday had one
    today = datetime.date.today()
    if tx.date == today:
        tx_count_today = db.query(Transaction).filter(
            Transaction.user_id == current_user.id,
            Transaction.date == today
        ).count()
        
        if tx_count_today == 1:
            yesterday = today - datetime.timedelta(days=1)
            tx_count_yesterday = db.query(Transaction).filter(
                Transaction.user_id == current_user.id,
                Transaction.date == yesterday
            ).count()
            
            if tx_count_yesterday > 0:
                current_user.streak_days += 1
                # Award points for streak milestones
                if current_user.streak_days % 7 == 0:
                    streak_bonus = 50
                    current_user.points += streak_bonus
                    db.add(PointLog(user_id=current_user.id, points_change=streak_bonus, reason=f"{current_user.streak_days}-day expense logging streak milestone!"))
                    
                    # Check for streak badges
                    if current_user.streak_days == 7:
                        db.add(Badge(user_id=current_user.id, name="Budget Master", description="Maintained an expense tracking streak of 7 consecutive days"))
                    elif current_user.streak_days == 30:
                        db.add(Badge(user_id=current_user.id, name="Expense Expert", description="Maintained an expense tracking streak of 30 consecutive days"))
            else:
                current_user.streak_days = 1
            
    db.commit()
    
    # Recalculate health score and recommendations
    calculate_financial_health_score(db, current_user.id)
    generate_ai_recommendations(db, current_user.id)
    
    return db_tx

@router.get("/transactions", response_model=List[TransactionResponse])
def get_transactions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Transaction).filter(Transaction.user_id == current_user.id).order_by(Transaction.date.desc(), Transaction.time.desc()).all()

@router.delete("/transactions/{tx_id}")
def delete_transaction(tx_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id, Transaction.user_id == current_user.id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    # Revert balance changes
    if tx.type == "income":
        current_user.current_balance -= tx.amount
    elif tx.type == "expense":
        current_user.current_balance += tx.amount
        
    tx_date = tx.date
    db.delete(tx)
    db.commit()
    
    # Sync budget, score, recs
    sync_daily_budgets_to_db(db, current_user.id, tx_date)
    calculate_financial_health_score(db, current_user.id)
    generate_ai_recommendations(db, current_user.id)
    
    return {"message": "Transaction deleted successfully"}

# 3. Budget & Goal Endpoints

@router.get("/budgets", response_model=List[DailyBudgetResponse])
def get_daily_budgets(month: Optional[int] = None, year: Optional[int] = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = datetime.date.today()
    target_month = month or today.month
    target_year = year or today.year
    
    start_date = datetime.date(target_year, target_month, 1)
    days_in_month = calendar.monthrange(target_year, target_month)[1]
    end_date = datetime.date(target_year, target_month, days_in_month)
    
    # Ensure database is synced for this month
    sync_daily_budgets_to_db(db, current_user.id, start_date)
    
    budgets = db.query(DailyBudget).filter(
        DailyBudget.user_id == current_user.id,
        DailyBudget.date >= start_date,
        DailyBudget.date <= end_date
    ).order_by(DailyBudget.date.asc()).all()
    
    return budgets

@router.get("/goals", response_model=List[GoalResponse])
def get_goals(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(SavingsGoal).filter(SavingsGoal.user_id == current_user.id).all()

@router.post("/goals", response_model=GoalResponse)
def create_goal(goal: GoalCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_goal = SavingsGoal(
        user_id=current_user.id,
        title=goal.title,
        purpose=goal.purpose,
        target_amount=goal.target_amount,
        current_amount=0.0,
        target_date=goal.target_date,
        monthly_contribution=goal.monthly_contribution,
        status="active"
    )
    db.add(db_goal)
    db.commit()
    
    # Sync budget and recommendations
    sync_daily_budgets_to_db(db, current_user.id, datetime.date.today())
    calculate_financial_health_score(db, current_user.id)
    
    return db_goal

@router.post("/goals/{goal_id}/add-savings")
def add_savings_to_goal(goal_id: int, amount: float, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
        
    goal = db.query(SavingsGoal).filter(SavingsGoal.id == goal_id, SavingsGoal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
        
    if amount > current_user.current_balance:
        raise HTTPException(status_code=400, detail="Insufficient current account balance to allocate to savings goal")
        
    goal.current_amount += amount
    current_user.current_balance -= amount
    
    # Check if goal completed
    if goal.current_amount >= goal.target_amount:
        goal.status = "completed"
        # Award completion points
        completion_points = 200
        current_user.points += completion_points
        db.add(PointLog(user_id=current_user.id, points_change=completion_points, reason=f"Savings Goal '{goal.title}' Completed!"))
        
        # Award "Savings Champion" badge
        db.add(Badge(user_id=current_user.id, name="Savings Champion", description=f"Achieved target amount of ₹{goal.target_amount:,.2f} for goal '{goal.title}'"))
        
    db.commit()
    calculate_financial_health_score(db, current_user.id)
    return {"message": "Savings added successfully", "goal_status": goal.status, "current_amount": goal.current_amount}

# 4. What-If Simulation Endpoint

@router.post("/simulate", response_model=WhatIfSimulationResponse)
def run_simulation(sim: WhatIfSimulationInput, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.monthly_income <= 0:
        raise HTTPException(status_code=400, detail="Complete financial setup before running simulations")
        
    today = datetime.date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    remaining_days = days_in_month - today.day + 1
    if remaining_days <= 0:
        remaining_days = 1
        
    # Fetch active goals contributions
    goals = db.query(SavingsGoal).filter(SavingsGoal.user_id == current_user.id, SavingsGoal.status == "active").all()
    current_contributions = sum(g.monthly_contribution for g in goals)
    
    # Fetch user expenses in current month to see category distribution
    start_date = datetime.date(today.year, today.month, 1)
    txs = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start_date,
        Transaction.type == "expense"
    ).all()
    
    cat_spent = {}
    for t in txs:
        cat_spent[t.category] = cat_spent.get(t.category, 0.0) + t.amount
        
    # Sum past expenses this month before today
    spent_past = db.query(Transaction.amount).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start_date,
        Transaction.date < today,
        Transaction.type == "expense"
    ).all()
    total_spent_past = sum(s[0] for s in spent_past)
    
    # Calculate base spending budget
    current_spending_budget = current_user.monthly_income - current_contributions - getattr(current_user, "recurring_expenses", 0.0) - getattr(current_user, "reserved_amount", 0.0)
    current_daily = max(0.0, current_spending_budget - total_spent_past) / remaining_days
    
    # Compute simulated savings from category reductions
    simulated_savings = 0.0
    for cat, reduction_pct in sim.reduce_categories.items():
        if reduction_pct < 0:
            raise HTTPException(status_code=400, detail="Reduction percentage cannot be negative")
        spent = cat_spent.get(cat, 0.0)
        saved_amt = spent * (reduction_pct / 100.0)
        simulated_savings += saved_amt
        
    # Simulated increase in monthly savings
    new_monthly_savings = current_contributions + sim.target_savings_increase + simulated_savings
    new_spending_budget = (current_user.monthly_income + sim.increase_income) - new_monthly_savings - getattr(current_user, "recurring_expenses", 0.0) - getattr(current_user, "reserved_amount", 0.0)
    new_spending_budget = max(0.0, new_spending_budget)
    new_daily = new_spending_budget / days_in_month
    
    # Recalculate rolling daily budget for new daily budget
    new_daily_rolling = max(0.0, new_spending_budget - total_spent_past) / remaining_days
    
    annual_savings_increase = (new_monthly_savings - current_contributions) * 12
    
    # Calculate speedup for savings goals
    goals_impact = []
    for goal in goals:
        if goal.monthly_contribution > 0:
            remaining_amount = goal.target_amount - goal.current_amount
            if remaining_amount > 0:
                # Calculate speedup based on increasing monthly contribution proportionally
                sim_multiplier = 1.0 + (simulated_savings / max(1.0, current_contributions))
                new_contribution = goal.monthly_contribution * sim_multiplier
                current_months = remaining_amount / goal.monthly_contribution
                new_months = remaining_amount / new_contribution
                speedup_months = current_months - new_months
                
                if speedup_months > 0.5:
                    goals_impact.append({
                        "goal": goal.title,
                        "impact": f"Will be completed approximately {speedup_months:.1f} months earlier"
                    })
                else:
                    goals_impact.append({
                        "goal": goal.title,
                        "impact": "Goal contribution will increase slightly, reducing target duration"
                    })
        else:
            goals_impact.append({
                "goal": goal.title,
                "impact": "Set a monthly contribution to project speedup details"
            })
            
    # Estimate health score impact (higher savings & budget adherence boosts score)
    projected_health = min(100, current_user.financial_health_score + int(simulated_savings / 1000) + 5)
    
    return WhatIfSimulationResponse(
        current_daily_budget=current_daily,
        new_daily_budget=new_daily_rolling,
        current_monthly_savings=current_contributions,
        new_monthly_savings=new_monthly_savings,
        projected_annual_savings_increase=annual_savings_increase,
        goals_impact=goals_impact,
        financial_health_impact=projected_health
    )

# 5. Gamification (Badges, Point Logs, Challenges) Endpoints

@router.get("/gamification/status")
def get_gamification_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    badges = db.query(Badge).filter(Badge.user_id == current_user.id).all()
    points_history = db.query(PointLog).filter(PointLog.user_id == current_user.id).order_by(PointLog.id.desc()).limit(10).all()
    
    # Seed default challenges if missing
    challenges = db.query(Challenge).filter(Challenge.is_active == True).all()
    
    # Get active/completed user challenges
    user_challenges = db.query(UserChallenge).filter(UserChallenge.user_id == current_user.id).all()
    
    return {
        "points": current_user.points,
        "streak_days": current_user.streak_days,
        "badges": [{"name": b.name, "description": b.description, "earned_at": b.earned_at} for b in badges],
        "points_history": [{"points_change": p.points_change, "reason": p.reason, "date": p.date} for p in points_history],
        "challenges": challenges,
        "user_challenges": [
            {
                "id": uc.id,
                "challenge_id": uc.challenge_id,
                "title": uc.challenge.title,
                "description": uc.challenge.description,
                "progress": uc.progress,
                "status": uc.status,
                "start_date": uc.start_date,
                "end_date": uc.end_date,
                "points_reward": uc.challenge.points_reward
            } for uc in user_challenges
        ]
    }

@router.post("/challenges/{challenge_id}/join")
def join_challenge(challenge_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id, Challenge.is_active == True).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Active challenge not found")
        
    # Check if already joined
    exists = db.query(UserChallenge).filter(
        UserChallenge.user_id == current_user.id,
        UserChallenge.challenge_id == challenge_id,
        UserChallenge.status == "active"
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="You are already participating in this challenge")
        
    start_date = datetime.date.today()
    end_date = start_date + datetime.timedelta(days=challenge.duration_days)
    
    uc = UserChallenge(
        user_id=current_user.id,
        challenge_id=challenge_id,
        progress=0.0,
        status="active",
        start_date=start_date,
        end_date=end_date
    )
    db.add(uc)
    db.commit()
    
    log_audit(db, current_user.id, current_user.username, f"Joined Challenge: {challenge.title}", None, "success")
    return {"message": "Successfully joined challenge", "end_date": end_date}

# 6. Report Endpoints

@router.get("/reports/monthly")
def get_monthly_report(month: int, year: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = datetime.date.today()
    if year > today.year or (year == today.year and month > today.month):
        raise HTTPException(status_code=400, detail="Cannot generate report for future periods")
        
    filename = f"report_{current_user.id}_{year}_{month:02d}.pdf"
    os.makedirs("./reports", exist_ok=True)
    file_path = os.path.join("./reports", filename)
    
    # Re-calculate budgets and health score for consistency before report compilation
    sync_daily_budgets_to_db(db, current_user.id, datetime.date(year, month, 1))
    calculate_financial_health_score(db, current_user.id)
    
    try:
        generate_monthly_pdf(db, current_user.id, year, month, file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report PDF: {str(e)}")
        
    log_audit(db, current_user.id, current_user.username, f"Generated Monthly Report PDF ({year}-{month:02d})", None, "success")
    return FileResponse(file_path, media_type="application/pdf", filename=f"SafeMoney_Report_{year}_{month:02d}.pdf")

# 7. Recommendations Endpoint

@router.get("/recommendations")
def get_recommendations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Regenerate recommendations
    recs = generate_ai_recommendations(db, current_user.id)
    return recs
