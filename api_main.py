from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from databases import Database
import asyncio

# --- Configuration ---
DATABASE_URL = "mysql://root:UdELAxesZYuFCtrPNMlEQWAuLhFKajbo@mysql.railway.internal:3306/railway"

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


# --- Database Setup ---
async def setup_database():
    """Creates the new, efficient user_points table."""
    print("Connecting to the database...")
    await database.connect()
    print("Database connected. Setting up table...")
    await database.execute("""
    CREATE TABLE IF NOT EXISTS user_points (
        user_id BIGINT PRIMARY KEY,
        points INT DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )
    """)
    print("✅ 'user_points' table is ready.")

    await database.execute("""
    CREATE TABLE IF NOT EXISTS mentor_assignments (
        mentor_id BIGINT NOT NULL,
        mentee_id BIGINT NOT NULL,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (mentor_id, mentee_id)
    )
    """)
    print("✅ 'mentor_assignments' table is ready.")


# --- API Events ---
@app.on_event("startup")
async def startup_event():
    """This runs when the API server starts."""
    await setup_database()

@app.on_event("shutdown")
async def shutdown_event():
    """This runs when the API server stops."""
    await database.disconnect()
    print("Database connection closed.")


# --- API Endpoints (The Accountant's actions) ---
@app.post("/add_points")
async def add_points(data: PointUpdate):
    """
    Atomically adds points to a user's balance.
    This is the core function that fixes the race condition.
    """
    # This single SQL command does everything: It finds the user, adds the points,
    # and creates them if they don't exist. It is "atomic", meaning it cannot be interrupted.
    query = """
    INSERT INTO user_points (user_id, points)
    VALUES (:user_id, :points)
    ON DUPLICATE KEY UPDATE points = points + VALUES(points);
    """
    try:
        await database.execute(query, values={"user_id": data.user_id, "points": data.points})
        # Get the new total to send back
        new_total_data = await get_points(data.user_id)
        return {"user_id": data.user_id, "new_total": new_total_data.get("points")}
    except Exception as e:
        print(f"Error adding points: {e}")
        raise HTTPException(status_code=500, detail="Error updating points in database.")


@app.get("/get_points/{user_id}")
async def get_points(user_id: int):
    """Gets a user's current point balance."""
    query = "SELECT points FROM user_points WHERE user_id = :user_id"
    result = await database.fetch_one(query, values={"user_id": user_id})
    if result:
        return {"user_id": user_id, "points": result["points"]}
    else:
        # If user is not in our new table, they have 0 points.
        return {"user_id": user_id, "points": 0}

@app.post("/set_points")
async def set_points(data: PointSet):
    """Sets a user's points to a specific value. Used for migration."""
    query = """
    INSERT INTO user_points (user_id, points)
    VALUES (:user_id, :points)
    ON DUPLICATE KEY UPDATE points = VALUES(points);
    """
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
        print(f"🔥 ERROR assigning mentor: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail="Failed to assign mentor")

@app.get("/")
async def root():
    return {"message": "Mentor API is running"}


