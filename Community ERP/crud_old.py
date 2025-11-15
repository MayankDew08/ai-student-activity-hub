from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from typing import Optional, List, Dict, Any
from bson import ObjectId
import schemas
from database import colleges_collection, students_collection


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


def _convert_to_dict(student: Dict):
    """Convert MongoDB document to dictionary with proper conversions and verification status."""
    if not student:
        return None
    
    # Create a copy with converted ObjectId
    student_copy = convert_objectid(student)
    
    skills = student_copy.get("skills", [])
    skills_verified = student_copy.get("skills_verified", [])
    achievements = student_copy.get("achievements", [])
    achievements_verified = student_copy.get("achievements_verified", [])
    projects = student_copy.get("projects", [])
    projects_verified = student_copy.get("projects_verified", [])
    project_links = student_copy.get("project_links", [])
    
    # Create detailed lists with verification status
    skills_with_status = [
        {"name": skill, "verified": skills_verified[i] if i < len(skills_verified) else False}
        for i, skill in enumerate(skills)
    ]
    
    achievements_with_status = [
        {"name": achievement, "verified": achievements_verified[i] if i < len(achievements_verified) else False}
        for i, achievement in enumerate(achievements)
    ]
    
    projects_with_status = [
        {
            "name": project,
            "github_link": project_links[i] if i < len(project_links) else None,
            "verified": projects_verified[i] if i < len(projects_verified) else False
        }
        for i, project in enumerate(projects)
    ]
    
    return {
        "id": student_copy.get("id"),
        "college_name": student_copy.get("college_name"),
        "name": student_copy.get("name"),
        "email": student_copy.get("email"),
        "phone": student_copy.get("phone"),
        "roll_no": student_copy.get("roll_no"),
        "branch": student_copy.get("branch"),
        "year": student_copy.get("year"),
        "age": student_copy.get("age"),
        "college_id_pic": student_copy.get("college_id_pic"),
        "skills": skills_with_status,
        "achievements": achievements_with_status,
        "projects": projects_with_status,
        "skill_certificates": student_copy.get("skill_certificates", []),
        "achievement_certificates": student_copy.get("achievement_certificates", []),
        "skill_descriptions": student_copy.get("skill_descriptions", []),
        "achievement_descriptions": student_copy.get("achievement_descriptions", [])
    }


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
            "admin_password": college.admin_password
        }
        
        result = colleges_collection.insert_one(college_doc)
        college_doc["_id"] = result.inserted_id
        return convert_objectid(college_doc)
        
    except DuplicateKeyError as e:
        # Parse which field caused the duplicate
        if "college_id" in str(e):
            raise ValueError(f"College ID '{college.college_id}' already exists")
        elif "contact_email" in str(e):
            raise ValueError(f"Email '{college.contact_email}' already exists")
        elif "contact_phone" in str(e):
            raise ValueError(f"Phone number '{college.contact_phone}' already exists")
        else:
            raise ValueError("Duplicate entry detected")


def get_colleges(db: Database):
    """Get all registered colleges."""
    colleges = list(colleges_collection.find())
    return [convert_objectid(c) for c in colleges]


def get_college_by_name(college_name: str, db: Database):
    """Check if a college exists by name."""
    college = colleges_collection.find_one({"name": college_name})
    return convert_objectid(college) if college else None


