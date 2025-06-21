# --- IMPORTS ---
import uvicorn
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from databases import Database
import asyncio

# --- Configuration ---
DATABASE_URL = "mysql://root:UdELAxesZYuFCtrPNMlEQWAuLhFKajbo@centerbeam.proxy.rlwy.net:40467/railway"

database = Database(DATABASE_URL)
app = FastAPI()

# --- Data Models ---
class MentorAssignment(BaseModel):
    mentor_id: int
    mentee_id: int

# --- API Events ---
@app.on_event("startup")
async def startup_event():
    """This runs when the API server starts."""
    # --- DIAGNOSTIC TEST ---
    # We are temporarily skipping the database connection to see if the server can start without it.
    print("--- RUNNING DIAGNOSTIC TEST: SKIPPING DATABASE CONNECTION ---")
    pass # Do nothing here for the test

@app.on_event("shutdown")
async def shutdown_event():
    """This runs when the API server stops."""
    # Since we didn't connect, we don't need to disconnect.
    print("Shutdown event called.")
    pass

# --- API Endpoints ---
@app.post("/mentor-assignments")
async def assign_mentor(data: MentorAssignment):
    # This will fail because the database isn't connected, which is expected for this test.
    raise HTTPException(status_code=503, detail="Database is offline for testing.")

@app.get("/")
async def root():
    return {"message": "Mentor API is running (in test mode)"}


# --- Server Startup Logic ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("api_main:app", host="0.0.0.0", port=port, reload=False)

@app.get("/")
async def root():
    return {"message": "Mentor API is running"}


