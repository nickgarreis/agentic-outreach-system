# src/schemas.py
# Pydantic models for request/response validation
# Defines data structures for API endpoints and database operations
# RELEVANT FILES: deps.py, main.py

from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# Base schemas with common fields


class TimestampMixin(BaseModel):
    """Mixin for models with timestamp fields"""

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class BaseResponse(BaseModel):
    """Base response model with common fields"""

    success: bool = Field(True, description="Operation success status")
    message: Optional[str] = Field(None, description="Optional message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


# Enums for campaign and client status


class CampaignStatus(str, Enum):
    """Campaign lifecycle status"""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ClientStatus(str, Enum):
    """Client engagement status"""

    PROSPECT = "prospect"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    CONVERTED = "converted"
    LOST = "lost"


# Campaign schemas


class CampaignBase(BaseModel):
    """Base campaign model"""

    name: str = Field(..., min_length=1, max_length=255, description="Campaign name")
    description: Optional[str] = Field(None, description="Campaign description")
    status: CampaignStatus = Field(CampaignStatus.DRAFT, description="Campaign status")

    model_config = ConfigDict(use_enum_values=True)


class CampaignCreate(CampaignBase):
    """Model for creating a new campaign"""

    target_audience: Optional[Dict[str, Any]] = Field(
        None, description="Target audience criteria"
    )
    settings: Optional[Dict[str, Any]] = Field(None, description="Campaign settings")


class CampaignUpdate(BaseModel):
    """Model for updating an existing campaign"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[CampaignStatus] = None
    target_audience: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(use_enum_values=True)


class CampaignResponse(CampaignBase, TimestampMixin):
    """Campaign response model"""

    id: str = Field(..., description="Campaign ID")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Campaign metrics")

    model_config = ConfigDict(from_attributes=True)


# Client schemas


class ClientBase(BaseModel):
    """Base client model"""

    email: EmailStr = Field(..., description="Client email address")
    name: str = Field(..., min_length=1, max_length=255, description="Client name")
    company: Optional[str] = Field(None, description="Client company")
    status: ClientStatus = Field(ClientStatus.PROSPECT, description="Client status")

    model_config = ConfigDict(use_enum_values=True)


class ClientCreate(ClientBase):
    """Model for creating a new client"""

    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional client metadata"
    )
    tags: Optional[List[str]] = Field(None, description="Client tags")


class ClientUpdate(BaseModel):
    """Model for updating an existing client"""

    email: Optional[EmailStr] = None
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    company: Optional[str] = None
    status: Optional[ClientStatus] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None

    model_config = ConfigDict(use_enum_values=True)


class ClientResponse(ClientBase, TimestampMixin):
    """Client response model"""

    id: str = Field(..., description="Client ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Client metadata")
    tags: List[str] = Field(default_factory=list, description="Client tags")
    last_contacted: Optional[datetime] = Field(
        None, description="Last contact timestamp"
    )

    model_config = ConfigDict(from_attributes=True)


# Outreach/Job schemas


class JobStatus(str, Enum):
    """Job execution status"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobCreate(BaseModel):
    """Model for creating a new job"""

    type: str = Field(..., description="Job type identifier")
    campaign_id: str = Field(..., description="Associated campaign ID")
    client_id: Optional[str] = Field(None, description="Associated client ID")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Job payload")
    scheduled_at: Optional[datetime] = Field(
        None, description="Scheduled execution time"
    )


class JobResponse(TimestampMixin):
    """Job response model"""

    id: str = Field(..., description="Job ID")
    type: str = Field(..., description="Job type")
    status: JobStatus = Field(..., description="Job status")
    campaign_id: str = Field(..., description="Campaign ID")
    client_id: Optional[str] = Field(None, description="Client ID")
    payload: Dict[str, Any] = Field(..., description="Job payload")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result")
    error: Optional[str] = Field(None, description="Error message if failed")
    started_at: Optional[datetime] = Field(None, description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# Metrics schemas


class MetricType(str, Enum):
    """Types of metrics tracked"""

    EMAIL_SENT = "email_sent"
    EMAIL_OPENED = "email_opened"
    EMAIL_CLICKED = "email_clicked"
    RESPONSE_RECEIVED = "response_received"
    MEETING_SCHEDULED = "meeting_scheduled"
    DEAL_CLOSED = "deal_closed"


class MetricCreate(BaseModel):
    """Model for creating a metric entry"""

    type: MetricType = Field(..., description="Metric type")
    campaign_id: str = Field(..., description="Campaign ID")
    client_id: Optional[str] = Field(None, description="Client ID")
    value: float = Field(1.0, description="Metric value")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional data")


class MetricResponse(MetricCreate, TimestampMixin):
    """Metric response model"""

    id: str = Field(..., description="Metric ID")

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# Pagination schemas


class PaginationParams(BaseModel):
    """Pagination parameters"""

    offset: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(20, ge=1, le=100, description="Number of items to return")
    order_by: Optional[str] = Field(None, description="Field to order by")
    order_desc: bool = Field(False, description="Order descending")


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""

    items: List[Any] = Field(..., description="Page items")
    total: int = Field(..., description="Total number of items")
    offset: int = Field(..., description="Current offset")
    limit: int = Field(..., description="Page size")
    has_more: bool = Field(..., description="Whether more items exist")
