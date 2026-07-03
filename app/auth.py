import os
import time
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, AuditLog
from dotenv import load_dotenv

load_dotenv()
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "safe-money-88ae2")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Memory Cache for Google's Firebase public keys
_certs_cache = {}
_certs_cache_expiry = 0.0

def get_google_certs() -> dict:
    global _certs_cache, _certs_cache_expiry
    now = time.time()
    if not _certs_cache or now > _certs_cache_expiry:
        try:
            url = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
            response = httpx.get(url, timeout=10.0)
            if response.status_code == 200:
                _certs_cache = response.json()
                max_age = 3600
                cc = response.headers.get("Cache-Control", "")
                for part in cc.split(","):
                    if "max-age" in part:
                        try:
                            max_age = int(part.split("=")[1].strip())
                        except Exception:
                            pass
                _certs_cache_expiry = now + max_age
        except Exception as e:
            print("Failed to fetch Google certs:", e)
    return _certs_cache

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    # Left for backward compatibility / legacy code support
    SECRET_KEY = os.environ.get("SAFEMONEY_SECRET_KEY", "SUPER_SECRET_RANDOM_KEY_12345!@#$%")
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=1440)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

def verify_firebase_token(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            raise JWTError("Missing Firebase key id")

        certs = get_google_certs()
        cert = certs.get(kid)
        if not cert:
            raise JWTError("Firebase signing certificate not found")

        payload = jwt.decode(
            token,
            cert,
            algorithms=["RS256"],
            audience=FIREBASE_PROJECT_ID,
            issuer=f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}"
        )

        firebase_uid: str = payload.get("sub")
        email: str = payload.get("email")
        if not firebase_uid or not email:
            raise JWTError("Firebase token missing required claims")

        return payload
    except JWTError as e:
        print("[AUTH ERROR] Firebase token decoding failed:", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except Exception as e:
        print("[AUTH ERROR] Firebase validation general error:", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def upsert_user_from_firebase_payload(db: Session, payload: dict) -> User:
    firebase_uid: str = payload.get("sub") or payload.get("firebase_uid")
    email: str = payload.get("email")
    name: str = payload.get("name")

    if not firebase_uid or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.firebase_uid = firebase_uid
            db.commit()
            db.refresh(user)
        else:
            if name:
                username = "".join(c for c in name if c.isalnum() or c in ("-", "_")).strip()
                if not username:
                    username = email.split("@")[0]
            else:
                username = email.split("@")[0]

            base_username = username
            counter = 1
            while db.query(User).filter(User.username == username).first():
                username = f"{base_username}{counter}"
                counter += 1

            role = "admin" if email == "admin@safemoney.com" else "user"

            user = User(
                username=username,
                email=email,
                firebase_uid=firebase_uid,
                hashed_password="firebase_authenticated_user",
                role=role,
                current_balance=0.0,
                monthly_income=0.0,
                points=1000 if role == "admin" else 50,
                streak_days=0,
                financial_health_score=100
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            log_audit(db, user.id, user.username, "Account Auto-created via Firebase Auth", None, "success")

    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    is_firebase_token = False
    try:
        header = jwt.get_unverified_header(token)
        if "kid" in header:
            is_firebase_token = True
    except Exception:
        pass

    if not is_firebase_token:
        try:
            SECRET_KEY = os.environ.get("SAFEMONEY_SECRET_KEY", "SUPER_SECRET_RANDOM_KEY_12345!@#$%")
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id: int = payload.get("user_id")
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    return user
        except Exception:
            pass
        raise credentials_exception

    payload = verify_firebase_token(token)
    return upsert_user_from_firebase_payload(db, payload)

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges"
        )
    return current_user

def log_audit(db: Session, user_id: Optional[int], username: Optional[str], action: str, ip_address: Optional[str], status_code: str):
    log_entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        ip_address=ip_address,
        status=status_code,
        timestamp=datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
