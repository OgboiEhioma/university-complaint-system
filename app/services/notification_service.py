from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template
from decouple import config
import logging

from app.models.models import User, Complaint, Notification, ComplaintStatus
from app.schemas.schemas import NotificationCreate
from app.crud import crud

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.smtp_host = config("SMTP_HOST", default="smtp.gmail.com")
        self.smtp_port = config("SMTP_PORT", cast=int, default=587)
        self.smtp_user = config("SMTP_USER", default="")
        self.smtp_password = config("SMTP_PASSWORD", default="")
        self.from_email = config("FROM_EMAIL", default=self.smtp_user)
        self.smtp_tls = config("SMTP_TLS", cast=bool, default=True)
    
    def create_notification(
        self, 
        db: Session, 
        user_id: int, 
        title: str, 
        message: str, 
        complaint_id: Optional[int] = None,
        notification_type: str = "system",
        send_email: bool = True
    ) -> Notification:
        """
        Create a new notification
        """
        try:
            # Create notification in database
            notification_data = NotificationCreate(
                title=title,
                message=message,
                user_id=user_id,
                complaint_id=complaint_id,
                notification_type=notification_type
            )
            
            notification = crud.notification.create(db, obj_in=notification_data)
            
            # Send email notification if enabled
            if send_email and self.smtp_user:
                self._send_email_notification(db, notification)
            
            logger.info(f"Notification created for user {user_id}: {title}")
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            raise
    
    def _send_email_notification(self, db: Session, notification: Notification):
        """
        Send email notification
        """
        try:
            # Get user details
            user = crud.user.get(db, id=notification.user_id)
            if not user or not user.email:
                return
            
            # Create email content
            subject = f"[Complaint System] {notification.title}"
            
            # Use HTML template for better formatting
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
                    .container { max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                    .header { background-color: #2563eb; color: white; padding: 20px; border-radius: 8px 8px 0 0; margin: -20px -20px 20px -20px; }
                    .title { margin: 0; font-size: 24px; }
                    .content { line-height: 1.6; color: #333; }
                    .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 14px; }
                    .button { display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin: 20px 0; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1 class="title">{{ title }}</h1>
                    </div>
                    <div class="content">
                        <p>Hello {{ user_name }},</p>
                        <p>{{ message }}</p>
                        {% if complaint_id %}
                        <a href="http://localhost:3000/complaints/{{ complaint_id }}" class="button">View Complaint</a>
                        {% endif %}
                    </div>
                    <div class="footer">
                        <p>This is an automated message from the University Complaint System.</p>
                        <p>Please do not reply to this email.</p>
                        <p>If you have questions, please contact your system administrator.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            template = Template(html_template)
            html_content = template.render(
                title=notification.title,
                user_name=user.full_name,
                message=notification.message,
                complaint_id=notification.complaint_id
            )
            
            # Send email
            self._send_email(user.email, subject, html_content)
            
        except Exception as e:
            logger.error(f"Error sending email notification: {str(e)}")
    
    def _send_email(self, to_email: str, subject: str, html_content: str):
        """
        Send email using SMTP
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
    
    def notify_complaint_status_change(
        self, 
        db: Session, 
        complaint: Complaint, 
        old_status: ComplaintStatus, 
        new_status: ComplaintStatus,
        changed_by: User
    ):
        """
        Notify relevant users about complaint status change
        """
        try:
            # Notify complainant
            if complaint.complainant_id != changed_by.id:
                self.create_notification(
                    db=db,
                    user_id=complaint.complainant_id,
                    title="Complaint Status Updated",
                    message=f"Your complaint '{complaint.title}' status has been changed from {old_status.value} to {new_status.value} by {changed_by.full_name}.",
                    complaint_id=complaint.id
                )
            
            # Notify assigned users
            for assigned_user in complaint.assigned_to:
                if assigned_user.id != changed_by.id:
                    self.create_notification(
                        db=db,
                        user_id=assigned_user.id,
                        title="Assigned Complaint Status Updated",
                        message=f"Complaint '{complaint.title}' that you're assigned to has been updated to {new_status.value}.",
                        complaint_id=complaint.id
                    )
            
        except Exception as e:
            logger.error(f"Error notifying status change: {str(e)}")
    
    def notify_complaint_assignment(
        self, 
        db: Session, 
        complaint: Complaint, 
        assigned_users: List[User],
        assigned_by: User
    ):
        """
        Notify users about complaint assignment
        """
        try:
            for user in assigned_users:
                self.create_notification(
                    db=db,
                    user_id=user.id,
                    title="New Complaint Assignment",
                    message=f"You have been assigned to complaint '{complaint.title}' by {assigned_by.full_name}.",
                    complaint_id=complaint.id
                )
            
        except Exception as e:
            logger.error(f"Error notifying assignment: {str(e)}")
    
    def notify_new_message(
        self, 
        db: Session, 
        complaint: Complaint,
        sender: User,
        message_content: str
    ):
        """
        Notify relevant users about new messages
        """
        try:
            # Get all users who should be notified
            notify_users = set()
            
            # Add complainant
            notify_users.add(complaint.complainant_id)
            
            # Add assigned users
            for assigned_user in complaint.assigned_to:
                notify_users.add(assigned_user.id)
            
            # Remove sender from notification list
            notify_users.discard(sender.id)
            
            # Send notifications
            for user_id in notify_users:
                self.create_notification(
                    db=db,
                    user_id=user_id,
                    title="New Message on Complaint",
                    message=f"{sender.full_name} added a message to complaint '{complaint.title}'.",
                    complaint_id=complaint.id
                )
            
        except Exception as e:
            logger.error(f"Error notifying new message: {str(e)}")
    
    def notify_overdue_complaints(self, db: Session):
        """
        Check for overdue complaints and send notifications
        """
        try:
            # Get all overdue complaints
            overdue_complaints = db.query(Complaint).filter(
                Complaint.due_date < datetime.utcnow(),
                Complaint.status.notin_([ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED])
            ).all()
            
            for complaint in overdue_complaints:
                # Notify assigned users
                for assigned_user in complaint.assigned_to:
                    self.create_notification(
                        db=db,
                        user_id=assigned_user.id,
                        title="Overdue Complaint Alert",
                        message=f"Complaint '{complaint.title}' is overdue and requires attention.",
                        complaint_id=complaint.id,
                        notification_type="alert"
                    )
                
                # Notify admins if no one is assigned
                if not complaint.assigned_to:
                    admins = crud.user.get_admins_by_university(db, university_id=complaint.university_id)
                    for admin in admins:
                        self.create_notification(
                            db=db,
                            user_id=admin.id,
                            title="Unassigned Overdue Complaint",
                            message=f"Unassigned complaint '{complaint.title}' is overdue and needs assignment.",
                            complaint_id=complaint.id,
                            notification_type="alert"
                        )
            
            logger.info(f"Processed {len(overdue_complaints)} overdue complaints")
            
        except Exception as e:
            logger.error(f"Error checking overdue complaints: {str(e)}")
    
    def send_daily_digest(self, db: Session, user_id: int):
        """
        Send daily digest of activities to a user
        """
        try:
            user = crud.user.get(db, id=user_id)
            if not user:
                return
            
            # Get user's complaints and assignments from last 24 hours
            yesterday = datetime.utcnow() - timedelta(days=1)
            
            # Get new complaints if user is admin
            new_complaints = []
            if user.role.value in ['admin', 'staff', 'super_admin']:
                new_complaints = db.query(Complaint).filter(
                    Complaint.university_id == user.university_id,
                    Complaint.created_at >= yesterday
                ).all()
            
            # Get updates on user's complaints
            user_complaints = crud.complaint.get_by_user(db, user_id=user.id)
            recent_activities = []
            for complaint in user_complaints:
                activities = db.query(crud.activity.model).filter(
                    crud.activity.model.complaint_id == complaint.id,
                    crud.activity.model.created_at >= yesterday,
                    crud.activity.model.user_id != user.id  # Exclude user's own activities
                ).all()
                recent_activities.extend(activities)
            
            # Send digest if there's content
            if new_complaints or recent_activities:
                digest_content = self._create_daily_digest_content(user, new_complaints, recent_activities)
                
                self.create_notification(
                    db=db,
                    user_id=user.id,
                    title="Daily Activity Digest",
                    message=digest_content,
                    notification_type="digest"
                )
            
        except Exception as e:
            logger.error(f"Error sending daily digest to user {user_id}: {str(e)}")
    
    def _create_daily_digest_content(self, user: User, new_complaints: List[Complaint], activities: List):
        """
        Create content for daily digest
        """
        content_parts = [f"Hello {user.full_name}, here's your daily activity summary:"]
        
        if new_complaints:
            content_parts.append(f"\n📋 {len(new_complaints)} new complaints submitted:")
            for complaint in new_complaints[:5]:  # Limit to 5
                content_parts.append(f"• {complaint.title} ({complaint.category.value})")
            
            if len(new_complaints) > 5:
                content_parts.append(f"• ... and {len(new_complaints) - 5} more")
        
        if activities:
            content_parts.append(f"\n🔄 {len(activities)} updates on your complaints:")
            for activity in activities[:5]:  # Limit to 5
                content_parts.append(f"• {activity.description}")
            
            if len(activities) > 5:
                content_parts.append(f"• ... and {len(activities) - 5} more")
        
        return "\n".join(content_parts)
    
    def send_welcome_email(self, db: Session, user: User):
        """
        Send welcome email to new users
        """
        try:
            welcome_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
                    .container { max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                    .header { background-color: #2563eb; color: white; padding: 20px; border-radius: 8px 8px 0 0; margin: -20px -20px 20px -20px; }
                    .title { margin: 0; font-size: 24px; }
                    .content { line-height: 1.6; color: #333; }
                    .button { display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin: 20px 0; }
                    .feature { background-color: #f8fafc; padding: 15px; margin: 10px 0; border-left: 4px solid #2563eb; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1 class="title">Welcome to the Complaint System!</h1>
                    </div>
                    <div class="content">
                        <p>Hello {{ user_name }},</p>
                        <p>Welcome to the University Complaint System! Your account has been successfully created.</p>
                        
                        <div class="feature">
                            <h3>🎯 Submit Complaints</h3>
                            <p>Easily submit and track your complaints with our user-friendly interface.</p>
                        </div>
                        
                        <div class="feature">
                            <h3>📱 Real-time Updates</h3>
                            <p>Get instant notifications when your complaints are updated or resolved.</p>
                        </div>
                        
                        <div class="feature">
                            <h3>📄 Document Upload</h3>
                            <p>Attach relevant documents and evidence to support your complaints.</p>
                        </div>
                        
                        <div class="feature">
                            <h3>💬 Communication</h3>
                            <p>Communicate directly with administrators through our messaging system.</p>
                        </div>
                        
                        <p><strong>Your Account Details:</strong></p>
                        <ul>
                            <li>Username: {{ username }}</li>
                            <li>Email: {{ email }}</li>
                            <li>Role: {{ role }}</li>
                            <li>University: {{ university }}</li>
                        </ul>
                        
                        <a href="http://localhost:3000/login" class="button">Login to Your Account</a>
                        
                        <p>If you have any questions or need assistance, please don't hesitate to contact our support team.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            template = Template(welcome_template)
            html_content = template.render(
                user_name=user.full_name,
                username=user.username,
                email=user.email,
                role=user.role.value.title(),
                university=user.university.name if user.university else "N/A"
            )
            
            self._send_email(
                user.email, 
                "Welcome to the University Complaint System", 
                html_content
            )
            
            logger.info(f"Welcome email sent to {user.email}")
            
        except Exception as e:
            logger.error(f"Error sending welcome email: {str(e)}")
    
    def send_password_reset_email(self, user: User, reset_token: str):
        """
        Send password reset email
        """
        try:
            reset_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
                    .container { max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                    .header { background-color: #dc2626; color: white; padding: 20px; border-radius: 8px 8px 0 0; margin: -20px -20px 20px -20px; }
                    .title { margin: 0; font-size: 24px; }
                    .content { line-height: 1.6; color: #333; }
                    .button { display: inline-block; background-color: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin: 20px 0; }
                    .warning { background-color: #fef2f2; border: 1px solid #fecaca; padding: 15px; border-radius: 4px; margin: 20px 0; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1 class="title">🔐 Password Reset Request</h1>
                    </div>
                    <div class="content">
                        <p>Hello {{ user_name }},</p>
                        <p>We received a request to reset your password for the University Complaint System.</p>
                        
                        <div class="warning">
                            <strong>⚠️ Security Notice:</strong> If you didn't request this password reset, please ignore this email and contact our support team immediately.
                        </div>
                        
                        <p>To reset your password, click the button below:</p>
                        
                        <a href="http://localhost:3000/reset-password?token={{ reset_token }}" class="button">Reset Password</a>
                        
                        <p>This link will expire in 1 hour for security reasons.</p>
                        
                        <p>If the button doesn't work, copy and paste this link into your browser:</p>
                        <p style="word-break: break-all; background-color: #f8fafc; padding: 10px; border-radius: 4px;">
                            http://localhost:3000/reset-password?token={{ reset_token }}
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            template = Template(reset_template)
            html_content = template.render(
                user_name=user.full_name,
                reset_token=reset_token
            )
            
            self._send_email(
                user.email, 
                "Password Reset Request - University Complaint System", 
                html_content
            )
            
            logger.info(f"Password reset email sent to {user.email}")
            
        except Exception as e:
            logger.error(f"Error sending password reset email: {str(e)}")
    
    def get_notification_preferences(self, db: Session, user_id: int) -> dict:
        """
        Get user's notification preferences (placeholder for future implementation)
        """
        # In a full implementation, this would fetch user preferences from database
        return {
            "email_notifications": True,
            "push_notifications": True,
            "daily_digest": True,
            "instant_alerts": True,
            "complaint_updates": True,
            "assignment_notifications": True
        }
    
    def update_notification_preferences(self, db: Session, user_id: int, preferences: dict):
        """
        Update user's notification preferences (placeholder for future implementation)
        """
        # In a full implementation, this would save preferences to database
        logger.info(f"Updated notification preferences for user {user_id}: {preferences}")
        return True