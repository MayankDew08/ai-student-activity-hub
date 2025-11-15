from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from typing import Optional, List, Dict, Any
from bson import ObjectId
import schemas
from database import colleges_collection, students_collection
from auth import hash_password, verify_password


# ==================== HELPER FUNCTIONS ====================
def convert_objectid(doc: Dict) -> Dict:
    """Convert MongoDB ObjectId to string for JSON serialization"""
    if not doc:
        return doc
    
    # Create a copy to avoid modifying the original document
    doc_copy = dict(doc)
    if "_id" in doc_copy:
        doc_copy["id"] = str(doc_copy["_id"])
        del doc_copy["_id"]
    return doc_copy


# ==================== COLLEGE CRUD ====================
def create_college(college: schemas.CollegeCreate, db: Database):
    """Create a new college in the system."""
    try:
        college_doc = {
            "name": college.name,
            "address": college.address,
            "contact_email": college.contact_email,
            "contact_phone": college.contact_phone,
            "college_id": college.college_id,
            "admin_password": hash_password(college.admin_password)  # Hash password
        }
        
        result = colleges_collection.insert_one(college_doc)
        college_doc["_id"] = result.inserted_id
        return convert_objectid(college_doc)
        
    except DuplicateKeyError as e:
        # Parse which field caused the duplicate
        error_msg = str(e)
        if "name" in error_msg:
            raise ValueError(f"College name '{college.name}' already exists")
        elif "college_id" in error_msg:
            raise ValueError(f"College ID '{college.college_id}' already exists")
        elif "contact_email" in error_msg:
            raise ValueError(f"Contact email '{college.contact_email}' already exists")
        elif "contact_phone" in error_msg:
            raise ValueError(f"Contact phone '{college.contact_phone}' already exists")
        else:
            raise ValueError("Duplicate entry detected. Please check all fields.")


def get_colleges(db: Database):
    """Get all colleges."""
    colleges = list(colleges_collection.find())
    return [convert_objectid(college) for college in colleges]


def get_college_by_name(name: str, db: Database):
    """Get a college by name."""
    college = colleges_collection.find_one({"name": name})
    return convert_objectid(college) if college else None


def authenticate_college_admin(college_id: str, admin_password: str, db: Database):
    """Authenticate a college admin by college ID and password."""
    college = colleges_collection.find_one({"college_id": college_id})
    if not college:
        return None
    if not verify_password(admin_password, college.get("admin_password")):
        return None
    return convert_objectid(college)


# ==================== STUDENT CRUD ====================
def create_student(student: schemas.StudentCreate, db: Database):
    """Create a new student with basic information only."""
    try:
        student_doc = {
            "college_name": student.college_name,
            "name": student.name,
            "email": student.email,
            "phone": student.phone,
            "roll_no": student.roll_no,
            "password": hash_password(student.password),  # Hash password
            "branch": student.branch,
            "year": student.year,
            "age": student.age,
            "college_id_pic": None,
            "skills": [],  # List of skill objects
            "achievements": [],  # List of achievement objects
            "projects": []  # List of project objects
        }
        
        result = students_collection.insert_one(student_doc)
        student_doc["_id"] = result.inserted_id
        return convert_objectid(student_doc)
        
    except DuplicateKeyError as e:
        # Parse which field caused the duplicate
        if "email" in str(e):
            raise ValueError(f"Email '{student.email}' already exists")
        elif "phone" in str(e):
            raise ValueError(f"Phone number '{student.phone}' already exists")
        elif "roll_no" in str(e):
            raise ValueError(f"Roll number '{student.roll_no}' already exists")
        else:
            raise ValueError("Duplicate entry detected")


def get_all_students(db: Database, college_name: str):
    """Get all students from a specific college."""
    # Filter by college name (case-insensitive exact match)
    students = list(students_collection.find({"college_name": {"$regex": f"^{college_name}$", "$options": "i"}}))
    return [convert_objectid(s) for s in students]


def get_student_by_roll_no(roll_no: str, db: Database):
    """Get detailed student profile by roll number."""
    student = students_collection.find_one({"roll_no": roll_no})
    return convert_objectid(student) if student else None