# ==================== AUTHENTICATION ====================
def authenticate_student(roll_no: str, password: str, db: Database):
    """Authenticate a student by roll number and password."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return None
    if student.get("password") != password:
        return None
    return convert_objectid(student)


def authenticate_college_admin(college_id: str, admin_password: str, db: Database):
    """Authenticate a college admin by college ID and password."""
    college = colleges_collection.find_one({"college_id": college_id})
    if not college:
        return None
    if college.get("admin_password") != admin_password:
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
            "password": student.password,
            "branch": student.branch,
            "year": student.year,
            "age": student.age,
            "college_id_pic": None,
            "skills": [],
            "achievements": [],
            "skill_certificates": [],
            "achievement_certificates": [],
            "skill_descriptions": [],
            "achievement_descriptions": [],
            "skills_verified": [],
            "achievements_verified": [],
            "projects": [],
            "project_links": [],
            "projects_verified": []
        }
        
        result = students_collection.insert_one(student_doc)
        student_doc["_id"] = result.inserted_id
        return _convert_to_dict(student_doc)
        
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


def get_all_students(db: Database):
    """Get all students with basic information."""
    students = list(students_collection.find())
    return [
        {
            "id": str(s["_id"]),
            "name": s.get("name"),
            "college_name": s.get("college_name"),
            "roll_no": s.get("roll_no"),
            "branch": s.get("branch"),
            "year": s.get("year"),
            "skills": s.get("skills", []),
            "achievements": s.get("achievements", [])
        }
        for s in students
    ]


def get_student_by_roll_no(roll_no: str, db: Database):
    """Get detailed student profile by roll number."""
    student = students_collection.find_one({"roll_no": roll_no})
    return _convert_to_dict(student) if student else None


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
    """Search students by name (case-insensitive)."""
    students = list(students_collection.find({"name": {"$regex": name, "$options": "i"}}))
    return [_convert_to_dict(s) for s in students] if students else []


def update_college_id_pic(roll_no: str, file_path: str, db: Database):
    """Update the college ID picture path for a student."""
    result = students_collection.update_one(
        {"roll_no": roll_no},
        {"$set": {"college_id_pic": file_path}}
    )
    
    if result.matched_count == 0:
        return None
    
    return get_student_by_roll_no(roll_no, db)


# ==================== SKILLS & ACHIEVEMENTS ====================
def add_skills(roll_no: str, skills: str, db: Database, certificate: Optional[str] = None, description: Optional[str] = None):
    """Add skills to a student with optional certificate and description."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return None
    
    # Add skill
    students_collection.update_one(
        {"roll_no": roll_no},
        {
            "$push": {
                "skills": skills,
                "skill_descriptions": description if description else "",
                "skill_certificates": certificate if certificate else "",
                "skills_verified": False
            }
        }
    )
    
    return get_student_by_roll_no(roll_no, db)


def add_achievements(roll_no: str, achievements: str, db: Database, certificate: Optional[str] = None, description: Optional[str] = None):
    """Add achievements to a student with optional certificate and description."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return None
    
    # Add achievement
    students_collection.update_one(
        {"roll_no": roll_no},
        {
            "$push": {
                "achievements": achievements,
                "achievement_descriptions": description if description else "",
                "achievement_certificates": certificate if certificate else "",
                "achievements_verified": False
            }
        }
    )
    
    return get_student_by_roll_no(roll_no, db)


def add_projects(roll_no: str, project_name: str, github_link: str, db: Database):
    """Add a project to a student with GitHub link."""
    # Validate GitHub link
    if not github_link or not ("github.com" in github_link.lower() or "gitlab.com" in github_link.lower()):
        return "Invalid repository link. Must be from GitHub or GitLab"
    
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return None
    
    # Add project
    students_collection.update_one(
        {"roll_no": roll_no},
        {
            "$push": {
                "projects": project_name,
                "project_links": github_link,
                "projects_verified": False
            }
        }
    )
    
    return get_student_by_roll_no(roll_no, db)


def get_student_projects(roll_no: str, db: Database):
    """Get all projects for a student with GitHub links."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return None
    
    projects = student.get("projects", [])
    project_links = student.get("project_links", [])
    projects_verified = student.get("projects_verified", [])
    
    projects_list = [
        {
            "name": projects[i],
            "github_link": project_links[i] if i < len(project_links) else None,
            "has_link": i < len(project_links) and bool(project_links[i]),
            "verified": projects_verified[i] if i < len(projects_verified) else False
        }
        for i in range(len(projects))
    ]
    
    return projects_list


