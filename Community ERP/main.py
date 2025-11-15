from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo.database import Database
from typing import Optional
from datetime import datetime, timedelta
import os
import sys
import shutil
from dotenv import load_dotenv
from PIL import Image
import numpy as np
import cv2
import io

# Add saved_models to path
sys.path.append(os.path.join(os.path.dirname(__file__), "saved_models"))
from backend_model_loader import ModelLoader

import schemas
import crud
from database import get_db
from auth import (
    create_student_token, 
    create_admin_token, 
    get_current_user, 
    get_current_student, 
    get_current_admin
)

# Load environment variables
load_dotenv()

# Initialize BLIP-2 and PaddleOCR models
print("Initializing models...")
models = ModelLoader(
    blip2_path=os.path.join(os.path.dirname(__file__), "saved_models", "blip2-opt-2.7b"),
    device="cuda"  # Change to "cpu" if no GPU available
)
print("✅ Models loaded successfully!")

# Initialize FastAPI app
app = FastAPI(
    title="Community ERP System",
    version="2.0.0",
    description="Student Management System with Authentication, Skills, Projects, and Admin Verification"
)

# CORS Middleware - Allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# File upload configuration
UPLOAD_DIR = "uploads/certificates"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==================== IMAGE PREPROCESSING HELPER ====================
def preprocess_image(image_bytes: bytes) -> Image.Image:
    """
    Preprocess image: resize, handle orientation, normalize
    Returns: PIL Image ready for processing
    """
    # Load image from bytes
    image = Image.open(io.BytesIO(image_bytes))
    
    # Handle EXIF orientation (auto-rotate based on metadata)
    try:
        from PIL import ImageOps
        image = ImageOps.exif_transpose(image)
    except Exception as e:
        print(f"EXIF orientation handling failed: {e}")
    
    # Convert to RGB if needed
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Resize if too large (max dimension 1920px while maintaining aspect ratio)
    max_dimension = 1920
    if max(image.size) > max_dimension:
        ratio = max_dimension / max(image.size)
        new_size = tuple(int(dim * ratio) for dim in image.size)
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    return image


# ==================== BLIP-2 + PADDLEOCR VERIFICATION ====================
async def verify_college_id_with_models(image_bytes: bytes, student_name: str, roll_no: str) -> tuple[bool, str, str]:
    """
    Use BLIP-2 to verify if the image is a college ID card,
    then use PaddleOCR to extract and verify name and roll number.
    Returns: (is_valid, message, extracted_college_id)
    """
    try:
        # Step 1: Preprocess image
        image = preprocess_image(image_bytes)
        
        # Step 2: Use BLIP-2 to verify if it's a college ID (reduced keywords for faster check)
        caption_prompt = "Question: Is this a college ID card or student identification card? Answer:"
        caption = models.generate_caption(image, prompt=caption_prompt)
        
        print(f"BLIP-2 Caption: {caption}")
        
        # Check if BLIP-2 confirms it's a college ID (only 3 key checks)
        caption_lower = caption.lower()
        is_id_card = any(keyword in caption_lower for keyword in [
            'yes', 'id', 'student'
        ])
        
        if not is_id_card:
            return False, "The uploaded image does not appear to be a valid college ID card", ""
        
        # Step 3: Extract text using PaddleOCR
        ocr_data = models.extract_text(image)
        extracted_text = ocr_data['full_text'].lower()
        
        print(f"OCR Extracted Text: {extracted_text}")
        
        if not extracted_text:
            return False, "Could not extract any text from the ID card. Please upload a clearer image", ""
        
        # Step 4: Verify student name (flexible matching - reduced threshold to 60%)
        student_name_lower = student_name.lower()
        name_parts = student_name_lower.split()
        
        # Check if at least 60% of name parts are present
        matched_parts = sum(1 for part in name_parts if len(part) > 2 and part in extracted_text)
        name_match_ratio = matched_parts / len(name_parts) if name_parts else 0
        
        if name_match_ratio < 0.6:
            return False, f"Student name '{student_name}' does not match the name on the ID card. Please ensure the name matches your registration.", ""
        
        # Step 5: Verify roll number (flexible matching - reduced threshold to 60%)
        roll_no_clean = roll_no.lower().replace(" ", "").replace("-", "").replace("_", "")
        extracted_clean = extracted_text.replace(" ", "").replace("-", "").replace("_", "")
        
        if roll_no_clean not in extracted_clean:
            # Try partial match (at least 60% of roll number characters)
            matched_chars = sum(1 for char in roll_no_clean if char in extracted_clean)
            roll_match_ratio = matched_chars / len(roll_no_clean) if roll_no_clean else 0
            
            if roll_match_ratio < 0.6:
                return False, f"Roll number '{roll_no}' does not match the ID on the card. Please verify your roll number and try again.", ""
        
        # Step 6: Extract college ID from OCR text (return full extracted text as college ID)
        extracted_college_id = ocr_data['full_text'].strip()
        
        # All checks passed
        return True, "College ID verified successfully", extracted_college_id
        
    except Exception as e:
        print(f"College ID verification error: {str(e)}")
        return False, f"Error processing college ID: {str(e)}", ""


