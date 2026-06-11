from typing import Literal, Optional
from pydantic import BaseModel


class PyMessage(BaseModel):
    text: str
    classSelection: str
    lesson: str
    actionPlan: str
    accessKey: str


class StatusResponse(BaseModel):
    """Response model for status indicator endpoint."""
    status: Literal["operational", "degraded", "down", "unknown"]
    timestamp: str
    status_page_url: Optional[str] = None


class StatusError(BaseModel):
    """Error response model for status indicator endpoint."""
    error: str
    timestamp: str
