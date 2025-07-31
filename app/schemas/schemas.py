from pydantic import BaseModel, EmailStr, field_validator, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.models import ComplaintStatus, ComplaintPriority, ComplaintCategory, UserRole

# Base Schemas
class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

# University Schemas
class UniversityBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    code: str = Field(..., min_length=2, max_length=50)
    domain: str = Field(..., max_length=100)
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    timezone: str = "UTC"

class UniversityCreate(UniversityBase):
    pass

class University(UniversityBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    logo_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole = UserRole.STUDENT
    student_id: Optional[str] = None
    employee_id: Optional[str] = None
    phone: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)
    university_id: int
    department_id: Optional[int] = None
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[int] = None
    avatar_url: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class User(UserBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    department_id: Optional[int] = None
    university_id: int
    avatar_url: Optional[str] = None
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

class UserProfile(User):
    university: Optional[University] = None
    total_complaints: Optional[int] = 0
    resolved_complaints: Optional[int] = 0

# Department Schemas
class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=2, max_length=10)
    description: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class DepartmentCreate(DepartmentBase):
    university_id: int
    head_id: Optional[int] = None

class Department(DepartmentBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    head_id: Optional[int] = None
    university_id: int
    is_active: bool
    created_at: datetime

# Complaint Schemas
class ComplaintBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    category: ComplaintCategory
    priority: ComplaintPriority = ComplaintPriority.MEDIUM
    is_anonymous: bool = False
    incident_date: Optional[datetime] = None
    location: Optional[str] = None
    witnesses: Optional[List[str]] = []
    department_id: Optional[int] = None

class ComplaintCreate(ComplaintBase):
    university_id: int

class ComplaintUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[ComplaintCategory] = None
    priority: Optional[ComplaintPriority] = None
    status: Optional[ComplaintStatus] = None
    department_id: Optional[int] = None
    incident_date: Optional[datetime] = None
    location: Optional[str] = None
    witnesses: Optional[List[str]] = None
    resolution: Optional[str] = None
    assigned_to_ids: Optional[List[int]] = None

class ComplaintAssignment(BaseModel):
    complaint_id: int
    assigned_to_ids: List[int]

class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus
    resolution: Optional[str] = None

class Complaint(ComplaintBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    status: ComplaintStatus
    complainant_id: int
    university_id: int
    resolved_at: Optional[datetime] = None
    resolved_by_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    satisfaction_rating: Optional[int] = None
    feedback: Optional[str] = None

class ComplaintDetail(Complaint):
    complainant: Optional[User] = None
    resolved_by: Optional[User] = None
    university: Optional[University] = None
    department: Optional[Department] = None
    assigned_to: List[User] = []
    attachments: List["Attachment"] = []
    messages: List["Message"] = []
    activities: List["Activity"] = []

# Attachment Schemas
class AttachmentBase(BaseModel):
    filename: str
    original_filename: str
    mime_type: str
    file_size: int

class AttachmentCreate(AttachmentBase):
    file_path: str
    complaint_id: int

class Attachment(AttachmentBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    file_path: str
    complaint_id: int
    uploaded_by_id: int
    created_at: datetime

# Message Schemas
class MessageBase(BaseModel):
    content: str = Field(..., min_length=1)
    is_internal: bool = False

class MessageCreate(MessageBase):
    complaint_id: int

class Message(MessageBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    complaint_id: int
    sender_id: int
    sender: Optional[User] = None
    created_at: datetime

# Activity Schemas
class ActivityBase(BaseModel):
    action: str
    description: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None

class ActivityCreate(ActivityBase):
    complaint_id: int
    user_id: int

class Activity(ActivityBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    complaint_id: int
    user_id: int
    user: Optional[User] = None
    created_at: datetime

# Notification Schemas
class NotificationBase(BaseModel):
    title: str = Field(..., max_length=200)
    message: str
    notification_type: str = "system"

class NotificationCreate(NotificationBase):
    user_id: int
    complaint_id: Optional[int] = None

class Notification(NotificationBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    complaint_id: Optional[int] = None
    is_read: bool
    created_at: datetime

# Analytics Schemas
class DashboardStats(BaseModel):
    total_complaints: int
    pending_complaints: int
    resolved_complaints: int
    overdue_complaints: int
    average_resolution_time: float
    satisfaction_score: float
    complaints_by_category: Dict[str, int]
    complaints_by_status: Dict[str, int]
    monthly_trends: List[Dict[str, Any]]

class ComplaintMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    university_id: int
    department_id: Optional[int] = None
    date: datetime
    total_complaints: int
    resolved_complaints: int
    average_resolution_time: float
    satisfaction_score: float

# Authentication Schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: User

class TokenData(BaseModel):
    username: str
    user_id: int
    role: str
    university_id: int

# Response Schemas
class ResponseBase(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int

# Search and Filter Schemas
class ComplaintFilter(BaseModel):
    status: Optional[ComplaintStatus] = None
    category: Optional[ComplaintCategory] = None
    priority: Optional[ComplaintPriority] = None
    department_id: Optional[int] = None
    assignee_id: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None

class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)

# File Upload Schema
class FileUpload(BaseModel):
    complaint_id: int
    description: Optional[str] = None

# Rating and Feedback Schema
class ComplaintRating(BaseModel):
    complaint_id: int
    rating: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = None

# Update forward references
ComplaintDetail.model_rebuild()
Attachment.model_rebuild()
Message.model_rebuild()
Activity.model_rebuild()