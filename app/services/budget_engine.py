import calendar
import datetime
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np
from app.models import User, Transaction, SavingsGoal, DailyBudget, PointLog, Badge, Challenge, UserChallenge, AIRecommendation

def get_days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]

def calculate_monthly_budgets(db: Session, user_id: int, target_date: datetime.date) -> dict:
    """
    Calculates the daily budgets for a user for a specific month, taking into account
    the carry-forward and overspent redistribution rules.
    Returns a dictionary of date -> daily_budget_info.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.monthly_income <= 0:
        return {}

    year = target_date.year
    month = target_date.month
    days_in_month = get_days_in_month(year, month)
    
    # Calculate sum of monthly contributions for active goals
    active_goals = db.query(SavingsGoal).filter(
        SavingsGoal.user_id == user_id,
        SavingsGoal.status == "active"
    ).all()
    total_monthly_contribution = sum(goal.monthly_contribution for goal in active_goals)
    
    # Deduct recurring expenses, savings goals, and reserved amounts
    monthly_spending_budget = user.monthly_income - total_monthly_contribution - getattr(user, "recurring_expenses", 0.0) - getattr(user, "reserved_amount", 0.0)
    if monthly_spending_budget < 0:
        monthly_spending_budget = 0.0
        
    base_daily_budget = monthly_spending_budget / days_in_month

    # Get all transactions for the user in this month
    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, days_in_month)
    
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).all()
    
    # Group transactions by date and track daily boosts
    daily_expenses = {}
    daily_income = {}
    daily_boosts = {}
    for d in range(1, days_in_month + 1):
        dt = datetime.date(year, month, d)
        daily_expenses[dt] = 0.0
        daily_income[dt] = 0.0
        daily_boosts[dt] = 0.0
        
    for t in transactions:
        if t.type == "expense":
            daily_expenses[t.date] = daily_expenses.get(t.date, 0.0) + t.amount
        elif t.type == "income":
            daily_income[t.date] = daily_income.get(t.date, 0.0) + t.amount
            if user.gift_budget_boost_enabled and getattr(t, "income_type", None) in ["Gift", "Bonus", "Cashback", "Reward"]:
                daily_boosts[t.date] = daily_boosts.get(t.date, 0.0) + t.amount

    # Simulation array to calculate final daily budgets
    daily_budgets = {}
    
    # Array to track overspends from prior days that need to be redistributed
    overspends = []
    
    # Track carry-forward from the previous day
    carried_forward = 0.0
    
    # Rolling daily budget calculation helper
    today = datetime.date.today()
    is_current_month = (year == today.year and month == today.month)
    current_day = today.day if is_current_month else 1
    
    if is_current_month:
        # Sum expenses logged on days before today in the current month
        spent_past = sum(daily_expenses[datetime.date(year, month, day)] for day in range(1, current_day))
        remaining_spending_budget = max(0.0, monthly_spending_budget - spent_past)
        remaining_days = days_in_month - current_day + 1
        base_daily_budget_rolling = remaining_spending_budget / remaining_days
    else:
        base_daily_budget_rolling = base_daily_budget

    for d in range(1, days_in_month + 1):
        dt = datetime.date(year, month, d)
        
        if is_current_month and d >= current_day:
            # Active current-month rolling logic
            boost_today = daily_boosts[dt]
            allocated_today = base_daily_budget_rolling
            
            daily_budgets[dt] = {
                "date": dt,
                "allocated_amount": allocated_today,
                "carried_forward_amount": 0.0,
                "redistributed_amount": 0.0,
                "final_budget": allocated_today,
                "spent_amount": daily_expenses[dt],
                "budget_boost": boost_today
            }
        else:
            # Standard historical carry-forward / redistribution logic
            # Calculate sum of redistribution deductions from prior overspends
            redistributed_deduction = 0.0
            for overspent_day, overspent_amt in overspends:
                remaining_days_from_overspent = days_in_month - overspent_day
                if remaining_days_from_overspent > 0 and d > overspent_day:
                    redistributed_deduction += overspent_amt / remaining_days_from_overspent
                    
            final_budget = base_daily_budget + carried_forward - redistributed_deduction
            final_budget_capped = max(0.0, final_budget)
            
            boost_today = daily_boosts[dt]
            updated_final_budget = final_budget_capped + boost_today
            
            spent_today = daily_expenses[dt]
            
            # Determine next day's carried_forward
            if spent_today < final_budget_capped:
                carried_forward = final_budget_capped - spent_today
            else:
                carried_forward = 0.0
                overspent_today = spent_today - updated_final_budget
                if final_budget < 0:
                    overspent_today += abs(final_budget)
                    
                if overspent_today > 0:
                    overspends.append((d, overspent_today))
                    
            daily_budgets[dt] = {
                "date": dt,
                "allocated_amount": base_daily_budget,
                "carried_forward_amount": carried_forward if d < days_in_month else 0.0,
                "redistributed_amount": redistributed_deduction,
                "final_budget": final_budget_capped,
                "spent_amount": spent_today,
                "budget_boost": boost_today
            }
        
    # Correct the carried_forward offset (shifting carry-forward to the receiving day)
    carried_received = 0.0
    for d in range(1, days_in_month + 1):
        dt = datetime.date(year, month, d)
        today_info = daily_budgets[dt]
        next_carry = today_info["carried_forward_amount"]
        
        # Only overwrite carried_forward_amount if we are in historical mode or it's a past day
        if not is_current_month or d < current_day:
            today_info["carried_forward_amount"] = carried_received
        else:
            # Folded into the rolling base budget for today/future
            today_info["carried_forward_amount"] = 0.0
            
        carried_received = next_carry

    return daily_budgets

def sync_daily_budgets_to_db(db: Session, user_id: int, target_date: datetime.date):
    """
    Recalculates daily budgets for the month and syncs them to the DailyBudget DB table.
    """
    budgets = calculate_monthly_budgets(db, user_id, target_date)
    if not budgets:
        return
        
    for dt, info in budgets.items():
        db_budget = db.query(DailyBudget).filter(
            DailyBudget.user_id == user_id,
            DailyBudget.date == dt
        ).first()
        
        if db_budget:
            db_budget.allocated_amount = info["allocated_amount"]
            db_budget.spent_amount = info["spent_amount"]
            db_budget.carried_forward_amount = info["carried_forward_amount"]
            db_budget.redistributed_amount = info["redistributed_amount"]
            db_budget.final_budget = info["final_budget"]
            db_budget.budget_boost = info.get("budget_boost", 0.0)
        else:
            db_budget = DailyBudget(
                user_id=user_id,
                date=dt,
                allocated_amount=info["allocated_amount"],
                spent_amount=info["spent_amount"],
                carried_forward_amount=info["carried_forward_amount"],
                redistributed_amount=info["redistributed_amount"],
                final_budget=info["final_budget"],
                budget_boost=info.get("budget_boost", 0.0)
            )
            db.add(db_budget)
            
    db.commit()

def calculate_financial_health_score(db: Session, user_id: int) -> int:
    """
    Computes a Financial Health Score from 0 to 100.
    - Budget Adherence (40 points)
    - Savings Goal Progress (30 points)
    - Transaction Entry Consistency (20 points)
    - Spending Stability (10 points)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return 100
        
    today = datetime.date.today()
    start_of_month = datetime.date(today.year, today.month, 1)
    
    # 1. Budget Adherence (40 points)
    # Days where spent_amount <= final_budget
    daily_budgets = db.query(DailyBudget).filter(
        DailyBudget.user_id == user_id,
        DailyBudget.date >= start_of_month,
        DailyBudget.date <= today
    ).all()
    
    adherence_score = 40
    if daily_budgets:
        adhered_days = sum(1 for b in daily_budgets if b.spent_amount <= b.final_budget)
        adherence_rate = adhered_days / len(daily_budgets)
        adherence_score = adherence_rate * 40
        
    # 2. Savings Progress (30 points)
    goals = db.query(SavingsGoal).filter(
        SavingsGoal.user_id == user_id,
        SavingsGoal.status == "active"
    ).all()
    
    savings_score = 20.0 # Default if no active goals
    if goals:
        total_target = sum(g.target_amount for g in goals)
        total_current = sum(g.current_amount for g in goals)
        if total_target > 0:
            savings_score = (total_current / total_target) * 30
            savings_score = min(30.0, savings_score)
            
    # 3. Transaction Entry Consistency (20 points)
    # Days with at least one transaction in the current month compared to elapsed days
    elapsed_days = today.day
    tx_days = db.query(Transaction.date).filter(
        Transaction.user_id == user_id,
        Transaction.date >= start_of_month,
        Transaction.date <= today
    ).distinct().all()
    
    unique_tx_days = len(tx_days)
    consistency_rate = unique_tx_days / elapsed_days if elapsed_days > 0 else 1.0
    consistency_score = consistency_rate * 20
    
    # 4. Spending Stability (10 points)
    # Volatility of daily transactions (Std Dev / Mean)
    expenses = db.query(Transaction.amount).filter(
        Transaction.user_id == user_id,
        Transaction.date >= start_of_month,
        Transaction.date <= today,
        Transaction.type == "expense"
    ).all()
    
    stability_score = 10
    if expenses and len(expenses) > 1:
        amounts = [e[0] for e in expenses]
        std_dev = np.std(amounts)
        mean_val = np.mean(amounts)
        if mean_val > 0:
            cov = std_dev / mean_val # Coefficient of variation
            if cov < 0.4:
                stability_score = 10
            elif cov < 0.8:
                stability_score = 7
            elif cov < 1.2:
                stability_score = 5
            else:
                stability_score = 2
                
    total_score = int(adherence_score + savings_score + consistency_score + stability_score)
    total_score = max(0, min(100, total_score))
    
    # Sync with user profile
    user.financial_health_score = total_score
    db.commit()
    
    return total_score