# ==================== ADMIN VERIFICATION ====================
def get_unverified_students(db: Database):
    """Get all students with unverified skills, achievements, or projects."""
    # Find students with at least one False in verification arrays
    students = list(students_collection.find({
        "$or": [
            {"skills_verified": False},
            {"achievements_verified": False},
            {"projects_verified": False}
        ]
    }))
    
    unverified_list = []
    
    for student in students:
        skills = student.get("skills", [])
        skills_verified = student.get("skills_verified", [])
        skill_certs = student.get("skill_certificates", [])
        skill_descs = student.get("skill_descriptions", [])
        
        achievements = student.get("achievements", [])
        achievements_verified = student.get("achievements_verified", [])
        achievement_certs = student.get("achievement_certificates", [])
        achievement_descs = student.get("achievement_descriptions", [])
        
        projects = student.get("projects", [])
        projects_verified = student.get("projects_verified", [])
        project_links = student.get("project_links", [])
        
        # Get unverified skills
        unverified_skills = [
            {
                "name": skills[i],
                "description": skill_descs[i] if i < len(skill_descs) else "",
                "certificate": skill_certs[i] if i < len(skill_certs) else ""
            }
            for i in range(len(skills))
            if i >= len(skills_verified) or not skills_verified[i]
        ]
        
        # Get unverified achievements
        unverified_achievements = [
            {
                "name": achievements[i],
                "description": achievement_descs[i] if i < len(achievement_descs) else "",
                "certificate": achievement_certs[i] if i < len(achievement_certs) else ""
            }
            for i in range(len(achievements))
            if i >= len(achievements_verified) or not achievements_verified[i]
        ]
        
        # Get unverified projects
        unverified_projects = [
            {
                "name": projects[i],
                "github_link": project_links[i] if i < len(project_links) else ""
            }
            for i in range(len(projects))
            if i >= len(projects_verified) or not projects_verified[i]
        ]
        
        if unverified_skills or unverified_achievements or unverified_projects:
            unverified_list.append({
                "roll_no": student.get("roll_no"),
                "name": student.get("name"),
                "email": student.get("email"),
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
    
    skills = student.get("skills", [])
    skills_verified = student.get("skills_verified", [])
    
    if skill_name not in skills:
        return {"success": False, "message": f"Skill '{skill_name}' not found"}
    
    skill_index = skills.index(skill_name)
    
    # Ensure skills_verified array is same length as skills
    while len(skills_verified) <= skill_index:
        skills_verified.append(False)
    
    skills_verified[skill_index] = True
    
    students_collection.update_one(
        {"roll_no": roll_no},
        {"$set": {"skills_verified": skills_verified}}
    )
    
    return {"success": True, "message": "Skill verified successfully"}


def verify_student_achievement(roll_no: str, achievement_name: str, db: Database):
    """Verify a specific achievement for a student."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return {"success": False, "message": "Student not found"}
    
    achievements = student.get("achievements", [])
    achievements_verified = student.get("achievements_verified", [])
    
    if achievement_name not in achievements:
        return {"success": False, "message": f"Achievement '{achievement_name}' not found"}
    
    achievement_index = achievements.index(achievement_name)
    
    # Ensure achievements_verified array is same length as achievements
    while len(achievements_verified) <= achievement_index:
        achievements_verified.append(False)
    
    achievements_verified[achievement_index] = True
    
    students_collection.update_one(
        {"roll_no": roll_no},
        {"$set": {"achievements_verified": achievements_verified}}
    )
    
    return {"success": True, "message": "Achievement verified successfully"}


def verify_student_project(roll_no: str, project_name: str, db: Database):
    """Verify a specific project for a student."""
    student = students_collection.find_one({"roll_no": roll_no})
    if not student:
        return {"success": False, "message": "Student not found"}
    
    projects = student.get("projects", [])
    projects_verified = student.get("projects_verified", [])
    
    if project_name not in projects:
        return {"success": False, "message": f"Project '{project_name}' not found"}
    
    project_index = projects.index(project_name)
    
    # Ensure projects_verified array is same length as projects
    while len(projects_verified) <= project_index:
        projects_verified.append(False)
    
    projects_verified[project_index] = True
    
    students_collection.update_one(
        {"roll_no": roll_no},
        {"$set": {"projects_verified": projects_verified}}
    )
    
    return {"success": True, "message": "Project verified successfully"}
