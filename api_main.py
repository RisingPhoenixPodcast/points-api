# --- IMPORTS ---
import uvicorn
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from databases import Database
import asyncio

# --- Configuration ---
# Uses the DATABASE_URL environment variable from Render's settings
DATABASE_URL = os.environ.get("DATABASE_URL")

database = Database(DATABASE_URL)
app = FastAPI()

# --- Data Models ---
class PointUpdate(BaseModel):
    user_id: int
    points: int

class PointSet(BaseModel):
    user_id: int
    points: int

class MentorAssignment(BaseModel):
    mentor_id: int
    mentee_id: int

# NEW: Added a model for check-in data
class CheckIn(BaseModel):
    user_id: int
    checkin_type: str


# --- API Events ---
@app.on_event("startup")
async def startup_event():
    try:
        await database.connect()
        print("✅ Database connection established.")
    except Exception as e:
        print(f"🔥 FATAL: Could not connect to the database. Error: {e}")
        return

    # Create user_points table with PostgreSQL-compatible syntax
    await database.execute("""
    CREATE TABLE IF NOT EXISTS user_points (
        user_id BIGINT PRIMARY KEY,
        points INT DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("✅ 'user_points' table is ready.")

    # Create mentor_assignments table
    await database.execute("""
    CREATE TABLE IF NOT EXISTS mentor_assignments (
        mentor_id BIGINT NOT NULL,
        mentee_id BIGINT NOT NULL,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (mentor_id, mentee_id)
    )
    """)
    print("✅ 'mentor_assignments' table is ready.")
    
    # NEW: Added table creation for daily check-ins
    await database.execute("""
    CREATE TABLE IF NOT EXISTS daily_checkins (
        checkin_id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        checkin_type VARCHAR(10) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("✅ 'daily_checkins' table is ready.")


@app.on_event("shutdown")
async def shutdown_event():
    await database.disconnect()
    print("Database connection closed.")


# --- API Endpoints ---
@app.post("/add_points")
async def add_points(data: PointUpdate):
    query = """
    INSERT INTO user_points (user_id, points)
    VALUES (:user_id, :points)
    ON CONFLICT (user_id) DO UPDATE SET points = user_points.points + :points;
    """
    try:
        await database.execute(query, values={"user_id": data.user_id, "points": data.points})
        new_total_data = await get_points(data.user_id)
        return {"user_id": data.user_id}