# ==================== CERTIFICATE VERIFICATION ====================
async def verify_college_id_with_ai(image_bytes: bytes, mime_type: str, student_name: str, roll_no: str) -> tuple[bool, str, str]:
    """
    Wrapper function for backward compatibility - uses BLIP-2 + PaddleOCR verification
    Returns: (is_valid, message, extracted_college_id)
    """
    return await verify_college_id_with_models(image_bytes, student_name, roll_no)


async def verify_certificate_with_ai(image_bytes: bytes, mime_type: str, student_name: str, skill_or_achievement: str, description: Optional[str] = None) -> tuple[bool, str, dict]:
    """
    Use BLIP-2 to verify certificate validity, then PaddleOCR to verify details.
    Description format: "Institution Name - Skill/Achievement Name"
    Returns: (is_valid, message, confidence_scores)
    """
    try:
        # Step 1: Preprocess image
        image = preprocess_image(image_bytes)
        
        # Step 2: Use BLIP-2 to verify if it's a valid certificate (only 3 key checks)
        caption_prompt = "Question: Is this a certificate, award, or achievement document? Answer:"
        caption = models.generate_caption(image, prompt=caption_prompt)
        
        print(f"BLIP-2 Certificate Caption: {caption}")
        
        # Check if BLIP-2 confirms it's a certificate (reduced to 3 keywords)
        caption_lower = caption.lower()
        is_certificate = any(keyword in caption_lower for keyword in [
            'yes', 'certificate', 'award'
        ])
        
        # Initialize confidence scores
        confidence_scores = {
            "overall_confidence": 0.0,
            "image_type_match": 0.0,
            "student_name_match": 0.0,
            "institution_match": 0.0,
            "skill_match": 0.0,
            "ocr_confidence": 0.0
        }
        
        # Image type confidence (BLIP-2 check)
        if is_certificate:
            confidence_scores["image_type_match"] = 1.0
        else:
            confidence_scores["image_type_match"] = 0.0
            confidence_scores["overall_confidence"] = 0.0
            return False, "The uploaded image does not appear to be a valid certificate", confidence_scores
        
        # Step 3: Extract text using PaddleOCR
        ocr_data = models.extract_text(image)
        extracted_text = ocr_data['full_text'].lower()
        
        print(f"OCR Extracted Text (Certificate): {extracted_text}")
        
        # Calculate average OCR confidence
        if ocr_data['confidence_scores']:
            avg_ocr_confidence = sum(ocr_data['confidence_scores']) / len(ocr_data['confidence_scores'])
            confidence_scores["ocr_confidence"] = round(avg_ocr_confidence, 2)
        else:
            confidence_scores["ocr_confidence"] = 0.0
        
        if not extracted_text:
            confidence_scores["overall_confidence"] = confidence_scores["ocr_confidence"] * 0.2
            return False, "Could not extract any text from the certificate. Please upload a clearer image", confidence_scores
        
        # Step 4: Verify student name (60% match)
        student_name_lower = student_name.lower()
        name_parts = student_name_lower.split()
        
        if name_parts:
            matched_name_parts = sum(1 for part in name_parts if len(part) > 2 and part in extracted_text)
            name_match_ratio = matched_name_parts / len(name_parts)
            confidence_scores["student_name_match"] = round(name_match_ratio, 2)
            
            if name_match_ratio < 0.6:
                confidence_scores["overall_confidence"] = round(
                    (confidence_scores["image_type_match"] * 0.25 + 
                     confidence_scores["student_name_match"] * 0.25 + 
                     confidence_scores["ocr_confidence"] * 0.5), 2
                )
                return False, f"Student name '{student_name}' does not match the name on the certificate", confidence_scores
        else:
            confidence_scores["student_name_match"] = 1.0
        
        # Step 5: Parse description if provided (format: "Institution - Skill/Achievement")
        institution_name = None
        expected_skill = skill_or_achievement.lower()
        
        if description and " - " in description:
            parts = description.split(" - ", 1)
            institution_name = parts[0].strip().lower()
            expected_skill = parts[1].strip().lower()
        
        # Step 6: Verify institution name if provided (60% match)
        if institution_name:
            institution_words = [w for w in institution_name.split() if len(w) > 2]
            if institution_words:
                matched_inst_words = sum(1 for word in institution_words if word in extracted_text)
                inst_match_ratio = matched_inst_words / len(institution_words)
                confidence_scores["institution_match"] = round(inst_match_ratio, 2)
                
                if inst_match_ratio < 0.6:
                    confidence_scores["overall_confidence"] = round(
                        (confidence_scores["image_type_match"] * 0.2 + 
                         confidence_scores["student_name_match"] * 0.2 + 
                         confidence_scores["institution_match"] * 0.2 + 
                         confidence_scores["ocr_confidence"] * 0.4), 2
                    )
                    return False, f"Institution name '{institution_name}' does not match the certificate content", confidence_scores
            else:
                confidence_scores["institution_match"] = 1.0  # No words to check
        else:
            confidence_scores["institution_match"] = 1.0  # Not checking
        
        # Step 7: Verify skill/achievement name after hyphen (60% match)
        skill_words = [w for w in expected_skill.split() if len(w) > 2]
        
        if skill_words:
            matched_skill_words = sum(1 for word in skill_words if word in extracted_text)
            skill_match_ratio = matched_skill_words / len(skill_words)
            confidence_scores["skill_match"] = round(skill_match_ratio, 2)
            
            if skill_match_ratio < 0.6:
                confidence_scores["overall_confidence"] = round(
                    (confidence_scores["image_type_match"] * 0.2 + 
                     confidence_scores["student_name_match"] * 0.2 + 
                     confidence_scores["institution_match"] * 0.15 + 
                     confidence_scores["skill_match"] * 0.2 + 
                     confidence_scores["ocr_confidence"] * 0.25), 2
                )
                return False, f"Skill/Achievement '{expected_skill}' does not match the certificate content", confidence_scores
        else:
            confidence_scores["skill_match"] = 1.0  # No words to check
        
        # Calculate overall confidence (weighted average)
        confidence_scores["overall_confidence"] = round(
            (confidence_scores["image_type_match"] * 0.2 + 
             confidence_scores["student_name_match"] * 0.2 + 
             confidence_scores["institution_match"] * 0.15 + 
             confidence_scores["skill_match"] * 0.2 + 
             confidence_scores["ocr_confidence"] * 0.25), 2
        )
        
        # All checks passed
        return True, "Certificate verified successfully", confidence_scores
        
    except Exception as e:
        print(f"Certificate verification error: {str(e)}")
        confidence_scores = {
            "overall_confidence": 0.0,
            "image_type_match": 0.0,
            "student_name_match": 0.0,
            "institution_match": 0.0,
            "skill_match": 0.0,
            "ocr_confidence": 0.0
        }
        return False, f"Error processing certificate: {str(e)}", confidence_scores