def authenticate_student(roll_no: str, password: str, db: Database):
    """Authenticate a student by roll number and password."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return None
    if not verify_password(password, student.get("password")):
        return None
    return convert_objectid(student)


def update_student(roll_no: str, student: schemas.StudentUpdate, db: Database):
    """Update student information."""
    update_data = student.dict(exclude_unset=True)
    
    if not update_data:
        return get_student_by_roll_no(roll_no, db)
    
    result = students_collection.update_one(
        {"roll_no": roll_no},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        return None
    
    return get_student_by_roll_no(roll_no, db)


def delete_student(roll_no: str, db: Database):
    """Delete a student."""
    result = students_collection.delete_one({"roll_no": roll_no})
    return result.deleted_count > 0


def search_students_by_name(name: str, db: Database):
    """Search students by name (case-insensitive partial match)."""
    students = list(students_collection.find({
        "name": {"$regex": name, "$options": "i"}
    }))
    return [convert_objectid(s) for s in students]


def update_college_id_pic(roll_no: str, file_path: str, db: Database):
    """Update the college ID picture path for a student."""
    result = students_collection.update_one(
        {"roll_no": roll_no},
        {"$set": {"college_id_pic": file_path}}
    )
    return result.matched_count > 0


# ==================== SKILLS & ACHIEVEMENTS (NEW STRUCTURE) ====================
def add_skills(roll_no: str, skill_name: str, db: Database, certificate: Optional[str] = None, description: Optional[str] = None):
    """Add a skill to a student with the new object structure."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return None
    
    # Create skill object
    skill_obj = {
        "name": skill_name,
        "verified": False,
        "certificate": certificate,
        "description": description
    }
    
    # Add skill object to array
    students_collection.update_one(
        {"roll_no": roll_no},
        {"$push": {"skills": skill_obj}}
    )
    
    return get_student_by_roll_no(roll_no, db)


def add_achievements(roll_no: str, achievement_name: str, db: Database, certificate: Optional[str] = None, description: Optional[str] = None):
    """Add an achievement to a student with the new object structure."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return None
    
    # Create achievement object
    achievement_obj = {
        "name": achievement_name,
        "verified": False,
        "certificate": certificate,
        "description": description
    }
    
    # Add achievement object to array
    students_collection.update_one(
        {"roll_no": roll_no},
        {"$push": {"achievements": achievement_obj}}
    )
    
    return get_student_by_roll_no(roll_no, db)


def add_projects(roll_no: str, project_name: str, github_link: str, db: Database):
    """Add a project to a student with the new object structure."""
    # Validate GitHub/GitLab link
    if not github_link or not ("github.com" in github_link.lower() or "gitlab.com" in github_link.lower()):
        return "Invalid repository link. Must be from GitHub or GitLab"
    
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return None
    
    # Create project object
    project_obj = {
        "name": project_name,
        "verified": False,
        "github_link": github_link,
        "description": None
    }
    
    # Add project object to array
    students_collection.update_one(
        {"roll_no": roll_no},
        {"$push": {"projects": project_obj}}
    )
    
    return get_student_by_roll_no(roll_no, db)


def get_student_projects(roll_no: str, db: Database):
    """Get all projects for a student."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return None
    
    return student.get("projects", [])


