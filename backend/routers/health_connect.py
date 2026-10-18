import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from database.dependencies import get_db
from database.models import (
    HealthConnectDevice,
    HealthConnectPairing,
    User,
)
from datapool.dependencies import get_datapool_db
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from schemas.integrations import (
    HealthConnectStatusResponse,
    HealthConnectSyncRequest,
    HealthConnectSyncResponse,
    HealthDeviceExchangeRequest,
    HealthDeviceExchangeResponse,
    HealthPairingResponse,
)
from services.health_connect import save_health_sync
from sqlalchemy.orm import Session

from routers.auth import get_current_user

router = APIRouter(
    prefix="/api/health-connect",
    tags=["Health Connect"],
)


def _require_signed_in_user(current_user: User | None) -> User:
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A user access token is required.",
        )
    return current_user


@router.get("/status", response_model=HealthConnectStatusResponse)
def get_health_connect_status(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    user = _require_signed_in_user(current_user)
    device = (
        db.query(HealthConnectDevice)
        .filter(HealthConnectDevice.user_id == user.user_id)
        .first()
    )
    return {
        "connected": device is not None,
        "linked_at": device.linked_at if device else None,
        "last_sync_at": device.last_sync_at if device else None,
    }


@router.post("/pairings", response_model=HealthPairingResponse)
def create_health_connect_pairing(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    user = _require_signed_in_user(current_user)
    pairing_code = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    pairing = HealthConnectPairing(
        code_hash=hashlib.sha256(pairing_code.encode("utf-8")).hexdigest(),
        user_id=user.user_id,
        expires_at=expires_at,
    )
    db.add(pairing)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "pairing_code": pairing_code,
        "expires_at": expires_at,
        "app_link": f"aiskillsense://connect?pairing_code={pairing_code}",
    }


@router.post(
    "/devices/exchange",
    response_model=HealthDeviceExchangeResponse,
)
def exchange_health_connect_pairing(
    request: HealthDeviceExchangeRequest,
    db: Session = Depends(get_db),
):
    code_hash = hashlib.sha256(
        request.pairing_code.encode("utf-8")
    ).hexdigest()
    pairing = (
        db.query(HealthConnectPairing)
        .filter(HealthConnectPairing.code_hash == code_hash)
        .with_for_update()
        .first()
    )
    now = datetime.now(timezone.utc)
    if pairing is None or pairing.consumed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or already-used Health Connect pairing code.",
        )

    expires_at = pairing.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Health Connect pairing code has expired.",
        )

    device_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(device_token.encode("utf-8")).hexdigest()
    device = (
        db.query(HealthConnectDevice)
        .filter(HealthConnectDevice.user_id == pairing.user_id)
        .first()
    )
    if device is None:
        device = HealthConnectDevice(
            user_id=pairing.user_id,
            token_hash=token_hash,
            device_name=request.device_name,
        )
        db.add(device)
    else:
        device.token_hash = token_hash
        device.device_name = request.device_name
        device.linked_at = now
        device.last_sync_at = None

    pairing.consumed_at = now
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"device_token": device_token, "user_id": pairing.user_id}


@router.delete("/devices/me", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_health_connect(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    user = _require_signed_in_user(current_user)
    device = (
        db.query(HealthConnectDevice)
        .filter(HealthConnectDevice.user_id == user.user_id)
        .first()
    )
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Health Connect is not connected.",
        )
    db.delete(device)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


@router.post("/sync", response_model=HealthConnectSyncResponse)
def sync_health_connect_records(
    request: HealthConnectSyncRequest,
    background_tasks: BackgroundTasks,
    x_health_connect_token: str | None = Header(
        default=None,
        alias="X-Health-Connect-Token",
    ),
    db: Session = Depends(get_db),
    datapool_db: Session = Depends(get_datapool_db),
):
    if not x_health_connect_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A Health Connect device token is required.",
        )

    token_hash = hashlib.sha256(
        x_health_connect_token.encode("utf-8")
    ).hexdigest()
    device = (
        db.query(HealthConnectDevice)
        .filter(HealthConnectDevice.token_hash == token_hash)
        .first()
    )
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Health Connect device token.",
        )

    try:
        result = save_health_sync(
            db,
            datapool_db,
            background_tasks,
            device.user_id,
            request.records,
        )
        device.last_sync_at = datetime.now(timezone.utc)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    return {
        "received": len(request.records),
        **result,
    }