# ==================== ROOT ====================
@app.get("/", tags=["Root"])
def read_root():
    return {
        "message": "Welcome to Community ERP System!",
        "version": "2.0.0",
        "docs": "/docs",
        "features": [
            "Student & College Management",
            "Authentication (Student + Admin)",
            "Skills & Achievements with Certificates",
            "Projects with GitHub Links",
            "Admin Verification System",
            "College ID Upload (Mandatory)"
        ]
    }


# ==================== AUTHENTICATION ENDPOINTS ====================
@app.post("/auth/student/login", tags=["Authentication"])
def student_login(credentials: schemas.StudentLogin, db: Database = Depends(get_db)):
    """Student login endpoint. Returns JWT token and student profile if credentials are valid."""
    student = crud.authenticate_student(credentials.roll_no, credentials.password, db)
    if not student:
        raise HTTPException(status_code=401, detail="Invalid roll number or password")
    
    # Create JWT token with student info using dedicated function
    access_token = create_student_token(
        roll_no=credentials.roll_no,
        name=student.get("name"),
        college_name=student.get("college_name")
    )
    
    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "student": crud.get_student_by_roll_no(credentials.roll_no, db)
    }


@app.post("/auth/college/login", tags=["Authentication"])
def college_admin_login(credentials: schemas.CollegeLogin, db: Database = Depends(get_db)):
    """College admin login endpoint. Returns JWT token and college info if credentials are valid."""
    college = crud.authenticate_college_admin(credentials.college_id, credentials.admin_password, db)
    if not college:
        raise HTTPException(status_code=401, detail="Invalid college ID or password")
    
    # Create JWT token with admin info using dedicated function
    access_token = create_admin_token(
        college_id=credentials.college_id,
        college_name=college.get("name", "Unknown College")
    )
    
    return {
        "message": "Admin login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "college": {
            "id": college.get("id"),
            "name": college.get("name"),
            "college_id": college.get("college_id"),
            "contact_email": college.get("contact_email"),
            "contact_phone": college.get("contact_phone"),
            "address": college.get("address")
        }
    }


