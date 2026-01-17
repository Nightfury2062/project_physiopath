"""
RehabAI FastAPI App with Google Gemini AI (Working Version)
Save this as: main.py
Run with: uvicorn main:app --host 0.0.0.0 --port 8001 --reload
"""

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from pathlib import Path
import traceback
import google.generativeai as genai
from datetime import datetime, timedelta
from database import init_database, save_plan, get_all_plans, get_stats
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Initialize FastAPI
app = FastAPI(title="RehabAI API")

# Initialize Database
init_database()

# Database setup
DATABASE_URL = "sqlite:///./rehab_plans.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Model
class RehabPlan(Base):
    __tablename__ = "rehab_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_age = Column(String)
    patient_gender = Column(String)
    surgery_date = Column(String)
    conditions = Column(String, nullable=True)
    additional_notes = Column(Text, nullable=True)
    procedure_identified = Column(String)
    days_post_op = Column(Integer)
    plan_json = Column(Text)  # Store full plan as JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    file_name = Column(String, nullable=True)

# Create tables
Base.metadata.create_all(bind=engine)
print("✅ Database initialized: rehab_plans.db")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini (OLD API - Works!)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Gemini AI initialized (FREE tier)")
else:
    model = None
    print("⚠️  No GEMINI_API_KEY found - using smart mock data")

# Rehab knowledge base
REHAB_PROTOCOLS = {
    "ACL Reconstruction": {
        "phase_1": {
            "name": "Immediate Post-Op (0-2 weeks)",
            "exercises": [
                {"name": "Quad Sets", "reps": "3 sets × 10 reps", "steps": ["Lie on back with leg straight", "Tighten thigh muscle and push knee down", "Hold 5 seconds, relax"], "precautions": ["Stop if sharp pain"]},
                {"name": "Heel Slides", "reps": "3 sets × 15 reps", "steps": ["Lie on back", "Slowly slide heel towards buttocks", "Hold 2 seconds, slide back"], "precautions": ["Do not force beyond comfort"]},
                {"name": "Ankle Pumps", "reps": "3 sets × 20 reps", "steps": ["Point toes up and down", "Perform slowly"], "precautions": ["Can do every 2-3 hours"]}
            ]
        },
        "phase_2": {
            "name": "Early Mobility (2-6 weeks)",
            "exercises": [
                {"name": "Straight Leg Raises", "reps": "3 sets × 10 reps", "steps": ["Lie on back, uninvolved leg bent", "Keep surgical leg straight", "Lift leg 6 inches off ground", "Hold 3 seconds, lower slowly"], "precautions": ["Quad must stay tight"]},
                {"name": "Mini Squats", "reps": "3 sets × 10 reps", "steps": ["Stand with feet shoulder-width", "Bend knees 30-45 degrees only", "Hold 2 seconds, return"], "precautions": ["Use wall support if needed"]}
            ]
        }
    },
    "Spinal Surgery": {
        "phase_1": {
            "name": "Initial Recovery (0-2 weeks)",
            "exercises": [
                {"name": "Diaphragmatic Breathing", "reps": "10 breaths × 3 times daily", "steps": ["Lie on back with knees bent", "Place hand on abdomen", "Breathe deeply, feeling belly rise", "Exhale slowly"], "precautions": ["No breath holding", "Stop if dizzy"]},
                {"name": "Ankle Pumps", "reps": "3 sets × 20 reps", "steps": ["Point toes up and down", "Perform slowly while lying down"], "precautions": ["Keep spine neutral"]},
                {"name": "Gentle Neck Rotations", "reps": "5 each side × 3 times", "steps": ["Sit or lie comfortably", "Slowly turn head left", "Return to center", "Repeat right"], "precautions": ["Very gentle movements only", "Stop if any pain"]}
            ]
        },
        "phase_2": {
            "name": "Early Mobility (2-6 weeks)",
            "exercises": [
                {"name": "Pelvic Tilts", "reps": "3 sets × 10 reps", "steps": ["Lie on back, knees bent", "Flatten lower back against floor", "Hold 5 seconds", "Release"], "precautions": ["No arching", "Gentle movements only"]},
                {"name": "Supine Marching", "reps": "2 sets × 10 each leg", "steps": ["Lie on back", "Slowly lift one knee toward chest", "Lower gently", "Alternate legs"], "precautions": ["Keep spine stable", "Stop if pain increases"]}
            ]
        }
    },
    "Shoulder Surgery": {
        "phase_1": {
            "name": "Immediate Post-Op (0-2 weeks)",
            "exercises": [
                {"name": "Pendulum Swings", "reps": "2 sets × 10 circles each direction", "steps": ["Bend forward at waist", "Let arm hang down", "Gently swing arm in small circles", "Keep shoulder relaxed"], "precautions": ["No active lifting", "Use sling when not exercising"]},
                {"name": "Elbow Flexion/Extension", "reps": "3 sets × 10 reps", "steps": ["Arm at side", "Bend elbow up", "Straighten slowly"], "precautions": ["Keep upper arm still"]},
                {"name": "Hand Grips", "reps": "3 sets × 15 reps", "steps": ["Squeeze a soft ball", "Hold 3 seconds", "Release"], "precautions": ["Keep shoulder relaxed"]}
            ]
        }
    },
    "Hip Replacement": {
        "phase_1": {
            "name": "Initial Recovery (0-2 weeks)",
            "exercises": [
                {"name": "Ankle Pumps", "reps": "3 sets × 20 reps", "steps": ["Point toes up and down", "Perform slowly"], "precautions": ["Can do hourly"]},
                {"name": "Quad Sets", "reps": "3 sets × 10 reps", "steps": ["Tighten thigh muscle", "Hold 5 seconds"], "precautions": ["Keep leg straight"]},
                {"name": "Glute Sets", "reps": "3 sets × 10 reps", "steps": ["Squeeze buttocks together", "Hold 5 seconds", "Release"], "precautions": ["Gentle contraction only"]}
            ]
        }
    }
}


