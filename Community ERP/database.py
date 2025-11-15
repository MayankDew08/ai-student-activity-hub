from pymongo import MongoClient
from pymongo.database import Database

# MongoDB connection URL (update with your MongoDB URI if using Atlas)
MONGODB_URL = "mongodb://localhost:27017/"
DATABASE_NAME = "erp"  # Changed from "community_erp" to match your MongoDB Compass database

# Create MongoDB client
client = MongoClient(MONGODB_URL)
database: Database = client[DATABASE_NAME]

# Collections
colleges_collection = database["colleges"]
students_collection = database["students"]

# Create indexes for unique fields
def create_indexes():
    """Create unique indexes for fields that must be unique"""
    # College indexes
    colleges_collection.create_index("name", unique=True)
    colleges_collection.create_index("college_id", unique=True)
    colleges_collection.create_index("contact_email", unique=True)
    colleges_collection.create_index("contact_phone", unique=True)
    
    # Student indexes
    students_collection.create_index("email", unique=True)
    students_collection.create_index("phone", unique=True)
    students_collection.create_index("roll_no", unique=True)

# Initialize indexes
create_indexes()

def get_db():
    """Dependency for getting database instance"""
    return database

