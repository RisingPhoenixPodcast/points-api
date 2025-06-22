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
    """ # Note: Changed to use PostgreSQL's ON CONFLICT syntax
    try:
        await database.execute(query, values={"user_id": data.user_id, "points": data.points})
        new_total_data = await get_points(data.user_id)
        return {"user_id": data.user_id, "new_total": new_total_data.get("points")}
    except Exception as e:
        print(f"Error adding points: {e}")
        raise HTTPException(status_code=500, detail="Error updating points in database.")


@app.get("/get_points/{user_id}")
async def get_points(user_id: int):
    query = "SELECT points FROM user_points WHERE user_id = :user_id"
    result = await database.fetch_one(query, values={"user_id": user_id})
    if result:
        return {"user_id": user_id, "points": result["points"]}
    else:
        return {"user_id": user_id, "points": 0}

@app.post("/set_points")
async def set_points(data: PointSet):
    query = """
    INSERT INTO user_points (user_id, points)
    VALUES (:user_id, :points)
    ON CONFLICT (user_id) DO UPDATE SET points = :points;
    """ # Note: Changed to use PostgreSQL's ON CONFLICT syntax
    try:
        await database.execute(query, values={"user_id": data.user_id, "points": data.points})
        return {"message": f"User {data.user_id} points set to {data.points}."}
    except Exception as e:
        print(f"Error setting points: {e}")
        raise HTTPException(status_code=500, detail="Error setting points in database.")


@app.post("/mentor-assignments")
async def assign_mentor(data: MentorAssignment):
    query = """
    INSERT INTO mentor_assignments (mentor_id, mentee_id)
    VALUES (:mentor_id, :mentee_id)
    """
    try:
        await database.execute(query, values={"mentor_id": data.mentor_id, "mentee_id": data.mentee_id})
        return {"message": "Mentor assigned successfully"}
    except Exception as e:
        # Check for PostgreSQL's unique violation error
        if 'unique constraint' in str(e).lower():
            raise HTTPException(status_code=400, detail="This mentor/mentee pairing already exists.")
        print(f"🔥 ERROR assigning mentor: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred in the database.")

@app.get("/")
async def root():
    return {"message": "Mentor API is running"}


# --- Server Startup Logic ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("api_main:app", host="0.0.0.0", port=port, reload=False)
