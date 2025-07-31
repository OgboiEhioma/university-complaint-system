from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import shutil
import os
import uuid
from pathlib import Path

from app.db.database import get_db
from app.core.security import (
    get_current_user, get_current_active_user, get_admin_user, 
    create_access_token, get_password_hash, verify_password,
    can_access_complaint, same_university_required
)
from app.crud import crud
from app.schemas import schemas
from app.models.models import User, UserRole, ComplaintStatus, ComplaintPriority
from app.utils.email import send_notification_email
from app.utils.file_handler import save_uploaded_file, delete_file
from app.services.notification_service import NotificationService

# Initialize router
router = APIRouter()

# Initialize services
notification_service = NotificationService()

# ================== AUTHENTICATION ROUTES ==================

@router.post("/auth/register", response_model=schemas.ResponseBase)
async def register(
    user_data: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    """
    Register a new user
    """
    # Check if user already exists
    existing_user = crud.user.get_by_email(db, email=user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    existing_username = crud.user.get_by_username(db, username=user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Verify university exists
    university = crud.university.get(db, id=user_data.university_id)
    if not university:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="University not found"
        )
    
    # Verify department exists (if provided)
    if user_data.department_id:
        department = crud.department.get(db, id=user_data.department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department not found"
            )
    
    # Create user
    try:
        user = crud.user.create(db, obj_in=user_data)
        return schemas.ResponseBase(
            success=True,
            message="User registered successfully",
            data={"user_id": user.id}
        )
    except Exception as e:
        # Print the actual error for debugging
        print(f"Registration error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return more specific error message
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )

@router.post("/auth/login", response_model=schemas.Token)
async def login(
    user_credentials: schemas.UserLogin,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return access token
    """
    user = crud.user.authenticate(
        db, username=user_credentials.username, password=user_credentials.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not crud.user.is_active(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "role": user.role,
            "university_id": user.university_id
        }, 
        expires_delta=access_token_expires
    )
    
    return schemas.Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=1800,  # 30 minutes in seconds
        user=schemas.User.from_orm(user)
    )

@router.get("/auth/me", response_model=schemas.UserProfile)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current user profile with statistics
    """
    # Get user statistics
    user_complaints = crud.complaint.get_by_user(db, user_id=current_user.id)
    total_complaints = len(user_complaints)
    resolved_complaints = len([c for c in user_complaints if c.status == ComplaintStatus.RESOLVED])
    
    user_profile = schemas.UserProfile.from_orm(current_user)
    user_profile.total_complaints = total_complaints
    user_profile.resolved_complaints = resolved_complaints
    
    return user_profile

# ================== USER MANAGEMENT ROUTES ==================

@router.get("/users", response_model=List[schemas.User])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get all users (Admin only)
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        users = crud.user.get_multi(db, skip=skip, limit=limit)
    else:
        users = crud.user.get_by_university(db, university_id=current_user.university_id, skip=skip, limit=limit)
    return users

@router.get("/users/{user_id}", response_model=schemas.User)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get user by ID (Admin only)
    """
    user = crud.user.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check university access
    if current_user.role != UserRole.SUPER_ADMIN and user.university_id != current_user.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return user

@router.put("/users/{user_id}", response_model=schemas.User)
async def update_user(
    user_id: int,
    user_update: schemas.UserUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update user (Admin only or own profile)
    """
    user = crud.user.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )
    
    # Update user
    updated_user = crud.user.update(db, db_obj=user, obj_in=user_update)
    return updated_user

# ================== COMPLAINT ROUTES ==================

@router.post("/complaints", response_model=schemas.Complaint)
async def create_complaint(
    complaint_data: schemas.ComplaintCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new complaint
    """
    # Verify university matches user's university
    if complaint_data.university_id != current_user.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create complaint for different university"
        )
    
    # Create complaint
    complaint = crud.complaint.create(db, obj_in=complaint_data, complainant_id=current_user.id)
    
    # Log activity
    crud.activity.log_activity(
        db=db,
        complaint_id=complaint.id,
        user_id=current_user.id,
        action="complaint_created",
        description=f"Complaint '{complaint.title}' created by {current_user.full_name}"
    )
    
    # Send notifications to admins
    admins = crud.user.get_admins_by_university(db, university_id=current_user.university_id)
    for admin in admins:
        notification_service.create_notification(
            db=db,
            user_id=admin.id,
            title="New Complaint Submitted",
            message=f"A new complaint '{complaint.title}' has been submitted by {current_user.full_name}",
            complaint_id=complaint.id
        )
    
    return complaint

@router.get("/complaints", response_model=schemas.PaginatedResponse)
async def get_complaints(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[ComplaintStatus] = None,
    category: Optional[str] = None,
    priority: Optional[ComplaintPriority] = None,
    department_id: Optional[int] = None,
    search: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get complaints with filtering and pagination
    """
    # Create filter object
    filters = schemas.ComplaintFilter(
        status=status,
        category=category,
        priority=priority,
        department_id=department_id,
        search=search,
        date_from=date_from,
        date_to=date_to
    )
    
    pagination = schemas.PaginationParams(page=page, size=size)
    
    if current_user.role in [UserRole.ADMIN, UserRole.STAFF]:
        # Admin can see all complaints in their university
        complaints, total = crud.complaint.get_by_university(
            db, university_id=current_user.university_id, filters=filters, pagination=pagination
        )
    else:
        # Students can only see their own complaints
        complaints = crud.complaint.get_by_user(
            db, user_id=current_user.id, skip=(page-1)*size, limit=size
        )
        total = len(complaints)
    
    pages = (total + size - 1) // size
    
    return schemas.PaginatedResponse(
        items=complaints,
        total=total,
        page=page,
        size=size,
        pages=pages
    )

@router.get("/complaints/{complaint_id}", response_model=schemas.ComplaintDetail)
async def get_complaint(
    complaint_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get complaint details
    """
    complaint = crud.complaint.get_with_details(db, complaint_id=complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found"
        )
    
    # Check access permissions
    access_checker = can_access_complaint(current_user)
    if not access_checker(complaint):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return complaint

@router.put("/complaints/{complaint_id}", response_model=schemas.Complaint)
async def update_complaint(
    complaint_id: int,
    complaint_update: schemas.ComplaintUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update complaint
    """
    complaint = crud.complaint.get(db, id=complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found"
        )
    
    # Check permissions
    access_checker = can_access_complaint(current_user)
    if not access_checker(complaint):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Students can only update their own complaints and only if not resolved
    if (current_user.role == UserRole.STUDENT and 
        (complaint.complainant_id != current_user.id or complaint.status == ComplaintStatus.RESOLVED)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update this complaint"
        )
    
    # Store old values for activity log
    old_status = complaint.status
    old_priority = complaint.priority
    
    # Update complaint
    updated_complaint = crud.complaint.update(db, db_obj=complaint, obj_in=complaint_update)
    
    # Log activities for changes
    if complaint_update.status and old_status != complaint_update.status:
        crud.activity.log_activity(
            db=db,
            complaint_id=complaint_id,
            user_id=current_user.id,
            action="status_changed",
            description=f"Status changed from {old_status} to {complaint_update.status}",
            old_value=old_status,
            new_value=complaint_update.status
        )
    
    if complaint_update.priority and old_priority != complaint_update.priority:
        crud.activity.log_activity(
            db=db,
            complaint_id=complaint_id,
            user_id=current_user.id,
            action="priority_changed",
            description=f"Priority changed from {old_priority} to {complaint_update.priority}",
            old_value=old_priority,
            new_value=complaint_update.priority
        )
    
    return updated_complaint

@router.post("/complaints/{complaint_id}/assign")
async def assign_complaint(
    complaint_id: int,
    assignment: schemas.ComplaintAssignment,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Assign complaint to users (Admin only)
    """
    complaint = crud.complaint.get(db, id=complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found"
        )
    
    # Check university access
    if current_user.role != UserRole.SUPER_ADMIN and complaint.university_id != current_user.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Assign users
    updated_complaint = crud.complaint.assign_users(db, complaint_id=complaint_id, user_ids=assignment.assigned_to_ids)
    
    # Log activity
    assigned_users = crud.user.get_multi(db)
    assigned_names = [u.full_name for u in assigned_users if u.id in assignment.assigned_to_ids]
    crud.activity.log_activity(
        db=db,
        complaint_id=complaint_id,
        user_id=current_user.id,
        action="complaint_assigned",
        description=f"Complaint assigned to: {', '.join(assigned_names)}"
    )
    
    # Notify assigned users
    for user_id in assignment.assigned_to_ids:
        notification_service.create_notification(
            db=db,
            user_id=user_id,
            title="Complaint Assigned",
            message=f"You have been assigned to complaint: {complaint.title}",
            complaint_id=complaint_id
        )
    
    return {"success": True, "message": "Complaint assigned successfully"}

@router.post("/complaints/{complaint_id}/status")
async def update_complaint_status(
    complaint_id: int,
    status_update: schemas.ComplaintStatusUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update complaint status (Admin only)
    """
    complaint, old_status = crud.complaint.update_status(
        db=db,
        complaint_id=complaint_id,
        status=status_update.status,
        resolution=status_update.resolution,
        resolved_by_id=current_user.id if status_update.status == ComplaintStatus.RESOLVED else None
    )
    
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found"
        )
    
    # Log activity
    crud.activity.log_activity(
        db=db,
        complaint_id=complaint_id,
        user_id=current_user.id,
        action="status_updated",
        description=f"Status updated from {old_status} to {status_update.status}",
        old_value=old_status,
        new_value=status_update.status
    )
    
    # Notify complainant
    notification_service.create_notification(
        db=db,
        user_id=complaint.complainant_id,
        title="Complaint Status Updated",
        message=f"Your complaint '{complaint.title}' status has been updated to {status_update.status}",
        complaint_id=complaint_id
    )
    
    return {"success": True, "message": "Status updated successfully"}

# ================== FILE UPLOAD ROUTES ==================

@router.post("/complaints/{complaint_id}/upload")
async def upload_file(
    complaint_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Upload file attachment to complaint
    """
    # Check if complaint exists and user has access
    complaint = crud.complaint.get(db, id=complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found"
        )
    
    access_checker = can_access_complaint(current_user)
    if not access_checker(complaint):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Validate file
    allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'txt']
    file_extension = file.filename.split('.')[-1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Check file size (10MB limit)
    max_size = 10 * 1024 * 1024  # 10MB
    if file.size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size too large. Maximum size is 10MB"
        )
    
    try:
        # Save file
        file_path = save_uploaded_file(file, complaint_id)
        
        # Create attachment record
        attachment_data = schemas.AttachmentCreate(
            filename=os.path.basename(file_path),
            original_filename=file.filename,
            file_path=file_path,
            mime_type=file.content_type,
            file_size=file.size,
            complaint_id=complaint_id
        )
        
        attachment = crud.attachment.create(db, obj_in=attachment_data)
        attachment.uploaded_by_id = current_user.id
        db.commit()
        
        # Log activity
        crud.activity.log_activity(
            db=db,
            complaint_id=complaint_id,
            user_id=current_user.id,
            action="file_uploaded",
            description=f"File '{file.filename}' uploaded"
        )
        
        return {"success": True, "message": "File uploaded successfully", "attachment_id": attachment.id}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file"
        )

# ================== MESSAGING ROUTES ==================

@router.post("/complaints/{complaint_id}/messages", response_model=schemas.Message)
async def create_message(
    complaint_id: int,
    message_data: schemas.MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Add message to complaint
    """
    complaint = crud.complaint.get(db, id=complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found"
        )
    
    access_checker = can_access_complaint(current_user)
    if not access_checker(complaint):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Create message
    message = crud.message.create(db, obj_in=message_data, sender_id=current_user.id)
    
    # Log activity
    crud.activity.log_activity(
        db=db,
        complaint_id=complaint_id,
        user_id=current_user.id,
        action="message_added",
        description=f"Message added by {current_user.full_name}"
    )
    
    # Notify relevant users (complainant and assigned users)
    notify_users = [complaint.complainant_id]
    notify_users.extend([u.id for u in complaint.assigned_to])
    notify_users = list(set(notify_users))  # Remove duplicates
    notify_users = [uid for uid in notify_users if uid != current_user.id]  # Don't notify sender
    
    for user_id in notify_users:
        notification_service.create_notification(
            db=db,
            user_id=user_id,
            title="New Message",
            message=f"New message on complaint: {complaint.title}",
            complaint_id=complaint_id
        )
    
    return message

@router.get("/complaints/{complaint_id}/messages", response_model=List[schemas.Message])
async def get_messages(
    complaint_id: int,
    include_internal: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get messages for complaint
    """
    complaint = crud.complaint.get(db, id=complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found"
        )
    
    access_checker = can_access_complaint(current_user)
    if not access_checker(complaint):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Only admin/staff can see internal messages
    if include_internal and current_user.role not in [UserRole.ADMIN, UserRole.STAFF, UserRole.SUPER_ADMIN]:
        include_internal = False
    
    messages = crud.message.get_by_complaint(db, complaint_id=complaint_id, include_internal=include_internal)
    return messages

# ================== ANALYTICS ROUTES ==================

@router.get("/analytics/dashboard", response_model=schemas.DashboardStats)
async def get_dashboard_analytics(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get dashboard analytics (Admin only)
    """
    stats = crud.complaint.get_statistics(db, university_id=current_user.university_id)
    
    # Get monthly trends
    monthly_trends = crud.analytics.get_monthly_trends(db, university_id=current_user.university_id)
    
    dashboard_stats = schemas.DashboardStats(
        **stats,
        monthly_trends=monthly_trends
    )
    
    return dashboard_stats

@router.get("/analytics/departments")
async def get_department_performance(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get department performance analytics (Admin only)
    """
    performance = crud.analytics.get_department_performance(db, university_id=current_user.university_id)
    return {"success": True, "data": performance}

# ================== NOTIFICATION ROUTES ==================

@router.get("/notifications", response_model=List[schemas.Notification])
async def get_notifications(
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get user notifications
    """
    notifications = crud.notification.get_by_user(db, user_id=current_user.id, unread_only=unread_only)
    return notifications

@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Mark notification as read
    """
    notification = crud.notification.mark_as_read(db, notification_id=notification_id, user_id=current_user.id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {"success": True, "message": "Notification marked as read"}

@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Mark all notifications as read
    """
    crud.notification.mark_all_as_read(db, user_id=current_user.id)
    return {"success": True, "message": "All notifications marked as read"}