"""Part 1: Secure FastAPI Backend (main.py)
This script configures a secure backend with JWT token authentication and role-based endpoints 
restricted to specific scientific teams."""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from pydantic import BaseModel, validator
from passlib.context import CryptContext
from app.security import InputValidator, PHIDetector, RateLimiter, SecurityHeaders, generate_request_id

logger = logging.getLogger(__name__)
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

# Configuration (Use environment variables in production)
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-scientific-key-12345")
if SECRET_KEY == "super-secret-scientific-key-12345":
    logger.warning("⚠️  SECURITY WARNING: Using default JWT_SECRET. Set JWT_SECRET environment variable in production.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501,http://localhost:3000").split(",")

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Mock Database for Scientific Teams
USER_DB = {
    "dr_smith": {
        "username": "dr_smith",
        "hashed_password": pwd_context.hash("password123"),
        "team": "BioGenomics",
    },
    "dr_jones": {
        "username": "dr_jones",
        "hashed_password": pwd_context.hash("password123"),
        "team": "QuantumChem",
    }
}

# Mock Compliance Audit Data
COMPLIANCE_DATA = [
    {"id": 1, "team": "BioGenomics", "metric": "Data Privacy", "score": 92, "status": "Passed", "date": "2026-10-01"},
    {"id": 2, "team": "BioGenomics", "metric": "Lab Safety", "score": 88, "status": "Passed", "date": "2026-10-03"},
    {"id": 3, "team": "QuantumChem", "metric": "Compute Governance", "score": 65, "status": "Failed", "date": "2026-10-05"},
    {"id": 4, "team": "QuantumChem", "metric": "Chemical Disposal", "score": 95, "status": "Passed", "date": "2026-10-06"},
]

app = FastAPI(title="Scientific Compliance API")

# Security: Add CORS middleware with restricted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600,
)

# Security: Add custom middleware to add security headers and request ID logging
@app.middleware("http")
async def add_security_middleware(request: Request, call_next):
    request_id = generate_request_id()
    request.state.request_id = request_id
    
    # Log incoming request
    logger.info(f"[{request_id}] {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    # Add security headers
    for header, value in SecurityHeaders.get_headers().items():
        response.headers[header] = value
    
    response.headers["X-Request-ID"] = request_id
    return response

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Pydantic Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    username: str
    team: str

class LoginRequest(BaseModel):
    username: str
    password: str
    
    @validator('username')
    def validate_username(cls, v):
        return InputValidator.validate_username(v)
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

# Helper Functions
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        team: str = payload.get("team")
        if username is None or team is None:
            raise credentials_exception
        return User(username=username, team=team)
    except JWTError:
        raise credentials_exception

# Authentication Endpoint
@app.post("/token", response_model=Token)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # Rate limiting
    if not rate_limiter.is_allowed(f"login_{request.client.host}"):
        logger.warning(f"Rate limit exceeded for login from {request.client.host}")
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": "60"},
        )
    
    # Validate input
    try:
        username = InputValidator.validate_username(form_data.username)
    except ValueError as e:
        logger.warning(f"Invalid username format: {form_data.username}")
        raise HTTPException(status_code=400, detail=str(e))
    
    user = USER_DB.get(username)
    if not user or not pwd_context.verify(form_data.password, user["hashed_password"]):
        logger.warning(f"Failed login attempt for user: {username}")
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user["username"], "team": user["team"]})
    logger.info(f"User {username} successfully authenticated")
    return {"access_token": access_token, "token_type": "bearer"}

# Secured Endpoint: Get compliance data for the authenticated user's team
@app.get("/compliance/audits")
async def get_audits(request: Request, current_user: User = Depends(get_current_user)):
    # Rate limiting per user
    if not rate_limiter.is_allowed(f"audits_{current_user.username}"):
        logger.warning(f"Rate limit exceeded for user: {current_user.username}")
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": "60"},
        )
    
    # Filter audits based on the specific scientific team assigned to the JWT
    team_audits = [audit for audit in COMPLIANCE_DATA if audit["team"] == current_user.team]
    logger.info(f"User {current_user.username} retrieved {len(team_audits)} audits for team {current_user.team}")
    
    return {"team": current_user.team, "audits": team_audits}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