# ==================== COLLEGE ENDPOINTS ====================
@app.post("/colleges/", response_model=schemas.CollegeOut, tags=["Colleges"])
def register_college(college: schemas.CollegeCreate, db: Database = Depends(get_db)):
    """Register a new college. Must be done before students can register."""
    try:
        return crud.create_college(college, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/colleges/", tags=["Colleges"])
def get_all_colleges(db: Database = Depends(get_db)):
    """Get list of all registered colleges."""
    return crud.get_colleges(db)


# ==================== STUDENT ENDPOINTS ====================
@app.post("/students/", tags=["Students"])
def create_student(student: schemas.StudentCreate, db: Database = Depends(get_db)):
    """
    Create a new student profile with basic information.
    College must be registered first.
    College ID picture must be uploaded separately using /students/{roll_no}/upload-college-id/
    """
    college = crud.get_college_by_name(student.college_name, db)
    if not college:
        raise HTTPException(
            status_code=400,
            detail=f"College '{student.college_name}' is not registered. Register it first at POST /colleges/"
        )
    
    try:
        return crud.create_student(student, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/students/", tags=["Students"])
def get_all_students(college_name: str, db: Database = Depends(get_db)):
    """Get all students from a specific college. College name is required."""
    students = crud.get_all_students(db, college_name)
    if not students:
        raise HTTPException(status_code=404, detail=f"No students found for college '{college_name}'")
    return students


@app.get("/students/{roll_no}", tags=["Students"])
def get_student(roll_no: str, db: Database = Depends(get_db)):
    """Get detailed student profile by roll number."""
    student = crud.get_student_by_roll_no(roll_no, db)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@app.put("/students/{roll_no}", tags=["Students"])
def update_student(roll_no: str, student_update: schemas.StudentUpdate, db: Database = Depends(get_db)):
    """Update student information."""
    result = crud.update_student(roll_no, student_update, db)
    if not result:
        raise HTTPException(status_code=404, detail="Student not found")
    return result


@app.delete("/students/{roll_no}", tags=["Students"])
def delete_student(roll_no: str, db: Database = Depends(get_db)):
    """Delete a student."""
    success = crud.delete_student(roll_no, db)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student deleted successfully"}


@app.get("/students/search/{name}", tags=["Students"])
def search_students(name: str, db: Database = Depends(get_db)):
    """Search students by name."""
    students = crud.search_students_by_name(name, db)
    if not students:
        raise HTTPException(status_code=404, detail="No students found")
    return students


@app.post("/students/{roll_no}/upload-college-id/", tags=["Students"])
async def upload_college_id(
    roll_no: str,
    college_id_pic: UploadFile = File(..., description="Upload college ID card photo (REQUIRED)"),
    db: Database = Depends(get_db)
):
    """
    Upload college ID card picture for a student. This is MANDATORY.
    Uses BLIP-2 to verify if the image is a valid college ID.
    Uses PaddleOCR to extract college ID, student name, and roll number from the image and verify them.
    Accepts image files (jpg, jpeg, png, gif).
    """
    if not college_id_pic.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Get student details first
    student = crud.get_student_by_roll_no(roll_no, db)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    student_name = student.get("name")
    if not student_name:
        raise HTTPException(status_code=400, detail="Student name not found in database")
    
    # Check file extension
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']
    file_ext = os.path.splitext(college_id_pic.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Determine MIME type
    mime_type_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif'
    }
    mime_type = mime_type_map.get(file_ext, 'image/jpeg')
    
    # Read image bytes for verification
    image_bytes = await college_id_pic.read()
    
    # Verify with AI (checks if it's a college ID, extracts and verifies name and roll number)
    is_valid, ai_message, extracted_college_id = await verify_college_id_with_ai(
        image_bytes, mime_type, student_name, roll_no
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=400, 
            detail=ai_message
        )
    
    # Save the file
    filename = f"{roll_no}_college_id.png"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        buffer.write(image_bytes)
    
    # Update student record
    result = crud.update_college_id_pic(roll_no, file_path, db)
    if not result:
        # Clean up file if update fails
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="Failed to update student record")
    
    return {
        "message": "College ID card uploaded and verified successfully",
        "roll_no": roll_no,
        "extracted_college_id": extracted_college_id,
        "file_path": file_path,
        "verification": ai_message
    }


@app.get("/students/{roll_no}/college-id-status/", tags=["Students"])
def check_college_id_status(roll_no: str, db: Database = Depends(get_db)):
    """Check if a student has uploaded their college ID card."""
    student = crud.get_student_by_roll_no(roll_no, db)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    has_college_id = bool(student.get('college_id_pic'))
    
    return {
        "roll_no": roll_no,
        "has_uploaded_college_id": has_college_id,
        "college_id_pic_path": student.get('college_id_pic') if has_college_id else None,
        "status": "Completed" if has_college_id else "Pending - MANDATORY"
    }


# ==================== SKILLS & ACHIEVEMENTS ====================
@app.post("/students/{roll_no}/skills/", tags=["Skills & Achievements"])
async def add_skill(
    roll_no: str,
    skills: str = Form(..., description="Skill name (e.g., Python)"),
    description: Optional[str] = Form(None, description="Institution - Skill Name (optional)"),
    certificate: Optional[UploadFile] = File(None, description="Upload skill certificate photo (optional)"),
    db: Database = Depends(get_db)
):
    """Add a skill to a student's profile. Certificate is verified with AI if uploaded."""
    # Get student details
    student = crud.get_student_by_roll_no(roll_no, db)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    student_name = student.get("name")
    if not student_name:
        raise HTTPException(status_code=400, detail="Student name not found in database")
    
    certificate_path = None
    verification_message = "No certificate uploaded"
    confidence_scores = None
    
    # If certificate is uploaded, verify it with AI
    if certificate and hasattr(certificate, 'filename') and certificate.filename:
        # Check file extension
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.pdf']
        file_ext = os.path.splitext(certificate.filename)[1].lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Determine MIME type
        mime_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf'
        }
        mime_type = mime_type_map.get(file_ext, 'image/jpeg')
        
        # Read certificate bytes
        cert_bytes = await certificate.read()
        
        # Verify certificate with AI
        is_valid, ai_message, confidence_scores = await verify_certificate_with_ai(
            cert_bytes, mime_type, student_name, skills, description
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=400, 
                detail=f"{ai_message}. Confidence Score: {confidence_scores.get('overall_confidence', 0.0)}"
            )
        
        verification_message = ai_message
        
        # Save the certificate file
        # Clean skill name for filename (remove special characters, spaces to underscore)
        clean_skill_name = "".join(c if c.isalnum() else "_" for c in skills).lower()
        filename = f"{roll_no}_{clean_skill_name}.png"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as buffer:
            buffer.write(cert_bytes)
        certificate_path = file_path

    final_description = description if description and description.strip() else None
    result = crud.add_skills(roll_no, skills, db, certificate_path, final_description)
    
    if not result:
        raise HTTPException(status_code=404, detail="Student not found")
    
    return {
        "message": "Skill added successfully",
        "certificate_uploaded": certificate_path is not None,
        "verification": verification_message,
        "confidence_scores": confidence_scores
    }