# ==================== ADMIN VERIFICATION (NEW STRUCTURE) ====================
def get_unverified_students(db: Database, college_name: Optional[str] = None):
    """Get all students with unverified skills, achievements, or projects. Optionally filter by college name."""
    # Build query filter
    query_filter = {
        "$or": [
            {"skills.verified": False},
            {"achievements.verified": False},
            {"projects.verified": False}
        ]
    }
    
    # Add college name filter if provided (combine with $and)
    if college_name:
        query_filter = {
            "$and": [
                {
                    "$or": [
                        {"skills.verified": False},
                        {"achievements.verified": False},
                        {"projects.verified": False}
                    ]
                },
                {"college_name": {"$regex": f"^{college_name}$", "$options": "i"}}
            ]
        }
    
    # Find students with at least one unverified item
    students = list(students_collection.find(query_filter))
    
    unverified_list = []
    
    for student in students:
        skills = student.get("skills", [])
        achievements = student.get("achievements", [])
        projects = student.get("projects", [])
        
        # Filter unverified items (handle both dict and string formats)
        unverified_skills = [s for s in skills if isinstance(s, dict) and not s.get("verified", False)]
        unverified_achievements = [a for a in achievements if isinstance(a, dict) and not a.get("verified", False)]
        unverified_projects = [p for p in projects if isinstance(p, dict) and not p.get("verified", False)]
        
        # Only include students with unverified items
        if unverified_skills or unverified_achievements or unverified_projects:
            unverified_list.append({
                "id": str(student["_id"]),
                "name": student.get("name"),
                "roll_no": student.get("roll_no"),
                "email": student.get("email"),
                "college_name": student.get("college_name"),
                "unverified_skills": unverified_skills,
                "unverified_achievements": unverified_achievements,
                "unverified_projects": unverified_projects
            })
    
    return unverified_list


def verify_student_skill(roll_no: str, skill_name: str, db: Database):
    """Verify a specific skill for a student."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return {"success": False, "message": "Student not found"}
    
    # Update the verified status for the matching skill
    result = students_collection.update_one(
        {"roll_no": roll_no, "skills.name": skill_name},
        {"$set": {"skills.$.verified": True}}
    )
    
    if result.modified_count > 0:
        return {"success": True, "message": f"Skill '{skill_name}' verified successfully"}
    else:
        return {"success": False, "message": f"Skill '{skill_name}' not found"}


def verify_student_achievement(roll_no: str, achievement_name: str, db: Database):
    """Verify a specific achievement for a student."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return {"success": False, "message": "Student not found"}
    
    # Update the verified status for the matching achievement
    result = students_collection.update_one(
        {"roll_no": roll_no, "achievements.name": achievement_name},
        {"$set": {"achievements.$.verified": True}}
    )
    
    if result.modified_count > 0:
        return {"success": True, "message": f"Achievement '{achievement_name}' verified successfully"}
    else:
        return {"success": False, "message": f"Achievement '{achievement_name}' not found"}


def verify_student_project(roll_no: str, project_name: str, db: Database):
    """Verify a specific project for a student."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return {"success": False, "message": "Student not found"}
    
    # Update the verified status for the matching project
    result = students_collection.update_one(
        {"roll_no": roll_no, "projects.name": project_name},
        {"$set": {"projects.$.verified": True}}
    )
    
    if result.modified_count > 0:
        return {"success": True, "message": f"Project '{project_name}' verified successfully"}
    else:
        return {"success": False, "message": f"Project '{project_name}' not found"}


# ==================== COMMENTS CRUD ====================
def add_comment(roll_no: str, author: str, author_type: str, text: str, db: Database):
    """Add a comment to a student's profile. Author can be admin or student."""
    from datetime import datetime
    
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return {"success": False, "message": "Student not found"}
    
    # Create comment object
    comment_obj = {
        "author": author,
        "author_type": author_type,  # 'admin' or 'student'
        "text": text,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Add comment to student's comments array
    students_collection.update_one(
        {"roll_no": roll_no},
        {"$push": {"comments": comment_obj}}
    )
    
    return {"success": True, "message": "Comment added successfully", "comment": comment_obj}


def get_comments(roll_no: str, db: Database):
    """Get all comments for a student."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return {"success": False, "message": "Student not found"}
    
    comments = student.get("comments", [])
    return {"success": True, "comments": comments}


def delete_comment(roll_no: str, timestamp: str, db: Database):
    """Delete a specific comment by timestamp."""
    result = students_collection.update_one(
        {"roll_no": roll_no},
        {"$pull": {"comments": {"timestamp": timestamp}}}
    )
    
    if result.modified_count > 0:
        return {"success": True, "message": "Comment deleted successfully"}
    else:
        return {"success": False, "message": "Comment not found"}

