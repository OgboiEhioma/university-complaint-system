from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session
import time
import logging
from pathlib import Path

# Import our modules
from app.api.v1.routes import router as api_router
from app.db.database import create_database, test_connection, get_db
from app.core.security import verify_token
from app.models import models
from app.crud import crud
from app.schemas.schemas import UniversityCreate, UserCreate
from app.models.models import UserRole

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create FastAPI app (single instance)
app = FastAPI(
    title="University Complaint System",
    description="A comprehensive complaint management system for universities",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Match frontend URL
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Trust host middleware (for security)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.localhost"]
)

# Custom middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} - {process_time:.4f}s")
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-API-Version"] = "1.0.0"
    return response

# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error_code": exc.status_code
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation Error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation error",
            "errors": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error": str(exc) if app.debug else "An unexpected error occurred"
        }
    )

# Mount static files
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount uploads directory
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include API routes
app.include_router(api_router, prefix="/api/v1", tags=["API v1"])

# Root endpoints
@app.get("/")
async def root():
    return {
        "message": "University Complaint System API",
        "version": "1.0.0",
        "status": "active",
        "docs": "/docs",
        "api_prefix": "/api/v1"
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_status = "unhealthy"
    return {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "timestamp": time.time(),
        "database": db_status,
        "version": "1.0.0"
    }

@app.get("/stats")
async def get_system_stats(db: Session = Depends(get_db)):
    try:
        total_universities = db.query(models.University).count()
        total_users = db.query(models.User).count()
        total_complaints = db.query(models.Complaint).count()
        active_complaints = db.query(models.Complaint).filter(
            models.Complaint.status != models.ComplaintStatus.RESOLVED
        ).count()
        return {
            "total_universities": total_universities,
            "total_users": total_users,
            "total_complaints": total_complaints,
            "active_complaints": active_complaints,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        return {"error": "Unable to fetch system statistics"}

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting University Complaint System API...")
    if test_connection():
        logger.info("✅ Database connection successful")
    else:
        logger.error("❌ Database connection failed")
        return
    try:
        create_database()
        logger.info("✅ Database tables ready")
    except Exception as e:
        logger.error(f"❌ Database setup failed: {str(e)}")
        return
    try:
        await create_default_data()
        logger.info("✅ Default data initialized")
    except Exception as e:
        logger.error(f"❌ Default data creation failed: {str(e)}")
    logger.info("🎉 Application startup completed successfully!")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Shutting down University Complaint System API...")
    logger.info("👋 Application shutdown completed")

async def create_default_data():
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        if db.query(models.University).count() > 0:
            return
        university_data = UniversityCreate(
            name="Demo University",
            code="DEMO",
            domain="demo.edu",
            address="123 University Ave, Demo City, DC 12345",
            phone="+1-555-0123",
            email="admin@demo.edu"
        )
        university = crud.university.create(db, obj_in=university_data)
        logger.info(f"Created default university: {university.name}")
        admin_data = UserCreate(
            email="admin@demo.edu",
            username="admin",
            full_name="System Administrator",
            password="admin123456",
            role=UserRole.SUPER_ADMIN,
            university_id=university.id
        )
        admin_user = crud.user.create(db, obj_in=admin_data)
        logger.info(f"Created default admin user: {admin_user.username}")
        student_data = UserCreate(
            email="student@demo.edu",
            username="student",
            full_name="Demo Student",
            password="student123",
            role=UserRole.STUDENT,
            student_id="STU001",
            university_id=university.id
        )
        student_user = crud.user.create(db, obj_in=student_data)
        logger.info(f"Created demo student user: {student_user.username}")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating default data: {str(e)}")
        raise
    finally:
        db.close()

@app.post("/api/v1/system/reset-demo-data")
async def reset_demo_data(db: Session = Depends(get_db)):
    try:
        db.query(models.Activity).delete()
        db.query(models.Message).delete()
        db.query(models.Attachment).delete()
        db.query(models.Notification).delete()
        db.query(models.Complaint).delete()
        db.query(models.User).delete()
        db.query(models.Department).delete()
        db.query(models.University).delete()
        db.commit()
        await create_default_data()
        return {"success": True, "message": "Demo data reset successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error resetting demo data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset demo data")

@app.get("/api/v1/system/backup")
async def create_backup():
    return {
        "success": True,
        "message": "Backup functionality not implemented yet",
        "timestamp": time.time()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )