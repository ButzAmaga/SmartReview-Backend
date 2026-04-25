"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.ml import generate_qa
import json
from app.utils import parse_line

router = APIRouter(
    prefix="/generate",
    tags=["generate"],
    responses={404: {"description": "Not found"}},
)

@router.post("/qa")
async def generate_stream(windows: list[str]):
    # Define an internal generator
    async def event_generator():
        for window in windows:
            generated_qa = generate_qa(window)
            obj = parse_line(generated_qa)

            if obj:
                # Use ensure_ascii=False if you have special characters
                yield json.dumps(obj) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


"""