@app.post("/students/{roll_no}/achievements/", tags=["Skills & Achievements"])
async def add_achievement(
    roll_no: str,
    achievements: str = Form(..., description="Achievement name"),
    description: Optional[str] = Form(None, description="Institution - Achievement (optional)"),
    certificate: Optional[UploadFile] = File(None, description="Upload achievement certificate photo (optional)"),
    db: Database = Depends(get_db)
):
    """Add an achievement to a student's profile. Certificate is verified with AI if uploaded."""
    # Get student details
    student = crud.get_student_by_roll_no(roll_no, db)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    student_name = student.get("name")
    if not student_name:
        raise HTTPException(status_code=400, detail="Student name not found in database")
    
    certificate_path = None
    verification_message = "No certificate uploaded"
    confidence_scores = None
    
    # If certificate is uploaded, verify it with AI
    if certificate and hasattr(certificate, 'filename') and certificate.filename:
        # Check file extension
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.pdf']
        file_ext = os.path.splitext(certificate.filename)[1].lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Determine MIME type
        mime_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf'
        }
        mime_type = mime_type_map.get(file_ext, 'image/jpeg')
        
        # Read certificate bytes
        cert_bytes = await certificate.read()
        
        # Verify certificate with AI
        is_valid, ai_message, confidence_scores = await verify_certificate_with_ai(
            cert_bytes, mime_type, student_name, achievements, description
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=400, 
                detail=f"{ai_message}. Confidence Score: {confidence_scores.get('overall_confidence', 0.0)}"
            )
        
        verification_message = ai_message
        
        # Save the certificate file
        # Clean achievement name for filename (remove special characters, spaces to underscore)
        clean_achievement_name = "".join(c if c.isalnum() else "_" for c in achievements).lower()
        filename = f"{roll_no}_{clean_achievement_name}.png"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as buffer:
            buffer.write(cert_bytes)
        certificate_path = file_path

    final_description = description if description and description.strip() else None
    result = crud.add_achievements(roll_no, achievements, db, certificate_path, final_description)
    
    if not result:
        raise HTTPException(status_code=404, detail="Student not found")
    
    return {
        "message": "Achievement added successfully",
        "certificate_uploaded": certificate_path is not None,
        "verification": verification_message,
        "confidence_scores": confidence_scores
    }


