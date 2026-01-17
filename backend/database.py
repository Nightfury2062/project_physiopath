"""
Database module for RehabAI
Handles all data storage and tracking
"""

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Database configuration
DATABASE_URL = "sqlite:///./rehab_plans.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class RehabPlan(Base):
    """Model for storing generated rehab plans"""
    __tablename__ = "rehab_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_age = Column(String)
    patient_gender = Column(String)
    surgery_date = Column(String)
    conditions = Column(String, nullable=True)
    additional_notes = Column(Text, nullable=True)
    procedure_identified = Column(String)
    days_post_op = Column(Integer)
    plan_json = Column(Text)  # Full plan stored as JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    file_name = Column(String, nullable=True)


def init_database():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized: rehab_plans.db")


def save_plan(patient_info: dict, procedure: str, days_post_op: int, 
              plan: dict, file_name: str = None, notes: str = None):
    """
    Save a generated rehab plan to database
    
    Args:
        patient_info: Dict with age, gender, surgeryDate, conditions
        procedure: Identified procedure name
        days_post_op: Days since surgery
        plan: Full rehab plan dict
        file_name: Name of uploaded file
        notes: Additional notes from patient
    
    Returns:
        Database record ID
    """
    db = SessionLocal()
    try:
        import json
        
        db_plan = RehabPlan(
            patient_age=patient_info.get('age', 'N/A'),
            patient_gender=patient_info.get('gender', 'N/A'),
            surgery_date=patient_info.get('surgeryDate', ''),
            conditions=patient_info.get('conditions', ''),
            additional_notes=notes or '',
            procedure_identified=procedure,
            days_post_op=days_post_op,
            plan_json=json.dumps(plan),
            file_name=file_name
        )
        
        db.add(db_plan)
        db.commit()
        db.refresh(db_plan)
        
        print(f"💾 Saved plan to database (ID: {db_plan.id})")
        return db_plan.id
        
    except Exception as e:
        print(f"❌ Database save failed: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def get_all_plans():
    """Retrieve all stored plans"""
    db = SessionLocal()
    try:
        plans = db.query(RehabPlan).all()
        return plans
    finally:
        db.close()


def get_plan_by_id(plan_id: int):
    """Get a specific plan by ID"""
    db = SessionLocal()
    try:
        plan = db.query(RehabPlan).filter(RehabPlan.id == plan_id).first()
        return plan
    finally:
        db.close()


def get_stats():
    """Get usage statistics"""
    db = SessionLocal()
    try:
        total_plans = db.query(RehabPlan).count()
        
        # Count by procedure
        from sqlalchemy import func
        procedures = db.query(
            RehabPlan.procedure_identified,
            func.count(RehabPlan.id)
        ).group_by(RehabPlan.procedure_identified).all()
        
        # Average age
        avg_age = db.query(func.avg(RehabPlan.patient_age)).scalar()
        
        return {
            "total_plans": total_plans,
            "procedures": dict(procedures),
            "average_age": avg_age
        }
    finally:
        db.close()