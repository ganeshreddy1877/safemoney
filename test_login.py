import sqlite3
from app.auth import verify_password
import bcrypt

def test_login():
    conn = sqlite3.connect("safemoney.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, hashed_password FROM users ORDER BY id DESC LIMIT 5;")
    rows = cursor.fetchall()
    
    print("Latest 5 users in database:")
    for row in rows:
        uid, username, hashed_pw = row
        print(f"User: {username} (ID: {uid}), Hash: {hashed_pw[:15]}...")
        
        # Test if we can verify with 'testpassword123' (used by verify_api.py)
        is_valid = verify_password("testpassword123", hashed_pw)
        print(f"  Valid with 'testpassword123': {is_valid}")
        
        # Test if we can verify with 'securepassword123' (used by verify_exploits.py)
        is_valid = verify_password("securepassword123", hashed_pw)
        print(f"  Valid with 'securepassword123': {is_valid}")

if __name__ == "__main__":
    test_login()