@app.get("/")
async def root():
    return {
        "status": "running",
        "message": "RehabAI with Gemini AI 🚀",
        "ai_enabled": model is not None,
        "version": "2.2.0-gemini-working"
    }


@app.get("/api/stats")
async def get_statistics():
    """Get usage statistics from database"""
    stats = get_stats()
    return {
        "success": True,
        "stats": stats
    }


@app.get("/api/plans")
async def list_plans():
    """Get all stored plans"""
    plans = get_all_plans()
    return {
        "success": True,
        "count": len(plans),
        "plans": [
            {
                "id": p.id,
                "procedure": p.procedure_identified,
                "age": p.patient_age,
                "gender": p.patient_gender,
                "surgery_date": p.surgery_date,
                "created_at": p.created_at.isoformat(),
                "days_post_op": p.days_post_op
            }
            for p in plans
        ]
    }


@app.post("/api/rehab/generate-plan")
async def generate_plan(
    file: UploadFile = File(...),
    patient_info: str = Form(...),
    additional_notes: str = Form(default="")
):
    """Generate personalized rehab plan using Gemini AI"""
    
    print("\n" + "="*60)
    print("📥 NEW PLAN REQUEST")
    print("="*60)
    
    try:
        patient_data = json.loads(patient_info)
        age = patient_data.get('age', 'N/A')
        surgery_date = patient_data.get('surgeryDate', '')
        
        if surgery_date:
            surgery_dt = datetime.strptime(surgery_date, '%Y-%m-%d')
            days_post_op = (datetime.now() - surgery_dt).days
        else:
            days_post_op = 7
        
        file_content = await file.read()
        file_text = file_content.decode('utf-8', errors='ignore') if file_content else ""
        
        print(f"👤 Patient: Age {age}")
        print(f"📅 Days post-op: {days_post_op}")
        print(f"📝 Notes: {additional_notes[:50]}...")
        
        if model:
            print("🤖 Using Gemini AI...")
            
            prompt = f"""You are a post-surgical rehabilitation AI. Analyze this patient and generate a rehab plan.

PATIENT:
- Age: {age}
- Surgery Date: {surgery_date} (Day {days_post_op} post-op)
- Notes: {additional_notes}

AVAILABLE PROTOCOLS:
{json.dumps(REHAB_PROTOCOLS, indent=2)}

TASK:
1. Identify procedure from notes (Spinal Surgery if spine/back mentioned, ACL Reconstruction if knee/ACL, Shoulder Surgery if shoulder, Hip Replacement if hip)
2. Select exercises from ONLY the matching protocol
3. Create 14-day schedule

OUTPUT ONLY THIS JSON (no markdown):
{{
  "procedure_identified": "exact name from protocols",
  "current_phase": "phase_1",
  "days_post_op": {days_post_op},
  "patient_info": {{"age": "{age}", "surgery_date": "{surgery_date}"}},
  "safety_notes": ["guideline 1", "guideline 2", "guideline 3", "guideline 4", "guideline 5"],
  "schedule": [
    {{
      "day": 1,
      "date": "2026-01-18",
      "phase": "phase_1",
      "sessions": [
        {{
          "time": "7:00-7:30 AM",
          "type": "morning",
          "exercises": [
            {{
              "name": "from protocol",
              "reps": "from protocol",
              "duration_minutes": 10,
              "steps": ["from protocol"],
              "precautions": ["from protocol"]
            }}
          ]
        }}
      ]
    }}
  ]
}}

CRITICAL: Use exercises ONLY from protocols. Output raw JSON only."""

            try:
                response = model.generate_content(prompt)
                response_text = response.text.strip()
                
                # Clean markdown
                if response_text.startswith("```"):
                    response_text = response_text.replace("```json", "").replace("```", "").strip()
                
                plan = json.loads(response_text)
                print(f"✅ AI Generated: {plan.get('procedure_identified')}")
                
            except Exception as e:
                print(f"⚠️  AI failed: {e}, using fallback")
                plan = generate_smart_fallback(additional_notes, age, surgery_date, days_post_op)
        else:
            print("⚠️  No API key, using smart fallback")
            plan = generate_smart_fallback(additional_notes, age, surgery_date, days_post_op)
        
        print("✅ Plan ready")
        print("="*60 + "\n")
        
        # Save to database
        plan_id = save_plan(
            patient_info=patient_data,
            procedure=plan.get('procedure_identified', 'Unknown'),
            days_post_op=days_post_op,
            plan=plan,
            file_name=file.filename,
            notes=additional_notes
        )
        
        return {
            "success": True,
            "plan": plan,
            "message": "Rehab plan generated",
            "ai_used": model is not None,
            "plan_id": plan_id
        }
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        print(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to generate plan"
        }


