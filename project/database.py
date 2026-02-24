from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite database file will be created in your project folder
DATABASE_URL = "sqlite:///./arogyapath.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── USER TABLE ───────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id                 = Column(Integer, primary_key=True, index=True)
    name               = Column(String, nullable=False)
    age                = Column(Integer, nullable=False)
    gender             = Column(String, nullable=False)
    mobile             = Column(String, unique=True, nullable=False)
    password           = Column(String, nullable=False)        # hashed

    # Category: "disabled" or "senior"
    category           = Column(String, nullable=False)

    # Disabled sub-type: "wheelchair" or "blind"
    disability_type    = Column(String, nullable=True)

    # Emergency contacts (stored as "Name:Number,Name:Number")
    emergency_contacts = Column(String, nullable=True)


# ─── CREATE TABLES ────────────────────────────────────────────────
def init_db():
    Base.metadata.create_all(bind=engine)


# ─── DB SESSION DEPENDENCY ────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── HELPER FUNCTIONS ─────────────────────────────────────────────
def get_user_by_mobile(db, mobile: str):
    return db.query(User).filter(User.mobile == mobile).first()


def get_user_by_id(db, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def create_user(db, name, age, gender, mobile, hashed_password,
                category, disability_type=None, emergency_contacts=None):
    user = User(
        name=name,
        age=age,
        gender=gender,
        mobile=mobile,
        password=hashed_password,
        category=category,
        disability_type=disability_type,
        emergency_contacts=emergency_contacts,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user