from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Literal
from datetime import date, time, datetime

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)

class PasswordResetRequest(BaseModel):
    temp_pass: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    username: str
    password: str

class FirebaseLoginRequest(BaseModel):
    idToken: str

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    role: str

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None

class GoalCreate(BaseModel):
    title: str
    purpose: str
    target_amount: float = Field(..., gt=0)
    target_date: date
    monthly_contribution: float = Field(..., ge=0)

class GoalResponse(BaseModel):
    id: int
    title: str
    purpose: str
    target_amount: float
    current_amount: float
    target_date: date
    monthly_contribution: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class FinancialSetup(BaseModel):
    current_balance: float = Field(..., ge=0)
    monthly_income: float = Field(..., ge=0)
    recurring_expenses: Optional[float] = Field(0.0, ge=0)
    reserved_amount: Optional[float] = Field(0.0, ge=0)
    goals: List[GoalCreate]

class TransactionCreate(BaseModel):
    date: date
    time: time
    category: str
    description: str
    payment_method: str
    amount: float = Field(..., gt=0)
    type: Literal["income", "expense"]
    notes: Optional[str] = None
    income_type: Optional[str] = None
    sender: Optional[str] = None

class TransactionResponse(BaseModel):
    id: int
    date: date
    time: time
    category: str
    description: str
    payment_method: str
    amount: float
    type: str
    notes: Optional[str]
    income_type: Optional[str] = None
    sender: Optional[str] = None
    budget_boost_amount: Optional[float] = 0.0
    updated_balance: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True

class DailyBudgetResponse(BaseModel):
    date: date
    allocated_amount: float
    spent_amount: float
    carried_forward_amount: float
    redistributed_amount: float
    final_budget: float
    budget_boost: float = 0.0

    class Config:
        from_attributes = True

class WhatIfSimulationInput(BaseModel):
    reduce_categories: Dict[str, float] # e.g. {"Food": 20.0, "Shopping": 10.0} (percentage reductions)
    increase_income: float = 0.0 # extra monthly income
    target_savings_increase: float = 0.0 # additional savings target

class WhatIfSimulationResponse(BaseModel):
    current_daily_budget: float
    new_daily_budget: float
    current_monthly_savings: float
    new_monthly_savings: float
    projected_annual_savings_increase: float
    goals_impact: List[Dict[str, str]] # goal title -> projected completion speedup message
    financial_health_impact: int # new projected health score

class ChallengeResponse(BaseModel):
    id: int
    title: str
    description: str
    points_reward: int
    target_type: str
    target_value: float
    duration_days: int
    is_active: bool

    class Config:
        from_attributes = True

class UserChallengeResponse(BaseModel):
    id: int
    challenge: ChallengeResponse
    progress: float
    status: str
    start_date: date
    end_date: date

    class Config:
        from_attributes = True

class UserProfileResponse(BaseModel):
    username: str
    email: str
    role: str
    current_balance: float
    monthly_income: float
    points: int
    streak_days: int
    financial_health_score: int
    gift_budget_boost_enabled: bool = True
    recurring_expenses: float = 0.0
    reserved_amount: float = 0.0
    firebase_uid: Optional[str] = None

    class Config:
        from_attributes = True

class ProfileUpdateInput(BaseModel):
    monthly_income: float = Field(..., ge=0)
    recurring_expenses: float = Field(..., ge=0)
    reserved_amount: float = Field(..., ge=0)
    current_balance: Optional[float] = Field(None, ge=0)
