from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func, extract, case
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from app.models.models import (
    User, University, Department, Complaint, Attachment, 
    Message, Activity, Notification, ComplaintMetrics,
    ComplaintStatus, ComplaintPriority, ComplaintCategory, UserRole
)
from app.schemas.schemas import (
    UserCreate, UserUpdate, UniversityCreate, DepartmentCreate,
    ComplaintCreate, ComplaintUpdate, MessageCreate, ActivityCreate,
    NotificationCreate, ComplaintFilter, PaginationParams
)
from app.core.security import get_password_hash, verify_password
import json

# Base CRUD Class
class CRUDBase:
    def __init__(self, model):
        self.model = model
    
    def get(self, db: Session, id: int):
        return db.query(self.model).filter(self.model.id == id).first()
    
    def get_multi(self, db: Session, skip: int = 0, limit: int = 100):
        return db.query(self.model).offset(skip).limit(limit).all()
    
    def create(self, db: Session, obj_in):
        db_obj = self.model(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update(self, db: Session, db_obj, obj_in):
        obj_data = obj_in.dict(exclude_unset=True)
        for field in obj_data:
            setattr(db_obj, field, obj_data[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def remove(self, db: Session, id: int):
        obj = db.query(self.model).get(id)
        db.delete(obj)
        db.commit()
        return obj

# User CRUD Operations
class CRUDUser(CRUDBase):
    def __init__(self):
        super().__init__(User)
    
    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()
    
    def get_by_username(self, db: Session, username: str) -> Optional[User]:
        return db.query(User).filter(User.username == username).first()
    
    def create(self, db: Session, obj_in: UserCreate) -> User:
        db_obj = User(
            email=obj_in.email,
            username=obj_in.username,
            full_name=obj_in.full_name,
            hashed_password=get_password_hash(obj_in.password),
            role=obj_in.role,
            student_id=obj_in.student_id,
            employee_id=obj_in.employee_id,
            university_id=obj_in.university_id,
            department_id=obj_in.department_id,
            phone=obj_in.phone
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def authenticate(self, db: Session, username: str, password: str) -> Optional[User]:
        user = self.get_by_username(db, username=username)
        if not user:
            user = self.get_by_email(db, email=username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    
    def is_active(self, user: User) -> bool:
        return user.is_active
    
    def get_by_university(self, db: Session, university_id: int, skip: int = 0, limit: int = 100):
        return db.query(User).filter(User.university_id == university_id).offset(skip).limit(limit).all()
    
    def get_admins_by_university(self, db: Session, university_id: int):
        return db.query(User).filter(
            and_(User.university_id == university_id, User.role.in_([UserRole.ADMIN, UserRole.STAFF]))
        ).all()

# University CRUD Operations
class CRUDUniversity(CRUDBase):
    def __init__(self):
        super().__init__(University)
    
    def get_by_code(self, db: Session, code: str) -> Optional[University]:
        return db.query(University).filter(University.code == code).first()
    
    def get_by_domain(self, db: Session, domain: str) -> Optional[University]:
        return db.query(University).filter(University.domain == domain).first()
    
    def get_active(self, db: Session):
        return db.query(University).filter(University.is_active == True).all()

# Department CRUD Operations
class CRUDDepartment(CRUDBase):
    def __init__(self):
        super().__init__(Department)
    
    def get_by_university(self, db: Session, university_id: int):
        return db.query(Department).filter(
            and_(Department.university_id == university_id, Department.is_active == True)
        ).all()
    
    def get_by_code(self, db: Session, university_id: int, code: str):
        return db.query(Department).filter(
            and_(Department.university_id == university_id, Department.code == code)
        ).first()

# Complaint CRUD Operations
class CRUDComplaint(CRUDBase):
    def __init__(self):
        super().__init__(Complaint)
    
    def create(self, db: Session, obj_in: ComplaintCreate, complainant_id: int) -> Complaint:
        # Get the dict and handle witnesses separately
        obj_data = obj_in.dict()
        witnesses_data = obj_data.pop('witnesses', None)
        
        db_obj = Complaint(
            **obj_data,
            complainant_id=complainant_id,
            witnesses=json.dumps(witnesses_data) if witnesses_data else None
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_with_details(self, db: Session, complaint_id: int):
        return db.query(Complaint).options(
            joinedload(Complaint.complainant),
            joinedload(Complaint.resolved_by),
            joinedload(Complaint.university),
            joinedload(Complaint.department),
            joinedload(Complaint.assigned_to),
            joinedload(Complaint.attachments),
            joinedload(Complaint.messages).joinedload(Message.sender),
            joinedload(Complaint.activities).joinedload(Activity.user)
        ).filter(Complaint.id == complaint_id).first()
    
    def get_by_user(self, db: Session, user_id: int, skip: int = 0, limit: int = 100):
        return db.query(Complaint).filter(Complaint.complainant_id == user_id).offset(skip).limit(limit).all()
    
    def get_assigned_to_user(self, db: Session, user_id: int, skip: int = 0, limit: int = 100):
        return db.query(Complaint).join(Complaint.assigned_to).filter(
            User.id == user_id
        ).offset(skip).limit(limit).all()
    
    def get_by_university(self, db: Session, university_id: int, filters: ComplaintFilter = None, 
                         pagination: PaginationParams = None):
        query = db.query(Complaint).filter(Complaint.university_id == university_id)
        
        # Apply filters
        if filters:
            if filters.status:
                query = query.filter(Complaint.status == filters.status)
            if filters.category:
                query = query.filter(Complaint.category == filters.category)
            if filters.priority:
                query = query.filter(Complaint.priority == filters.priority)
            if filters.department_id:
                query = query.filter(Complaint.department_id == filters.department_id)
            if filters.assignee_id:
                query = query.join(Complaint.assigned_to).filter(User.id == filters.assignee_id)
            if filters.date_from:
                query = query.filter(Complaint.created_at >= filters.date_from)
            if filters.date_to:
                query = query.filter(Complaint.created_at <= filters.date_to)
            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        Complaint.title.ilike(search_term),
                        Complaint.description.ilike(search_term)
                    )
                )
        
        # Count total before pagination
        total = query.count()
        
        # Apply pagination
        if pagination:
            skip = (pagination.page - 1) * pagination.size
            query = query.offset(skip).limit(pagination.size)
        
        # Order by creation date (newest first)
        query = query.order_by(desc(Complaint.created_at))
        
        return query.all(), total
    
    def assign_users(self, db: Session, complaint_id: int, user_ids: List[int]):
        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        if complaint:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
            complaint.assigned_to = users
            db.commit()
            db.refresh(complaint)
        return complaint
    
    def update_status(self, db: Session, complaint_id: int, status: ComplaintStatus, 
                     resolution: str = None, resolved_by_id: int = None):
        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        if complaint:
            old_status = complaint.status
            complaint.status = status
            if status == ComplaintStatus.RESOLVED:
                complaint.resolved_at = datetime.utcnow()
                complaint.resolved_by_id = resolved_by_id
                if resolution:
                    complaint.resolution = resolution
            db.commit()
            db.refresh(complaint)
            return complaint, old_status
        return None, None
    
    def get_overdue(self, db: Session, university_id: int):
        return db.query(Complaint).filter(
            and_(
                Complaint.university_id == university_id,
                Complaint.due_date < datetime.utcnow(),
                Complaint.status.notin_([ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED])
            )
        ).all()
    
    def get_statistics(self, db: Session, university_id: int, department_id: int = None, 
                      date_from: datetime = None, date_to: datetime = None):
        query = db.query(Complaint).filter(Complaint.university_id == university_id)
        
        if department_id:
            query = query.filter(Complaint.department_id == department_id)
        if date_from:
            query = query.filter(Complaint.created_at >= date_from)
        if date_to:
            query = query.filter(Complaint.created_at <= date_to)
        
        complaints = query.all()
        
        total_complaints = len(complaints)
        resolved_complaints = len([c for c in complaints if c.status == ComplaintStatus.RESOLVED])
        pending_complaints = len([c for c in complaints 
                                if c.status in [ComplaintStatus.SUBMITTED, ComplaintStatus.UNDER_REVIEW, ComplaintStatus.IN_PROGRESS]])
        overdue_complaints = len([c for c in complaints 
                                if c.due_date and c.due_date < datetime.utcnow() 
                                and c.status not in [ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED]])
        
        # Calculate average resolution time
        resolved_with_time = [c for c in complaints if c.resolved_at and c.created_at]
        if resolved_with_time:
            total_hours = sum([(c.resolved_at - c.created_at).total_seconds() / 3600 
                             for c in resolved_with_time])
            average_resolution_time = total_hours / len(resolved_with_time)
        else:
            average_resolution_time = 0.0
        
        # Calculate satisfaction score
        rated_complaints = [c for c in complaints if c.satisfaction_rating]
        if rated_complaints:
            satisfaction_score = sum([c.satisfaction_rating for c in rated_complaints]) / len(rated_complaints)
        else:
            satisfaction_score = 0.0
        
        # Complaints by category
        complaints_by_category = {}
        for category in ComplaintCategory:
            complaints_by_category[category.value] = len([c for c in complaints if c.category == category])
        
        # Complaints by status
        complaints_by_status = {}
        for status in ComplaintStatus:
            complaints_by_status[status.value] = len([c for c in complaints if c.status == status])
        
        return {
            "total_complaints": total_complaints,
            "pending_complaints": pending_complaints,
            "resolved_complaints": resolved_complaints,
            "overdue_complaints": overdue_complaints,
            "average_resolution_time": average_resolution_time,
            "satisfaction_score": satisfaction_score,
            "complaints_by_category": complaints_by_category,
            "complaints_by_status": complaints_by_status
        }

# Message CRUD Operations
class CRUDMessage(CRUDBase):
    def __init__(self):
        super().__init__(Message)
    
    def create(self, db: Session, obj_in: MessageCreate, sender_id: int) -> Message:
        db_obj = Message(**obj_in.dict(), sender_id=sender_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_by_complaint(self, db: Session, complaint_id: int, include_internal: bool = False):
        query = db.query(Message).filter(Message.complaint_id == complaint_id)
        if not include_internal:
            query = query.filter(Message.is_internal == False)
        return query.order_by(Message.created_at).all()

# Activity CRUD Operations
class CRUDActivity(CRUDBase):
    def __init__(self):
        super().__init__(Activity)
    
    def create(self, db: Session, obj_in: ActivityCreate) -> Activity:
        db_obj = Activity(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def log_activity(self, db: Session, complaint_id: int, user_id: int, action: str, 
                    description: str, old_value: str = None, new_value: str = None):
        activity = Activity(
            complaint_id=complaint_id,
            user_id=user_id,
            action=action,
            description=description,
            old_value=old_value,
            new_value=new_value
        )
        db.add(activity)
        db.commit()
        db.refresh(activity)
        return activity
    
    def get_by_complaint(self, db: Session, complaint_id: int):
        return db.query(Activity).filter(Activity.complaint_id == complaint_id).order_by(Activity.created_at).all()

# Attachment CRUD Operations
class CRUDAttachment(CRUDBase):
    def __init__(self):
        super().__init__(Attachment)
    
    def get_by_complaint(self, db: Session, complaint_id: int):
        return db.query(Attachment).filter(Attachment.complaint_id == complaint_id).all()

# Notification CRUD Operations
class CRUDNotification(CRUDBase):
    def __init__(self):
        super().__init__(Notification)
    
    def create(self, db: Session, obj_in: NotificationCreate) -> Notification:
        db_obj = Notification(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_by_user(self, db: Session, user_id: int, unread_only: bool = False):
        query = db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            query = query.filter(Notification.is_read == False)
        return query.order_by(desc(Notification.created_at)).all()
    
    def mark_as_read(self, db: Session, notification_id: int, user_id: int):
        notification = db.query(Notification).filter(
            and_(Notification.id == notification_id, Notification.user_id == user_id)
        ).first()
        if notification:
            notification.is_read = True
            db.commit()
            db.refresh(notification)
        return notification
    
    def mark_all_as_read(self, db: Session, user_id: int):
        db.query(Notification).filter(Notification.user_id == user_id).update({"is_read": True})
        db.commit()
        return True

# Analytics CRUD Operations
class CRUDAnalytics:
    def get_monthly_trends(self, db: Session, university_id: int, months: int = 6):
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months * 30)
        
        # Group complaints by month
        monthly_data = db.query(
            extract('year', Complaint.created_at).label('year'),
            extract('month', Complaint.created_at).label('month'),
            func.count(Complaint.id).label('total'),
            func.sum(
                case(
                    (Complaint.status == ComplaintStatus.RESOLVED, 1),
                    else_=0
                )
            ).label('resolved')
        ).filter(
            and_(
                Complaint.university_id == university_id,
                Complaint.created_at >= start_date
            )
        ).group_by(
            extract('year', Complaint.created_at),
            extract('month', Complaint.created_at)
        ).all()
        
        trends = []
        for data in monthly_data:
            trends.append({
                "month": f"{int(data.year)}-{int(data.month):02d}",
                "total_complaints": data.total,
                "resolved_complaints": data.resolved,
                "resolution_rate": (data.resolved / data.total * 100) if data.total > 0 else 0
            })
        
        return trends
    
    def get_department_performance(self, db: Session, university_id: int):
        department_stats = db.query(
            Department.name,
            func.count(Complaint.id).label('total_complaints'),
            func.sum(
                case(
                    (Complaint.status == ComplaintStatus.RESOLVED, 1),
                    else_=0
                )
            ).label('resolved_complaints'),
            func.avg(Complaint.satisfaction_rating).label('avg_satisfaction')
        ).outerjoin(Complaint).filter(
            Department.university_id == university_id
        ).group_by(Department.id, Department.name).all()
        
        performance = []
        for stat in department_stats:
            total = stat.total_complaints or 0
            resolved = stat.resolved_complaints or 0
            performance.append({
                "department": stat.name,
                "total_complaints": total,
                "resolved_complaints": resolved,
                "resolution_rate": (resolved / total * 100) if total > 0 else 0,
                "average_satisfaction": round(stat.avg_satisfaction or 0, 2)
            })
        
        return performance

# Initialize CRUD instances
user = CRUDUser()
university = CRUDUniversity()
department = CRUDDepartment()
complaint = CRUDComplaint()
message = CRUDMessage()
activity = CRUDActivity()
attachment = CRUDAttachment()
notification = CRUDNotification()
analytics = CRUDAnalytics()