@app.post("/students/{roll_no}/projects/", tags=["Projects"])
def add_project(
    roll_no: str,
    project_name: str = Form(..., description="Project name"),
    github_link: str = Form(..., description="GitHub repository link"),
    db: Database = Depends(get_db)
):
    """Add a project to a student's profile with GitHub link. Link is required."""
    result = crud.add_projects(roll_no, project_name, github_link, db)
    
    if result is None:
        raise HTTPException(status_code=404, detail="Student not found")
    if isinstance(result, str):
        raise HTTPException(status_code=400, detail=result)
    
    return {"message": "Project added successfully", "project_name": project_name, "github_link": github_link}


@app.get("/students/{roll_no}/projects/", tags=["Projects"])
def get_student_projects(roll_no: str, db: Database = Depends(get_db)):
    """Get all projects for a student with GitHub links and verification status."""
    projects = crud.get_student_projects(roll_no, db)
    
    if projects is None:
        raise HTTPException(status_code=404, detail="Student not found")
    
    return {
        "roll_no": roll_no,
        "projects": projects,
        "total_projects": len(projects)
    }
    


# ==================== CERTIFICATE SERVING ====================
@app.get("/certificates/{filename}", tags=["Certificates"])
def get_certificate(filename: str):
    """Serve certificate images for viewing."""
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Certificate not found")


