# Email utility functions
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from decouple import config
import logging

logger = logging.getLogger(__name__)

def send_notification_email(to_email: str, subject: str, message: str):
    """Send email notification"""
    try:
        smtp_host = config("SMTP_HOST", default="smtp.gmail.com")
        smtp_port = config("SMTP_PORT", cast=int, default=587)
        smtp_user = config("SMTP_USER", default="")
        smtp_password = config("SMTP_PASSWORD", default="")
        
        if not smtp_user:
            logger.warning("SMTP not configured, skipping email")
            return False
        
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(message, 'plain'))
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False