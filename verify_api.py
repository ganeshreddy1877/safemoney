import urllib.request
import urllib.parse
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def make_request(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    req_data = None
    if data:
        req_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
        
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"HTTP Error {e.code} for {path}: {err_msg}")
        raise e

def run_verification():
    print("--- Starting API Verification Sequence ---")
    
    # 1. Register User
    print("\n1. Testing Account Registration...")
    reg_payload = {
        "username": "api_test_user",
        "email": "api_test@safemoney.com",
        "password": "testpassword123"
    }
    try:
        status, resp = make_request("/auth/register", "POST", reg_payload)
        print(f"Registration Result: {status} - {resp['message']}")
    except Exception:
        print("Registration failed (user might already exist, continuing...)")
        
    # 2. Login User
    print("\n2. Testing Secure Login...")
    login_payload = {
        "username": "api_test_user",
        "password": "testpassword123"
    }
    status, token_resp = make_request("/auth/login", "POST", login_payload)
    token = token_resp["access_token"]
    print(f"Login Result: {status} - Success. Obtained Token.")
    
    # 3. Financial Setup
    print("\n3. Testing Initial Financial Profile Setup...")
    setup_payload = {
        "current_balance": 75000.0,
        "monthly_income": 95000.0,
        "goals": [
            {
                "title": "Graduate Fund",
                "purpose": "Education",
                "target_amount": 150000.0,
                "target_date": "2027-06-30",
                "monthly_contribution": 10000.0
            },
            {
                "title": "New Car",
                "purpose": "Vehicle",
                "target_amount": 500000.0,
                "target_date": "2029-12-31",
                "monthly_contribution": 15000.0
            }
        ]
    }
    status, setup_resp = make_request("/api/setup", "POST", setup_payload, token)
    print(f"Setup Result: {status} - Health Score initialized to {setup_resp['health_score']}%")
    
    # 4. Log Income and Expense Transactions
    print("\n4. Testing Transaction Logging...")
    # Log Expense
    expense_payload = {
        "date": "2026-06-30",
        "time": "14:30",
        "category": "Shopping",
        "description": "Purchased noise-canceling headphones",
        "payment_method": "Debit Card",
        "amount": 7500.0,
        "type": "expense"
    }
    status, tx_resp = make_request("/api/transactions", "POST", expense_payload, token)
    print(f"Log Expense Result: {status} - Registered transaction ID {tx_resp['id']}")
    
    # 5. Fetch Profile & Budgets
    print("\n5. Testing Profile & Budgets Retrieval...")
    status, profile = make_request("/api/profile", "GET", token=token)
    print(f"User Profile: Username: {profile['username']}, Balance: Rs. {profile['current_balance']}, Points: {profile['points']} XP")
    
    status, budgets = make_request("/api/budgets?month=6&year=2026", "GET", token=token)
    print(f"Monthly Budgets: Fetched {len(budgets)} days of rolling budget details.")
    
    # 6. Run What-If Simulation
    print("\n6. Testing What-If Savings Simulation...")
    sim_payload = {
        "reduce_categories": {
            "Food": 25.0,
            "Shopping": 15.0
        },
        "increase_income": 8000.0,
        "target_savings_increase": 4000.0
    }
    status, sim_resp = make_request("/api/simulate", "POST", sim_payload, token)
    print(f"Simulation Forecast: Current Daily: Rs. {sim_resp['current_daily_budget']:.2f} -> New Daily: Rs. {sim_resp['new_daily_budget']:.2f}")
    print(f"Annual savings gain: +Rs. {sim_resp['projected_annual_savings_increase']:.2f}")
    
    # 7. Join Challenge
    print("\n7. Testing Gamification & Challenge Enrollment...")
    status, gam_status = make_request("/api/gamification/status", "GET", token=token)
    challenges = gam_status["challenges"]
    if challenges:
        target_chall_id = challenges[0]["id"]
        status, join_resp = make_request(f"/api/challenges/{target_chall_id}/join", "POST", token=token)
        print(f"Joined Challenge '{challenges[0]['title']}' - Status: {status} - End Date: {join_resp['end_date']}")
    
    # 8. Report Generation
    print("\n8. Testing Monthly PDF Report Compilation...")
    url = f"{BASE_URL}/api/reports/monthly?month=6&year=2026"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as res:
        content_type = res.headers.get("Content-Type")
        print(f"Report Compilation: HTTP {res.status} - Content-Type: {content_type}")
        if content_type == "application/pdf":
            print("Successfully verified PDF report generation!")
            
    # 9. Verify Admin Access
    print("\n9. Testing Admin Dashboard API Access...")
    admin_login_payload = {
        "username": "admin",
        "password": "adminpassword"
    }
    status, admin_token_resp = make_request("/auth/login", "POST", admin_login_payload)
    admin_token = admin_token_resp["access_token"]
    
    status, admin_stats = make_request("/api/admin/stats", "GET", token=admin_token)
    print(f"Admin Access Result: {status} - Total Users: {admin_stats['total_users']}, Avg Health: {admin_stats['avg_health_score']}%")
    
    print("\n--- API VERIFICATION SUCCESSFUL ---")

if __name__ == "__main__":
    run_verification()
