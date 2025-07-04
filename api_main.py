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
    
    # Added table creation for daily check-ins
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
    """
    try:
        await database.execute(query, values={"user_id": data.user_id, "points": data.points})
        return {"message": f"User {data.user_id} points set to {data.points}."}
    except Exception as e:
        print(f"Error setting points: {e}")
        raise HTTPException(status_code=500, detail="Error setting points in database.")

@app.post("/mentor-assignments")
async def manage_mentor_assignment(data: MentorAssignment):
    """
    Handles both assigning and un-assigning a mentor.
    If the pair exists, it's deleted (unassigned).
    If the pair does not exist, it's created (assigned).
    """
    try:
        select_query = "SELECT mentor_id FROM mentor_assignments WHERE mentor_id = :mentor_id AND mentee_id = :mentee_id"
        values = {"mentor_id": data.mentor_id, "mentee_id": data.mentee_id}
        existing_assignment = await database.fetch_one(select_query, values)

        if existing_assignment:
            delete_query = "DELETE FROM mentor_assignments WHERE mentor_id = :mentor_id AND mentee_id = :mentee_id"
            await database.execute(delete_query, values)
            print(f"✅ Unassigned mentor {data.mentor_id} from mentee {data.mentee_id}")
            return {"message": "Mentor unassigned successfully"}
        else:
            insert_query = "INSERT INTO mentor_assignments (mentor_id, mentee_id) VALUES (:mentor_id, :mentee_id)"
            await database.execute(insert_query, values)
            print(f"✅ Assigned mentor {data.mentor_id} to mentee {data.mentee_id}")
            return {"message": "Mentor assigned successfully"}
            
    except Exception as e:
        print(f"🔥 ERROR managing mentor assignment: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail="An unexpected database error occurred.")

# --- NEW ENDPOINT FOR THE REMINDER LOOP ---
@app.get("/mentor-assignments")
async def get_all_assignments():
    """Fetches all mentor-mentee assignments from the database."""
    try:
        query = "SELECT mentor_id, mentee_id FROM mentor_assignments"
        assignments = await database.fetch_all(query)
        return assignments
    except Exception as e:
        print(f"🔥 ERROR fetching all assignments: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve assignments from database.")


@app.post("/log-checkin")
async def log_checkin(data: CheckIn):
    if data.checkin_type.lower() not in ['good', 'bad']:
        raise HTTPException(status_code=400, detail="Invalid checkin_type. Must be 'good' or 'bad'.")

    query = """
    INSERT INTO daily_checkins (user_id, checkin_type)
    VALUES (:user_id, :checkin_type)
    """
    try:
        await database.execute(query, values={"user_id": data.user_id, "checkin_type": data.checkin_type.lower()})
        return {"message": f"Successfully logged '{data.checkin_type}' check-in for user {data.user_id}."}
    except Exception as e:
        print(f"🔥 ERROR logging checkin: {e}")
        raise HTTPException(status_code=500, detail="Failed to log check-in.")


@app.get("/")
async def root():
    return {"message": "Mentor API is running"}


# --- Server Startup Logic ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("api_main:app", host="0.0.0.0", port=port, reload=False)
