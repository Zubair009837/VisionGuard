from typing import Optional

from pydantic import BaseModel


class CameraBase(BaseModel):
    name: str
    status: str
    nvr: str
    ip: str


class CameraCreate(CameraBase):
    pass


class CameraResponse(CameraBase):
    id: int
    ptz_supported: Optional[bool] = None
    ptz_baseline: Optional[dict] = None

    class Config:
        from_attributes = True