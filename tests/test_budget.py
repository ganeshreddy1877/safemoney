import datetime
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User, Transaction, SavingsGoal, DailyBudget
from app.services.budget_engine import calculate_monthly_budgets, sync_daily_budgets_to_db, calculate_financial_health_score

class TestSafeMoneyBudgetEngine(unittest.TestCase):
    def setUp(self):
        # Create an in-memory database for isolated unit testing
        self.engine = create_engine("sqlite:///:memory:")
        Session = sessionmaker(bind=self.engine)
        self.db = Session()
        Base.metadata.create_all(bind=self.engine)
        
        # Seed a test user
        self.user = User(
            username="tester",
            email="tester@safemoney.com",
            hashed_password="hashedpassword123",
            role="user",
            current_balance=10000.0,
            monthly_income=30000.0,
            points=100,
            streak_days=0,
            financial_health_score=100
        )
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_carry_forward_budget_saving(self):
        """
        Verify that spending less than the daily budget on day 1 carries forward to day 2.
        """
        # Set up an active goal: ₹3,000 monthly contribution
        goal = SavingsGoal(
            user_id=self.user.id,
            title="Emergency Fund",
            purpose="Investment",
            target_amount=10000.0,
            current_amount=0.0,
            target_date=datetime.date(2026, 12, 31),
            monthly_contribution=3000.0,
            status="active"
        )
        self.db.add(goal)
        self.db.commit()
        
        # Monthly spending budget = 30000 - 3000 = 27000
        # For June (30 days), base daily budget = 27000 / 30 = ₹900
        target_date = datetime.date(2026, 6, 1)
        
        # Add an expense of ₹500 on June 1 (under-spend of ₹400)
        tx = Transaction(
            user_id=self.user.id,
            date=datetime.date(2026, 6, 1),
            time=datetime.time(12, 0),
            category="Food",
            description="Lunch delivery",
            payment_method="UPI",
            amount=500.0,
            type="expense"
        )
        self.db.add(tx)
        self.db.commit()
        
        # Recalculate
        budgets = calculate_monthly_budgets(self.db, self.user.id, target_date)
        
        # June 1 final budget should be ₹900, spent ₹500
        self.assertEqual(budgets[datetime.date(2026, 6, 1)]["final_budget"], 900.0)
        self.assertEqual(budgets[datetime.date(2026, 6, 1)]["spent_amount"], 500.0)
        
        # June 2 final budget should be base (900) + carried forward (900 - 500 = 400) = ₹1300
        self.assertEqual(budgets[datetime.date(2026, 6, 2)]["final_budget"], 1300.0)
        self.assertEqual(budgets[datetime.date(2026, 6, 2)]["carried_forward_amount"], 400.0)

    def test_overspend_redistribution(self):
        """
        Verify that exceeding the daily budget on day 1 distributes the excess deduction
        across all remaining days of the month.
        """
        # For June (30 days), no savings goals. Monthly Income = 30,000.
        # Base daily budget = 30,000 / 30 = ₹1,000.
        target_date = datetime.date(2026, 6, 1)
        
        # User spends ₹1,580 on June 1 (overspent by ₹580)
        # Remaining days = 30 - 1 = 29 days.
        # Redistribution deduction = 580 / 29 = ₹20 per day.
        tx = Transaction(
            user_id=self.user.id,
            date=datetime.date(2026, 6, 1),
            time=datetime.time(15, 30),
            category="Shopping",
            description="Impulse purchase",
            payment_method="Credit Card",
            amount=1580.0,
            type="expense"
        )
        self.db.add(tx)
        self.db.commit()
        
        # Recalculate
        budgets = calculate_monthly_budgets(self.db, self.user.id, target_date)
        
        # June 1: final = 1000, spent = 1580 (overspent by 580)
        self.assertEqual(budgets[datetime.date(2026, 6, 1)]["final_budget"], 1000.0)
        self.assertEqual(budgets[datetime.date(2026, 6, 1)]["spent_amount"], 1580.0)
        
        # June 2: final = base (1000) - redistributed deduction (20) = ₹980
        # Since no transactions are recorded on June 2 yet, it has 0 spent and 0 received carry-forward.
        self.assertEqual(budgets[datetime.date(2026, 6, 2)]["final_budget"], 980.0)
        self.assertEqual(budgets[datetime.date(2026, 6, 2)]["redistributed_amount"], 20.0)
        
        # If the user spends exactly the final budget (980) on each subsequent day,
        # there is no carry-forward. Let's record expenses of 980 for June 2 to June 29.
        for d in range(2, 30):
            tx = Transaction(
                user_id=self.user.id,
                date=datetime.date(2026, 6, d),
                time=datetime.time(18, 0),
                category="Food",
                description="Daily budget spend",
                payment_method="UPI",
                amount=980.0,
                type="expense"
            )
            self.db.add(tx)
        self.db.commit()
        
        # Recalculate with expenses logged
        budgets_after = calculate_monthly_budgets(self.db, self.user.id, target_date)
        self.assertEqual(budgets_after[datetime.date(2026, 6, 30)]["final_budget"], 980.0)

    def test_recurring_expenses_and_reserved_amount_deduction(self):
        """
        Verify that recurring expenses and reserved amounts are correctly deducted from monthly spending budget.
        """
        self.user.recurring_expenses = 5000.0
        self.user.reserved_amount = 2000.0
        self.db.commit()
        
        target_date = datetime.date(2026, 6, 1) # June 2026 (historical)
        budgets = calculate_monthly_budgets(self.db, self.user.id, target_date)
        
        # Base daily budget should be: (30000.0 - 5000.0 - 2000.0) / 30 = 23000.0 / 30 = 766.66666...
        expected_base = (30000.0 - 5000.0 - 2000.0) / 30.0
        self.assertAlmostEqual(budgets[datetime.date(2026, 6, 1)]["allocated_amount"], expected_base, places=2)

    def test_current_month_rolling_budget(self):
        """
        Verify that calculation for the current month uses dynamic rolling logic based on remaining days.
        """
        import calendar
        today = datetime.date.today()
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        
        # Seeding User
        self.user.recurring_expenses = 0.0
        self.user.reserved_amount = 0.0
        self.db.commit()
        
        # Log a past expense on Day 1 (if today is Day 2 or later)
        if today.day > 1:
            tx = Transaction(
                user_id=self.user.id,
                date=datetime.date(today.year, today.month, 1),
                time=datetime.time(12, 0),
                category="Food",
                description="Day 1 Lunch",
                payment_method="UPI",
                amount=1000.0,
                type="expense"
            )
            self.db.add(tx)
            self.db.commit()
            
            # Recalculate for current month
            budgets = calculate_monthly_budgets(self.db, self.user.id, today)
            
            # Remaining days = days_in_month - today.day + 1
            remaining_days = days_in_month - today.day + 1
            # Remaining budget = 30000 - 1000 = 29000
            expected_rolling = 29000.0 / remaining_days
            
            self.assertAlmostEqual(budgets[today]["allocated_amount"], expected_rolling, places=2)
            self.assertEqual(budgets[today]["carried_forward_amount"], 0.0)
            self.assertEqual(budgets[today]["redistributed_amount"], 0.0)
        else:
            # If today is Day 1, expected rolling is 30000 / days_in_month
            budgets = calculate_monthly_budgets(self.db, self.user.id, today)
            expected_rolling = 30000.0 / days_in_month
            self.assertAlmostEqual(budgets[today]["allocated_amount"], expected_rolling, places=2)


if __name__ == "__main__":
    unittest.main()
