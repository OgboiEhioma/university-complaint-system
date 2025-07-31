import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile
from typing import Optional
from PIL import Image
import magic
from decouple import config

# Configuration
UPLOAD_DIR = config("UPLOAD_DIR", default="uploads")
MAX_FILE_SIZE = config("MAX_FILE_SIZE", cast=int, default=10485760)  # 10MB
ALLOWED_EXTENSIONS = config("ALLOWED_EXTENSIONS", default="pdf,jpg,jpeg,png,doc,docx,txt").split(",")
USE_S3 = config("USE_S3", cast=bool, default=False)

def ensure_upload_directory():
    """
    Ensure upload directory exists
    """
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

def generate_unique_filename(original_filename: str) -> str:
    """
    Generate unique filename while preserving extension
    """
    file_extension = original_filename.split('.')[-1].lower()
    unique_name = f"{uuid.uuid4().hex}.{file_extension}"
    return unique_name

def validate_file(file: UploadFile) -> tuple[bool, str]:
    """
    Validate uploaded file
    Returns: (is_valid, error_message)
    """
    # Check if file has content
    if not file.filename:
        return False, "No file selected"
    
    # Check file extension
    file_extension = file.filename.split('.')[-1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        return False, f"File type '{file_extension}' not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # Check file size
    if hasattr(file, 'size') and file.size > MAX_FILE_SIZE:
        return False, f"File size too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.1f}MB"
    
    return True, ""

def save_uploaded_file(file: UploadFile, complaint_id: int) -> str:
    """
    Save uploaded file to disk
    Returns: file_path
    """
    # Validate file
    is_valid, error_msg = validate_file(file)
    if not is_valid:
        raise ValueError(error_msg)
    
    # Ensure upload directory exists
    ensure_upload_directory()
    
    # Create complaint-specific directory
    complaint_dir = Path(UPLOAD_DIR) / f"complaint_{complaint_id}"
    complaint_dir.mkdir(exist_ok=True)
    
    # Generate unique filename
    unique_filename = generate_unique_filename(file.filename)
    file_path = complaint_dir / unique_filename
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Validate file content (basic check)
        validate_file_content(file_path)
        
        return str(file_path)
    
    except Exception as e:
        # Clean up if something went wrong
        if file_path.exists():
            file_path.unlink()
        raise ValueError(f"Failed to save file: {str(e)}")

def validate_file_content(file_path: Path) -> bool:
    """
    Validate file content using python-magic
    """
    try:
        # Get file MIME type
        mime_type = magic.from_file(str(file_path), mime=True)
        
        # Define allowed MIME types
        allowed_mime_types = {
            'pdf': 'application/pdf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'txt': 'text/plain'
        }
        
        file_extension = file_path.suffix.lower().lstrip('.')
        expected_mime = allowed_mime_types.get(file_extension)
        
        if expected_mime and mime_type != expected_mime:
            # For images, be more flexible
            if file_extension in ['jpg', 'jpeg', 'png'] and mime_type.startswith('image/'):
                return True
            # For text files, be flexible
            elif file_extension == 'txt' and mime_type.startswith('text/'):
                return True
            else:
                raise ValueError(f"File content doesn't match extension. Expected: {expected_mime}, Got: {mime_type}")
        
        return True
    
    except Exception as e:
        print(f"File validation warning: {str(e)}")
        return True  # Don't block upload for validation issues

def delete_file(file_path: str) -> bool:
    """
    Delete file from disk
    """
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            return True
        return False
    except Exception as e:
        print(f"Error deleting file {file_path}: {str(e)}")
        return False

def get_file_info(file_path: str) -> dict:
    """
    Get file information
    """
    path = Path(file_path)
    if not path.exists():
        return {}
    
    stat = path.stat()
    return {
        "filename": path.name,
        "size": stat.st_size,
        "created": stat.st_ctime,
        "modified": stat.st_mtime,
        "extension": path.suffix.lower().lstrip('.'),
        "mime_type": magic.from_file(str(path), mime=True) if magic else "unknown"
    }

def create_thumbnail(image_path: str, max_size: tuple = (300, 300)) -> Optional[str]:
    """
    Create thumbnail for image files
    """
    try:
        path = Path(image_path)
        if path.suffix.lower() not in ['.jpg', '.jpeg', '.png']:
            return None
        
        # Create thumbnail directory
        thumb_dir = path.parent / "thumbnails"
        thumb_dir.mkdir(exist_ok=True)
        
        # Generate thumbnail path
        thumb_path = thumb_dir / f"thumb_{path.name}"
        
        # Create thumbnail
        with Image.open(path) as img:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            img.save(thumb_path, optimize=True, quality=85)
        
        return str(thumb_path)
    
    except Exception as e:
        print(f"Error creating thumbnail: {str(e)}")
        return None

def clean_old_files(days_old: int = 30):
    """
    Clean up old files (for maintenance)
    """
    try:
        upload_path = Path(UPLOAD_DIR)
        if not upload_path.exists():
            return
        
        import time
        cutoff_time = time.time() - (days_old * 24 * 60 * 60)
        
        deleted_count = 0
        for file_path in upload_path.rglob("*"):
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting old file {file_path}: {str(e)}")
        
        print(f"Cleaned up {deleted_count} old files")
        return deleted_count
    
    except Exception as e:
        print(f"Error during cleanup: {str(e)}")
        return 0

def get_upload_stats() -> dict:
    """
    Get upload directory statistics
    """
    try:
        upload_path = Path(UPLOAD_DIR)
        if not upload_path.exists():
            return {"total_files": 0, "total_size": 0}
        
        total_files = 0
        total_size = 0
        
        for file_path in upload_path.rglob("*"):
            if file_path.is_file():
                total_files += 1
                total_size += file_path.stat().st_size
        
        return {
            "total_files": total_files,
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "upload_dir": str(upload_path.absolute())
        }
    
    except Exception as e:
        print(f"Error getting upload stats: {str(e)}")
        return {"error": str(e)}

# S3 Upload functions (if using AWS S3)
if USE_S3:
    import boto3
    from botocore.exceptions import ClientError
    
    # S3 Configuration
    AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
    AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
    AWS_BUCKET_NAME = config("AWS_BUCKET_NAME", default="")
    AWS_REGION = config("AWS_REGION", default="us-east-1")
    
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
    
    def upload_to_s3(file_path: str, s3_key: str) -> bool:
        """
        Upload file to S3
        """
        try:
            s3_client.upload_file(file_path, AWS_BUCKET_NAME, s3_key)
            return True
        except ClientError as e:
            print(f"Error uploading to S3: {str(e)}")
            return False
    
    def delete_from_s3(s3_key: str) -> bool:
        """
        Delete file from S3
        """
        try:
            s3_client.delete_object(Bucket=AWS_BUCKET_NAME, Key=s3_key)
            return True
        except ClientError as e:
            print(f"Error deleting from S3: {str(e)}")
            return False
    
    def generate_presigned_url(s3_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate presigned URL for S3 object
        """
        try:
            response = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': AWS_BUCKET_NAME, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            print(f"Error generating presigned URL: {str(e)}")
            return None

# File serving functions
def serve_file(file_path: str, filename: str = None):
    """
    Serve file for download
    """
    from fastapi.responses import FileResponse
    
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError("File not found")
    
    return FileResponse(
        path=file_path,
        filename=filename or path.name,
        media_type='application/octet-stream'
    )

def compress_file(file_path: str, compression_level: int = 6) -> str:
    """
    Compress file using gzip
    """
    import gzip
    
    compressed_path = f"{file_path}.gz"
    
    try:
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb', compresslevel=compression_level) as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        return compressed_path
    
    except Exception as e:
        print(f"Error compressing file: {str(e)}")
        return file_path

def extract_text_from_file(file_path: str) -> str:
    """
    Extract text content from files (for indexing/search)
    """
    path = Path(file_path)
    extension = path.suffix.lower()
    
    try:
        if extension == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        elif extension == '.pdf':
            try:
                import PyPDF2
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text()
                    return text
            except ImportError:
                print("PyPDF2 not installed - cannot extract PDF text")
                return ""
        
        elif extension in ['.doc', '.docx']:
            try:
                import docx
                doc = docx.Document(file_path)
                return '\n'.join([paragraph.text for paragraph in doc.paragraphs])
            except ImportError:
                print("python-docx not installed - cannot extract Word text")
                return ""
        
        else:
            return ""
    
    except Exception as e:
        print(f"Error extracting text from {file_path}: {str(e)}")
        return ""

# Security functions
def scan_file_for_viruses(file_path: str) -> bool:
    """
    Basic file security scan (placeholder for antivirus integration)
    """
    # In production, integrate with ClamAV or similar
    path = Path(file_path)
    
    # Basic checks
    if path.stat().st_size == 0:
        return False  # Empty files are suspicious
    
    # Check for suspicious extensions
    suspicious_extensions = ['.exe', '.bat', '.cmd', '.scr', '.pif', '.com']
    if path.suffix.lower() in suspicious_extensions:
        return False
    
    # Add more sophisticated checks here
    return True

def quarantine_file(file_path: str) -> str:
    """
    Move suspicious file to quarantine directory
    """
    path = Path(file_path)
    quarantine_dir = Path(UPLOAD_DIR) / "quarantine"
    quarantine_dir.mkdir(exist_ok=True)
    
    quarantine_path = quarantine_dir / f"quarantined_{path.name}"
    shutil.move(str(path), str(quarantine_path))
    
    return str(quarantine_path)