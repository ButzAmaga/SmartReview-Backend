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

def parse_line_w_context(line: str) -> dict | None:
    # Check for all required markers
    if not all(x in line for x in ["Q:", "A:", "C:"]):
        return None
    
    # Extract question: between Q: and A:
    q_part = line.split("Q:", 1)[1].split("A:", 1)
    question = q_part[0].strip()
    
    # Extract answer: between A: and C:
    a_part = q_part[1].split("C:", 1)
    answer = a_part[0].strip()
    
    # Extract context: everything after C:
    context = a_part[1].strip()
    
    return {
        "question": question, 
        "answer": answer, 
        "context": context
    }
