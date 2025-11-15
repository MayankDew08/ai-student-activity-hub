from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List


# ==================== AUTHENTICATION SCHEMAS ====================
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    roll_no: Optional[str] = None
    role: Optional[str] = None


# ==================== COMMENT SCHEMAS ====================
class CommentCreate(BaseModel):
    text: str = Field(..., example="Great progress on this project!", min_length=1, max_length=1000)


class CommentOut(BaseModel):
    author: str = Field(..., example="admin or CS101")
    author_type: str = Field(..., example="admin or student")
    text: str
    timestamp: str


# ==================== COLLEGE SCHEMAS ====================
class CollegeBase(BaseModel):
    name: str = Field(..., example="IIITNR", min_length=3)
    address: str = Field(..., example="123 Main St, City, State")
    contact_email: EmailStr = Field(..., example="contact@college.edu")
    contact_phone: str = Field(..., example="1234567890", min_length=10, max_length=15)
    college_id: str = Field(..., example="COLL001", min_length=3)


class CollegeCreate(CollegeBase):
    admin_password: str = Field(..., example="securePassword123", min_length=6)


class CollegeOut(CollegeBase):
    id: int

    class Config:
        from_attributes = True


class CollegeLogin(BaseModel):
    college_id: str = Field(..., example="COLL001", min_length=3)
    admin_password: str = Field(..., example="securePassword123", min_length=6)


# ==================== STUDENT SCHEMAS ====================
class StudentCreate(BaseModel):
    college_name: str = Field(..., example="IIITNR", min_length=3)
    name: str = Field(..., example="John Doe", min_length=3)
    email: EmailStr = Field(..., example="john.doe@example.com")
    phone: str = Field(..., example="1234567890", min_length=10, max_length=15)
    roll_no: str = Field(..., example="CS101", min_length=2, max_length=12)
    password: str = Field(..., example="studentPassword123", min_length=6)
    branch: str = Field(..., example="Computer Science", min_length=3)
    year: int = Field(..., example=2, ge=1, le=4)
    age: int = Field(..., example=20, ge=15, le=40)


class StudentLogin(BaseModel):
    roll_no: str = Field(..., example="CS101", min_length=2, max_length=12)
    password: str = Field(..., example="studentPassword123", min_length=6)


class StudentUpdate(BaseModel):
    college_name: Optional[str] = Field(None, example="IIITNR", min_length=3)
    name: Optional[str] = Field(None, example="John Doe", min_length=3)
    email: Optional[EmailStr] = Field(None, example="john.doe@example.com")
    phone: Optional[str] = Field(None, example="1234567890", min_length=10, max_length=15)
    roll_no: Optional[str] = Field(None, example="CS101", min_length=2, max_length=12)
    branch: Optional[str] = Field(None, example="Computer Science", min_length=3)
    year: Optional[int] = Field(None, example=2, ge=1, le=4)
    age: Optional[int] = Field(None, example=20, ge=15, le=40)
    college_id_pic: Optional[str] = Field(None, example="college_id_pic.jpg")


class StudentOut(BaseModel):
    id: int
    college_name: str
    name: str
    email: EmailStr
    phone: str
    roll_no: str
    branch: str
    year: int
    age: int
    college_id_pic: Optional[str]
    skills: List[str] = []
    achievements: List[str] = []
    skill_certificates: List[str] = []
    achievement_certificates: List[str] = []
    skill_descriptions: List[str] = []
    achievement_descriptions: List[str] = []
    skills_verified: List[str] = []
    achievements_verified: List[str] = []
    projects: List[str] = []
    project_links: List[str] = []
    projects_verified: List[str] = []

    class Config:
        from_attributes = True
