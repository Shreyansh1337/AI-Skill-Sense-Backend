from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class GenericWebhookEvent(BaseModel):
    activity_type: str = Field(min_length=1, max_length=100)
    log_desc: str = Field(min_length=1, max_length=5000)
    event_id: str = Field(min_length=1, max_length=255)


class WebhookSettingsResponse(BaseModel):
    configured: bool
    created_at: datetime | None = None


class WebhookCredentialResponse(BaseModel):
    webhook_url: str
    created_at: datetime


class HealthPairingResponse(BaseModel):
    pairing_code: str
    expires_at: datetime
    app_link: str


class HealthDeviceExchangeRequest(BaseModel):
    pairing_code: str = Field(min_length=32, max_length=128)
    device_name: str = Field(min_length=1, max_length=100)


class HealthDeviceExchangeResponse(BaseModel):
    device_token: str
    user_id: str


class HealthConnectRecordUpload(BaseModel):
    record_id: str = Field(min_length=1, max_length=255)
    record_type: Literal[
        "steps",
        "active_calories",
        "distance",
        "exercise",
        "heart_rate",
    ]
    value: float = Field(ge=0, allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=40)
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_time_range(self):
        start = self.start_time
        end = self.end_time
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("Health record timestamps must include a timezone.")
        if end < start:
            raise ValueError("Health record end_time must not precede start_time.")
        return self


class HealthConnectSyncRequest(BaseModel):
    records: list[HealthConnectRecordUpload] = Field(max_length=1000)


class HealthConnectSyncResponse(BaseModel):
    received: int
    inserted: int
    updated: int
    quest_progress_updates: int


class HealthConnectStatusResponse(BaseModel):
    connected: bool
    linked_at: datetime | None = None
    last_sync_at: datetime | None = None
