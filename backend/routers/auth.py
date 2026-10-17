from uuid import uuid4
import os
import jwt
from database.connection import SessionLocal
from database.models import User
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    hash_password,
    verify_password,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth", tags=["Authentication"])

bearer_scheme = HTTPBearer(auto_error=False)
AGENT_SECRET_KEY = os.getenv("AGENT_SECRET_KEY")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(User)
        .filter(User.email == payload.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        user_id=str(uuid4()),
        username=payload.username.strip(),
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    return {
        "message": "Account created successfully.",
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
    }


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    email = str(payload.email).lower()

    user = (
        db.query(User)
      .filter(User.email == email)
        .first()
    )

    if not user or not verify_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.user_id)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )



def get_current_user(
    user_id: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_agent_secret: str | None = Header(None, alias="X-Agent-Secret"),
    db: Session = Depends(get_db),
) -> User:
    """
    Unified dependency keeping the exact name 'get_current_user'. 
    Supports standard user Bearer tokens OR background agent X-Agent-Secret headers.
    """
    if not SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not configured.")

    # 1. Handle Internal Agent Request via Header
    if x_agent_secret:
        if not AGENT_SECRET_KEY or x_agent_secret != AGENT_SECRET_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid agent secret key.",
            )
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID context missing for agent request.",
            )
        user = db.query(User).filter(User.user_id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
        return user

    # 2. Handle Standard User Token Request
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise credentials_exception

    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        token_user_id = payload.get("sub")

        if not isinstance(token_user_id, str) or not token_user_id:
            raise credentials_exception

        # If user_id was passed via path, ensure it matches token subject
        if user_id and token_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied for this user.",
            )

        target_user_id = user_id if user_id else token_user_id
    except jwt.InvalidTokenError:
        raise credentials_exception

    user = (
        db.query(User)
        .filter(User.user_id == target_user_id)
        .first()
    )

    if user is None:
        raise credentials_exception

    return user



@router.get("/me")
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "email": current_user.email,
    }