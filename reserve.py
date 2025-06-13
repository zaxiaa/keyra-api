from datetime import datetime, timedelta
from fastapi import FastAPI
from pydantic import BaseModel
import pytz

app = FastAPI()

# Nested input models matching the JSON Schema
class ReservationArgs(BaseModel):
    party_size: int
    reserve_time: str | None = None

class ReservationRequest(BaseModel):
    args: ReservationArgs

def round_to_next_30_minutes(dt: datetime) -> datetime:
    """Round datetime to next 30-minute slot"""
    # Remove seconds and microseconds
    candidate = dt.replace(second=0, microsecond=0)
    # Round down to previous 30-minute mark
    rounded_minute = (candidate.minute // 30) * 30
    candidate = candidate.replace(minute=rounded_minute)
    # If candidate is before original time, add 30 minutes
    if candidate <= dt:
        candidate += timedelta(minutes=30)
    return candidate

@app.post("/generate_reservation_link")
async def generate_link(request: ReservationRequest):
    # Extract arguments from nested structure
    party_size = request.args.party_size
    reserve_time = request.args.reserve_time

    # Use current time if not provided
    if reserve_time:
        dt = datetime.fromisoformat(reserve_time)
    else:
        dt = datetime.now(pytz.utc).astimezone()
    
    # Round to next 30-minute slot
    rounded_dt = round_to_next_30_minutes(dt)
    
    # Format datetime for URL
    dt_str = rounded_dt.strftime("%Y-%m-%dT%H:%M").replace(":", "%3A")
    
    # Generate new link
    base_link = (
        "https://www.opentable.com/restref/client/"
        "?rid=1409818&restref=1409818&lang=en-US&color=1&r3uid=cfe&dark=false"
        f"&partysize={party_size}&datetime={dt_str}"
        "&ot_source=Restaurant%20website&corrid=d9ccb5d8-46e7-46ff-8a23-2b7d0b181992"
    )
    
    return {"reservation_link": base_link}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)