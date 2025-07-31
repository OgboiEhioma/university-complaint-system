from datetime import datetime, timedelta
from typing import Any, Union, Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from decouple import config
from app.db.database import get_db
from app.models.models import User, UserRole
from app.schemas.schemas import TokenData

# Configuration
SECRET_KEY = config("SECRET_KEY", default="your-super-secret-key-change-this-in-production")
ALGORITHM = config("ALGORITHM", default="HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = config("ACCESS_TOKEN_EXPIRE_MINUTES", cast=int, default=30)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Security
security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    """
    Create JWT access token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[TokenData]:
    """
    Verify JWT token and return token data
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        role: str = payload.get("role")
        university_id: int = payload.get("university_id")
        
        if username is None or user_id is None:
            return None
        
        token_data = TokenData(
            username=username, 
            user_id=user_id, 
            role=role,
            university_id=university_id
        )
        return token_data
    except JWTError:
        return None

def get_password_hash(password: str) -> str:
    """
    Hash password using bcrypt
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash
    """
    return pwd_context.verify(plain_password, hashed_password)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = verify_token(credentials.credentials)
    if token_data is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Get current active user
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def require_roles(allowed_roles: list):
    """
    Decorator to require specific roles
    """
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted. Insufficient privileges."
            )
        return current_user
    return role_checker

# Role-based dependencies
def get_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Require admin or staff role
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.STAFF, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

def get_super_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Require super admin role
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required"
        )
    return current_user

def same_university_required(current_user: User = Depends(get_current_active_user)):
    """
    Ensure users can only access data from their university
    """
    def check_university(resource_university_id: int):
        if current_user.university_id != resource_university_id and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Different university."
            )
        return True
    return check_university

def can_access_complaint(current_user: User = Depends(get_current_active_user)):
    """
    Check if user can access a specific complaint
    """
    def check_access(complaint):
        # Super admin can access all
        if current_user.role == UserRole.SUPER_ADMIN:
            return True
        
        # Different university check
        if current_user.university_id != complaint.university_id:
            return False
        
        # Complaint owner can access
        if complaint.complainant_id == current_user.id:
            return True
        
        # Assigned users can access
        if current_user in complaint.assigned_to:
            return True
        
        # Admin/Staff can access all complaints in their university
        if current_user.role in [UserRole.ADMIN, UserRole.STAFF]:
            return True
        
        return False
    return check_access

# Utility functions
def generate_reset_token(user_id: int) -> str:
    """
    Generate password reset token
    """
    data = {"sub": str(user_id), "type": "reset", "exp": datetime.utcnow() + timedelta(hours=1)}
    token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    return token

def verify_reset_token(token: str) -> Optional[int]:
    """
    Verify password reset token
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        
        if token_type != "reset":
            return None
        
        return int(user_id)
    except (JWTError, ValueError):
        return None

def generate_verification_token(user_id: int) -> str:
    """
    Generate email verification token
    """
    data = {"sub": str(user_id), "type": "verify", "exp": datetime.utcnow() + timedelta(days=7)}
    token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    return token

def verify_verification_token(token: str) -> Optional[int]:
    """
    Verify email verification token
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        
        if token_type != "verify":
            return None
        
        return int(user_id)
    except (JWTError, ValueError):
        return None

# Rate limiting and security headers
def check_rate_limit(user_id: int, action: str, limit: int = 10, window: int = 3600):
    """
    Simple rate limiting (in production, use Redis or similar)
    """
    # This is a basic implementation - in production, use Redis
    # For now, we'll just log the action
    pass

def validate_file_upload(filename: str, file_size: int, allowed_extensions: list) -> bool:
    """
    Validate uploaded files
    """
    if not filename:
        return False
    
    # Check file extension
    file_ext = filename.split('.')[-1].lower()
    if file_ext not in allowed_extensions:
        return False
    
    # Check file size (10MB limit)
    max_size = 10 * 1024 * 1024  # 10MB
    if file_size > max_size:
        return False
    
    return True

def sanitize_input(text: str) -> str:
    """
    Basic input sanitization
    """
    if not text:
        return ""
    
    # Remove potential XSS characters
    dangerous_chars = ['<', '>', '"', "'", '&']
    for char in dangerous_chars:
        text = text.replace(char, '')
    
    return text.strip()

# API Key validation (for external integrations)
def validate_api_key(api_key: str, db: Session) -> Optional[User]:
    """
    Validate API key for external integrations
    """
    # In production, store API keys in database with proper hashing
    # For now, we'll use a simple check
    if api_key == config("MASTER_API_KEY", default=""):
        # Return system user or create one
        return None
    return None