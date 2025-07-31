from sqlalchemy import create_engine, text  # ✅ Add text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from decouple import config

# ✅ Get database URL from environment or fallback default
DATABASE_URL = config("DATABASE_URL", default="postgresql://postgres:password@localhost:5432/complaint_system")

# ✅ SQLAlchemy engine setup
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    pool_pre_ping=True,
    echo=config("DB_ECHO", default=False, cast=bool)
)

# ✅ Session class for DB access
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ✅ Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency to get database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_database():
    """
    Create all database tables.
    """
    from app.models.models import Base
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")


def drop_database():
    """
    Drop all database tables (use with caution!).
    """
    from app.models.models import Base
    Base.metadata.drop_all(bind=engine)
    print("⚠️ All database tables dropped!")


def test_connection():
    """
    Test database connection.
    """
    try:
        with engine.connect() as connection:
            # ✅ Wrap raw SQL in text()
            connection.execute(text("SELECT 1"))
            print("✅ Database connection successful!")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
