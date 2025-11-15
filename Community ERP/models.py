from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from bson import ObjectId

# Custom ObjectId field for MongoDB
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


# Comment structure
class Comment(BaseModel):
    author: str  # 'admin' or student roll_no
    author_type: str  # 'admin' or 'student'
    text: str
    timestamp: str  # ISO format datetime string

# Skill/Achievement/Project item structure
class SkillItem(BaseModel):
    name: str
    verified: bool = False
    certificate: Optional[str] = None
    description: Optional[str] = None

class AchievementItem(BaseModel):
    name: str
    verified: bool = False
    certificate: Optional[str] = None
    description: Optional[str] = None

class ProjectItem(BaseModel):
    name: str
    verified: bool = False
    github_link: str
    description: Optional[str] = None


class Student(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    college_name: str
    name: str
    age: int
    email: str
    phone: str
    roll_no: str
    password: str  # Password for student login
    branch: str
    year: int
    college_id_pic: Optional[str] = None  # Stores file path to uploaded college ID photo (MANDATORY - must upload separately)
    skills: Optional[List[Dict[str, Any]]] = []  # List of skill objects
    achievements: Optional[List[Dict[str, Any]]] = []  # List of achievement objects
    projects: Optional[List[Dict[str, Any]]] = []  # List of project objects
    comments: Optional[List[Dict[str, Any]]] = []  # List of comments (admin ↔ student)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class College(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str
    address: str
    contact_email: str
    contact_phone: str
    college_id: str
    admin_password: str  # Password for college admin login

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}