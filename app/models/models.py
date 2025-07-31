from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey, Enum, Float, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from datetime import datetime

Base = declarative_base()

# Enums for status and priorities
class ComplaintStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"

class ComplaintPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class ComplaintCategory(str, enum.Enum):
    ACADEMIC = "academic"
    HOUSING = "housing"
    HARASSMENT = "harassment"
    FINANCIAL = "financial"
    FACILITIES = "facilities"
    DISCRIMINATION = "discrimination"
    SAFETY = "safety"
    TECHNOLOGY = "technology"
    FOOD_SERVICES = "food_services"
    TRANSPORTATION = "transportation"
    OTHER = "other"

class UserRole(str, enum.Enum):
    STUDENT = "student"
    ADMIN = "admin"
    STAFF = "staff"
    SUPER_ADMIN = "super_admin"

# Association table for complaint assignments
complaint_assignments = Table(
    'complaint_assignments',
    Base.metadata,
    Column('complaint_id', Integer, ForeignKey('complaints.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True)
)

# University/Tenant Model
class University(Base):
    __tablename__ = "universities"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "MIT", "HARVARD"
    domain = Column(String(100), nullable=False)  # e.g., "mit.edu"
    address = Column(Text)
    phone = Column(String(20))
    email = Column(String(100))
    logo_url = Column(String(500))
    timezone = Column(String(50), default="UTC")
    is_active = Column(Boolean, default=True)
    settings = Column(Text)  # JSON string for custom settings
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    users = relationship("User", back_populates="university")
    complaints = relationship("Complaint", back_populates="university")
    departments = relationship("Department", back_populates="university")

# User Model
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.STUDENT)
    student_id = Column(String(50), index=True)  # For students
    employee_id = Column(String(50), index=True)  # For staff/admin
    department_id = Column(Integer, ForeignKey("departments.id"))
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    phone = Column(String(20))
    avatar_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships - Fixed with explicit foreign_keys
    university = relationship("University", back_populates="users")
    department = relationship("Department", back_populates="users", foreign_keys=[department_id])
    complaints_submitted = relationship("Complaint", back_populates="complainant", foreign_keys="Complaint.complainant_id")
    assigned_complaints = relationship("Complaint", secondary=complaint_assignments, back_populates="assigned_to")
    messages_sent = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")
    activities = relationship("Activity", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    
    # Relationship for departments where this user is head
    departments_headed = relationship("Department", back_populates="head", foreign_keys="Department.head_id")

# Department Model
class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(10), nullable=False)
    description = Column(Text)
    head_id = Column(Integer, ForeignKey("users.id"))
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    email = Column(String(100))
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships - Fixed with explicit foreign_keys
    university = relationship("University", back_populates="departments")
    users = relationship("User", back_populates="department", foreign_keys="User.department_id")
    complaints = relationship("Complaint", back_populates="department")
    head = relationship("User", back_populates="departments_headed", foreign_keys=[head_id])

# Complaint Model
class Complaint(Base):
    __tablename__ = "complaints"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False)
    category = Column(Enum(ComplaintCategory), nullable=False, index=True)
    priority = Column(Enum(ComplaintPriority), default=ComplaintPriority.MEDIUM, index=True)
    status = Column(Enum(ComplaintStatus), default=ComplaintStatus.SUBMITTED, index=True)
    
    # References
    complainant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"))
    
    # Complaint Details
    is_anonymous = Column(Boolean, default=False)
    incident_date = Column(DateTime(timezone=True))
    location = Column(String(200))
    witnesses = Column(Text)  # JSON string
    
    # Resolution Details
    resolution = Column(Text)
    resolved_at = Column(DateTime(timezone=True))
    resolved_by_id = Column(Integer, ForeignKey("users.id"))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    due_date = Column(DateTime(timezone=True))
    
    # Rating and Feedback
    satisfaction_rating = Column(Integer)  # 1-5 scale
    feedback = Column(Text)
    
    # Relationships
    complainant = relationship("User", back_populates="complaints_submitted", foreign_keys=[complainant_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])
    university = relationship("University", back_populates="complaints")
    department = relationship("Department", back_populates="complaints")
    assigned_to = relationship("User", secondary=complaint_assignments, back_populates="assigned_complaints")
    attachments = relationship("Attachment", back_populates="complaint")
    activities = relationship("Activity", back_populates="complaint")
    messages = relationship("Message", back_populates="complaint")

# Attachment Model
class Attachment(Base):
    __tablename__ = "attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    complaint = relationship("Complaint", back_populates="attachments")
    uploaded_by = relationship("User")

# Message Model (for communication)
class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_internal = Column(Boolean, default=False)  # Internal admin notes vs public messages
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    complaint = relationship("Complaint", back_populates="messages")
    sender = relationship("User", back_populates="messages_sent", foreign_keys=[sender_id])

# Activity Log Model
class Activity(Base):
    __tablename__ = "activities"
    
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(100), nullable=False)  # e.g., "status_changed", "assigned", "comment_added"
    description = Column(Text, nullable=False)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    old_value = Column(String(255))
    new_value = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    complaint = relationship("Complaint", back_populates="activities")
    user = relationship("User", back_populates="activities")

# Notification Model
class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    complaint_id = Column(Integer, ForeignKey("complaints.id"))
    is_read = Column(Boolean, default=False)
    notification_type = Column(String(50), nullable=False)  # email, push, system
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    complaint = relationship("Complaint")

# Analytics/Metrics Model
class ComplaintMetrics(Base):
    __tablename__ = "complaint_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"))
    date = Column(DateTime(timezone=True), nullable=False)
    total_complaints = Column(Integer, default=0)
    resolved_complaints = Column(Integer, default=0)
    average_resolution_time = Column(Float, default=0.0)  # in hours
    satisfaction_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    university = relationship("University")
    department = relationship("Department")

# Custom Workflow Model (for advanced features)
class Workflow(Base):
    __tablename__ = "workflows"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(Enum(ComplaintCategory), nullable=False)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    steps = Column(Text, nullable=False)  # JSON string defining workflow steps
    auto_escalation_hours = Column(Integer, default=72)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    university = relationship("University")