# ==================== ADMIN VERIFICATION ====================
@app.get("/admin/unverified-students", tags=["Admin"])
def get_unverified_students(college_name: Optional[str] = None, db: Database = Depends(get_db)):
    """Get all students with unverified skills or achievements. Optionally filter by college name."""
    unverified = crud.get_unverified_students(db, college_name)
    return {"count": len(unverified), "students": unverified, "college_filter": college_name}


@app.get("/admin/unverified-view", response_class=HTMLResponse, tags=["Admin"])
def view_unverified_students(college_name: Optional[str] = None, db: Database = Depends(get_db)):
    """HTML page for admin to view unverified skills/achievements with certificate images. Optionally filter by college name."""
    unverified = crud.get_unverified_students(db, college_name)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin - Verify Skills & Achievements</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            h1 {{ color: #333; }}
            .student-card {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .student-header {{ border-bottom: 2px solid #4CAF50; padding-bottom: 10px; margin-bottom: 15px; }}
            .item {{ background: #f9f9f9; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #2196F3; }}
            .achievement-item {{ border-left: 4px solid #FF9800; }}
            img {{ max-width: 300px; max-height: 300px; border: 2px solid #ddd; border-radius: 5px; margin: 10px 0; }}
            .verify-btn {{ background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin-top: 10px; }}
            .verify-btn:hover {{ background-color: #45a049; }}
            .no-cert {{ color: #999; font-style: italic; }}
            .description {{ color: #666; margin: 5px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Admin Verification Panel</h1>
            <p>Total students with unverified items: <strong>{len(unverified)}</strong></p>
    """
    
    for student in unverified:
        html_content += f"""
            <div class="student-card">
                <div class="student-header">
                    <h2>{student['name']}</h2>
                    <p><strong>Roll No:</strong> {student['roll_no']} | <strong>Email:</strong> {student['email']}</p>
                </div>
        """
        
        if student['unverified_skills']:
            html_content += "<h3>📚 Unverified Skills:</h3>"
            for skill_item in student['unverified_skills']:
                html_content += f"""
                    <div class="item">
                        <h4>Skill: {skill_item['name']}</h4>
                        <p class="description"><strong>Description:</strong> {skill_item.get('description', 'No description')}</p>
                """
                if skill_item.get('certificate'):
                    html_content += f'<p><strong>Certificate:</strong></p><img src="/{skill_item["certificate"]}" alt="Certificate">'
                else:
                    html_content += '<p class="no-cert">No certificate uploaded</p>'
                
                html_content += f"""
                        <form action="/admin/verify-skill/{student['roll_no']}" method="post">
                            <input type="hidden" name="skill_name" value="{skill_item['name']}">
                            <button class="verify-btn" type="submit">✅ Verify</button>
                        </form>
                    </div>
                """
        
        if student['unverified_achievements']:
            html_content += "<h3>🏆 Unverified Achievements:</h3>"
            for ach_item in student['unverified_achievements']:
                html_content += f"""
                    <div class="item achievement-item">
                        <h4>Achievement: {ach_item['name']}</h4>
                        <p class="description"><strong>Description:</strong> {ach_item.get('description', 'No description')}</p>
                """
                if ach_item.get('certificate'):
                    html_content += f'<p><strong>Certificate:</strong></p><img src="/{ach_item["certificate"]}" alt="Certificate">'
                else:
                    html_content += '<p class="no-cert">No certificate uploaded</p>'
                
                html_content += f"""
                        <form action="/admin/verify-achievement/{student['roll_no']}" method="post">
                            <input type="hidden" name="achievement_name" value="{ach_item['name']}">
                            <button class="verify-btn" type="submit">✅ Verify</button>
                        </form>
                    </div>
                """
        
        if student.get('unverified_projects'):
            html_content += "<h3>💻 Unverified Projects:</h3>"
            for proj_item in student['unverified_projects']:
                html_content += f"""
                    <div class="item achievement-item">
                        <h4>Project: {proj_item['name']}</h4>
                        <p class="description"><strong>GitHub Link:</strong> <a href="{proj_item.get('github_link', '#')}" target="_blank">{proj_item.get('github_link', 'No link provided')}</a></p>
                        <form action="/admin/verify-project/{student['roll_no']}" method="post">
                            <input type="hidden" name="project_name" value="{proj_item['name']}">
                            <button class="verify-btn" type="submit">✅ Verify</button>
                        </form>
                    </div>
                """
        
        html_content += "</div>"
    
    html_content += "</div></body></html>"
    return HTMLResponse(content=html_content)


@app.post("/admin/verify-skill/{roll_no}", tags=["Admin"])
def verify_skill(roll_no: str, skill_name: str, db: Database = Depends(get_db)):
    """Admin endpoint to verify a specific skill."""
    result = crud.verify_student_skill(roll_no, skill_name, db)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@app.post("/admin/verify-achievement/{roll_no}", tags=["Admin"])
def verify_achievement(roll_no: str, achievement_name: str, db: Database = Depends(get_db)):
    """Admin endpoint to verify a specific achievement."""
    result = crud.verify_student_achievement(roll_no, achievement_name, db)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@app.post("/admin/verify-project/{roll_no}", tags=["Admin"])
def verify_project(roll_no: str, project_name: str, db: Database = Depends(get_db)):
    """Admin endpoint to verify a specific project."""
    result = crud.verify_student_project(roll_no, project_name, db)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


# ==================== COMMENTS ====================
@app.post("/students/{roll_no}/comments/admin", tags=["Comments"])
def admin_add_comment(
    roll_no: str,
    comment: schemas.CommentCreate,
    db: Database = Depends(get_db)
):
    """Admin adds a comment on a student's profile (optional)."""
    result = crud.add_comment(
        roll_no=roll_no,
        author="admin",
        author_type="admin",
        text=comment.text,
        db=db
    )
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@app.post("/students/{roll_no}/comments/student", tags=["Comments"])
def student_add_comment(
    roll_no: str,
    comment: schemas.CommentCreate,
    db: Database = Depends(get_db)
):
    """Student adds a comment on their own profile (optional)."""
    # Verify the student exists
    student = crud.get_student_by_roll_no(roll_no, db)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    result = crud.add_comment(
        roll_no=roll_no,
        author=roll_no,
        author_type="student",
        text=comment.text,
        db=db
    )
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@app.get("/students/{roll_no}/comments", tags=["Comments"])
def get_student_comments(roll_no: str, db: Database = Depends(get_db)):
    """Get all comments for a student (both admin and student comments)."""
    result = crud.get_comments(roll_no, db)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@app.delete("/students/{roll_no}/comments/{timestamp}", tags=["Comments"])
def delete_student_comment(
    roll_no: str,
    timestamp: str,
    db: Database = Depends(get_db)
):
    """Delete a specific comment by timestamp (admin or student can delete their own comments)."""
    result = crud.delete_comment(roll_no, timestamp, db)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result



