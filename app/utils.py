import asyncio
import json

lines = [
    "Q: What is computer vision? A: A field of AI that enables machines to interpret and understand visual data.",
    "Q: What is an image pixel? A: The smallest unit of an image representing color or intensity.",
    "Q: What is convolution in computer vision? A: A mathematical operation used to extract features from images.",
]

def parse_line(line: str) -> dict | None:
    # Split on ' A: ' to get question and answer
    if "Q:" not in line or "A:" not in line:
        return None
    parts = line.split(" A: ", 1)
    question = parts[0].replace("Q:", "").strip()
    answer = parts[1].strip()
    return {"question": question, "answer": answer}

