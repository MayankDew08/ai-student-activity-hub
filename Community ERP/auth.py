"""
Authentication Module for Community ERP System
Handles JWT token generation, password hashing, and user authentication
Works with MongoDB for both Students and College Admins
"""

from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from typing import Optional, Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.http import HTTPAuthorizationCredentials
import os

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production-use-env-variable")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


# ==================== PASSWORD HASHING ====================
def hash_password(password: str) -> str:
    """Hash a plain text password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


# ==================== JWT TOKEN MANAGEMENT ====================
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary containing claims (e.g., {"sub": roll_no, "role": "student"})
        expires_delta: Optional custom expiration time
    
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict:
    """
    Decode and verify a JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload
    
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ==================== AUTHENTICATION DEPENDENCIES ====================
async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict:
    """
    Dependency to get current authenticated user from JWT token.
    
    Usage in endpoints:
        @app.get("/protected")
        async def protected_route(current_user: dict = Depends(get_current_user)):
            return {"user": current_user}
    """
    payload = decode_access_token(token)
    
    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    
    return payload


async def get_current_student(current_user: Dict = Depends(get_current_user)) -> Dict:
    """
    Dependency to ensure the current user is a student.
    
    Returns student information from token.
    """
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required",
        )
    return current_user


async def get_current_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    """
    Dependency to ensure the current user is an admin.
    
    Returns admin information from token.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# ==================== TOKEN VERIFICATION ====================
def verify_token(token: str) -> Optional[Dict]:
    """
    Verify a token and return the payload if valid.
    Returns None if invalid.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# ==================== ROLE-BASED ACCESS ====================
def create_student_token(roll_no: str, name: str, college_name: str) -> str:
    """
    Create a JWT token specifically for a student.
    
    Args:
        roll_no: Student's roll number
        name: Student's name
        college_name: Student's college
    
    Returns:
        JWT token string
    """
    token_data = {
        "sub": roll_no,
        "role": "student",
        "name": name,
        "college": college_name
    }
    return create_access_token(token_data)


def create_admin_token(college_id: str, college_name: str) -> str:
    """
    Create a JWT token specifically for a college admin.
    
    Args:
        college_id: College's unique ID
        college_name: College's name
    
    Returns:
        JWT token string
    """
    token_data = {
        "sub": college_id,
        "role": "admin",
        "name": college_name
    }
    return create_access_token(token_data)