def generate_smart_fallback(notes, age, surgery_date, days_post_op):
    """Fallback with smart detection"""
    notes_lower = notes.lower()
    
    if any(w in notes_lower for w in ['spine', 'spinal', 'back', 'vertebra', 'disk', 'disc']):
        procedure = "Spinal Surgery"
    elif any(w in notes_lower for w in ['shoulder', 'rotator', 'labrum']):
        procedure = "Shoulder Surgery"
    elif any(w in notes_lower for w in ['hip', 'replacement', 'thr']):
        procedure = "Hip Replacement"
    else:
        procedure = "ACL Reconstruction"
    
    protocol = REHAB_PROTOCOLS.get(procedure, REHAB_PROTOCOLS["ACL Reconstruction"])
    phase_key = "phase_1" if days_post_op <= 14 else "phase_2"
    
    safety_map = {
        "Spinal Surgery": [
            "No bending, lifting, or twisting (BLT rule)",
            "Wear back brace as prescribed",
            "Log roll when getting in/out of bed",
            "Stop if increased pain or numbness",
            "Contact surgeon if symptoms worsen"
        ],
        "Shoulder Surgery": [
            "Wear sling except during exercises",
            "No active lifting with surgical arm",
            "Sleep in reclined position",
            "Ice 3-4 times daily",
            "Follow all restrictions"
        ],
        "Hip Replacement": [
            "No bending past 90°, crossing legs, or internal rotation",
            "Use elevated toilet seat",
            "Sleep with pillow between legs",
            "Use walker/crutches as prescribed",
            "Watch for dislocation signs"
        ],
        "ACL Reconstruction": [
            "Partial weight bearing (50%) with crutches",
            "Avoid pivoting or twisting",
            "Ice 3-4 times daily for 20 minutes",
            "Elevate leg when resting",
            "Contact PT if sharp pain or swelling"
        ]
    }
    
    plan = {
        "procedure_identified": procedure,
        "current_phase": phase_key,
        "days_post_op": days_post_op,
        "patient_info": {"age": age, "surgery_date": surgery_date},
        "safety_notes": safety_map[procedure],
        "schedule": []
    }
    
    start_date = datetime.now()
    exercises = protocol.get(phase_key, protocol["phase_1"])["exercises"]
    
    for day in range(1, 15):
        day_date = (start_date + timedelta(days=day-1)).strftime('%Y-%m-%d')
        sessions = []
        
        morning_ex = exercises[:2] if len(exercises) >= 2 else exercises
        sessions.append({
            "time": "7:00-7:30 AM",
            "type": "morning",
            "exercises": [
                {
                    "name": ex["name"],
                    "reps": ex["reps"],
                    "duration_minutes": 8 + idx*2,
                    "steps": ex["steps"],
                    "precautions": ex["precautions"]
                }
                for idx, ex in enumerate(morning_ex)
            ]
        })
        
        if len(exercises) > 2:
            evening_ex = exercises[2:4]
            sessions.append({
                "time": "7:00-7:30 PM",
                "type": "evening",
                "exercises": [
                    {
                        "name": ex["name"],
                        "reps": ex["reps"],
                        "duration_minutes": 8 + idx*2,
                        "steps": ex["steps"],
                        "precautions": ex["precautions"]
                    }
                    for idx, ex in enumerate(evening_ex)
                ]
            })
        
        plan["schedule"].append({
            "day": day,
            "date": day_date,
            "phase": phase_key,
            "sessions": sessions
        })
    
    return plan


if __name__ == "__main__":
    import uvicorn
    print("\n🚀 RehabAI Server Starting...")
    uvicorn.run(app, host="0.0.0.0", port=8001)