def generate_ai_recommendations(db: Session, user_id: int) -> list:
    """
    Uses Pandas to analyze user transactions and generate personalized suggestions.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return []
        
    today = datetime.date.today()
    month_start = datetime.date(today.year, today.month, 1)
    
    # Fetch user transactions
    txs = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.date >= month_start - datetime.timedelta(days=30), # Look back 30 days
        Transaction.date <= today
    ).all()
    
    if not txs:
        recommendations = [{
            "category": "General",
            "suggestion": "No transactions found. Start logging your daily expenses to receive personalized savings recommendations.",
            "impact_amount": 0.0
        }]
        
        # Save recommendations to database
        db.query(AIRecommendation).filter(AIRecommendation.user_id == user_id).delete()
        for rec in recommendations:
            db_rec = AIRecommendation(
                user_id=user_id,
                category=rec["category"],
                suggestion=rec["suggestion"],
                impact_amount=rec.get("impact_amount", 0.0)
            )
            db.add(db_rec)
        db.commit()
        
        return recommendations
        
    # Convert to DataFrame for analysis
    data = []
    for t in txs:
        data.append({
            "date": t.date,
            "category": t.category,
            "amount": t.amount,
            "type": t.type
        })
    df = pd.DataFrame(data)
    
    expenses_df = df[df["type"] == "expense"]
    if expenses_df.empty:
        recommendations = [{
            "category": "General",
            "suggestion": "No expense transactions found. Try logging some expenses to see where you can optimize!",
            "impact_amount": 0.0
        }]
        
        # Save recommendations to database
        db.query(AIRecommendation).filter(AIRecommendation.user_id == user_id).delete()
        for rec in recommendations:
            db_rec = AIRecommendation(
                user_id=user_id,
                category=rec["category"],
                suggestion=rec["suggestion"],
                impact_amount=rec.get("impact_amount", 0.0)
            )
            db.add(db_rec)
        db.commit()
        
        return recommendations
        
    recommendations = []
    total_expense = expenses_df["amount"].sum()
    
    # 1. Category Breakdown Analysis
    cat_totals = expenses_df.groupby("category")["amount"].sum().reset_index()
    cat_totals["percentage"] = (cat_totals["amount"] / total_expense) * 100
    
    # Sort categories by spending
    cat_totals = cat_totals.sort_values(by="amount", ascending=False)
    
    # Rule A: Flag high spending categories (> 25% of budget)
    for idx, row in cat_totals.iterrows():
        cat = row["category"]
        pct = row["percentage"]
        amt = row["amount"]
        
        if pct > 25.0 and cat in ["Shopping", "Entertainment", "Food", "Rent", "Utility bills", "Subscriptions"]:
            if cat == "Food":
                recommendations.append({
                    "category": "Food",
                    "suggestion": f"Your Food expenses represent {pct:.1f}% (₹{amt:.2f}) of your total monthly spending. Consider cooking at home or reducing restaurant deliveries twice a week to boost your savings.",
                    "impact_amount": amt * 0.15
                })
            elif cat == "Shopping":
                recommendations.append({
                    "category": "Shopping",
                    "suggestion": f"Shopping accounts for {pct:.1f}% (₹{amt:.2f}) of your budget. Implement the '48-hour rule' before checking out items to avoid impulsive purchases.",
                    "impact_amount": amt * 0.20
                })
            elif cat == "Entertainment" or cat == "Subscriptions":
                recommendations.append({
                    "category": "Entertainment",
                    "suggestion": f"Your Entertainment and Subscriptions category takes up {pct:.1f}% (₹{amt:.2f}) of your expenses. Review active subscriptions and cancel those you haven't used in 30 days.",
                    "impact_amount": amt * 0.10
                })
            elif cat in ["Rent", "Utility bills"]:
                recommendations.append({
                    "category": cat,
                    "suggestion": f"Your {cat} expenses take up {pct:.1f}% (₹{amt:.2f}) of your budget. Consider negotiating rates or auditing your usage to find potential savings.",
                    "impact_amount": amt * 0.05
                })
                
    # Rule B: Frequency Checks (e.g. food delivery frequency)
    food_df = expenses_df[expenses_df["category"] == "Food"]
    if len(food_df) >= 8: # More than ~2 food orders per week
        est_saving = food_df["amount"].mean() * 3
        recommendations.append({
            "category": "Food",
            "suggestion": f"You logged {len(food_df)} food transactions this month. Reducing dining out or deliveries by just 3 meals could save you around ₹{est_saving:.0f} this month.",
            "impact_amount": est_saving
        })
        
    # Rule C: Daily budget compliance
    daily_budgets = db.query(DailyBudget).filter(
        DailyBudget.user_id == user_id,
        DailyBudget.date >= month_start,
        DailyBudget.date <= today
    ).all()
    
    if daily_budgets:
        over_days = sum(1 for b in daily_budgets if b.spent_amount > (b.final_budget + getattr(b, "budget_boost", 0.0)))
        pct_over = (over_days / len(daily_budgets)) * 100
        if pct_over > 40.0:
            recommendations.append({
                "category": "General",
                "suggestion": f"You have exceeded your daily budget on {pct_over:.0f}% of the days this month. Try tracking expenses in real-time on your dashboard to stay within limits before paying.",
                "impact_amount": 0.0
            })
            
    # Rule D: Unexpected Income / Boost Recommendations
    # Look for qualifying income transactions in the lookback period
    boost_txs = [t for t in txs if t.type == "income" and getattr(t, "income_type", None) in ["Gift", "Bonus", "Cashback", "Reward"]]
    if boost_txs:
        total_boost = sum(t.amount for t in boost_txs)
        # Check if there is an active goal
        active_goals = db.query(SavingsGoal).filter(SavingsGoal.user_id == user_id, SavingsGoal.status == "active").all()
        if active_goals:
            goal_titles = ", ".join([f"'{g.title}'" for g in active_goals[:2]])
            recommendations.append({
                "category": "Unexpected Income",
                "suggestion": f"You received unexpected income/boosts of ₹{total_boost:,.2f} from {len(boost_txs)} transactions recently. Consider allocating a portion of this to your active savings goal(s) (e.g. {goal_titles}) to reach them faster.",
                "impact_amount": total_boost * 0.5
            })
        else:
            recommendations.append({
                "category": "Unexpected Income",
                "suggestion": f"You received unexpected income/boosts of ₹{total_boost:,.2f} recently. Consider creating a savings goal to invest these unexpected windfalls and build a secure financial cushion.",
                "impact_amount": total_boost * 0.5
            })
            
    # If no specific recommendations generated, give positive feedback or general tip
    if not recommendations:
        recommendations.append({
            "category": "General",
            "suggestion": "Great job! Your spending is well-distributed across categories. Keep maintaining your discipline to hit your savings goals early.",
            "impact_amount": 0.0
        })
        
    # Save recommendations to database
    # Clear previous ones to keep it clean
    db.query(AIRecommendation).filter(AIRecommendation.user_id == user_id).delete()
    for rec in recommendations:
        db_rec = AIRecommendation(
            user_id=user_id,
            category=rec["category"],
            suggestion=rec["suggestion"],
            impact_amount=rec.get("impact_amount", 0.0)
        )
        db.add(db_rec)
    db.commit()
    
    return recommendations
