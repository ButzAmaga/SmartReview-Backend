
from io import StringIO
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.ml import generate_qa, generate_qa_batch_t5, generate_qa_sequences
import json
from app.utils import parse_line
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from unstructured.partition.docx import partition_docx
from unstructured.partition.text import partition_text
import tempfile, os, json
import pandas as pd
from langchain_core.documents import Document

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




# ─────────────────────────────────────────
# GROUPING LOGIC
# ─────────────────────────────────────────

def group_elements(elements) -> list[Document]:
    grouped_docs = []
    buffer_content = []
    current_title = ""

    for el in elements:
        if el.category == "Title":
            # Flush any pending title-list group before starting a new title
            if current_title and buffer_content:
                full_text = f"The number of {current_title} examples is \"{len(buffer_content)}\"."
                grouped_docs.append(Document(
                    page_content=full_text,
                    metadata={"category": "Title-List-Group"}
                ))

            # Start new title, reset buffer
            current_title = el.text
            buffer_content = []

        elif el.category == "ListItem":
            # Append each list item as its own Document

            grouped_docs.append(Document(
                page_content=el.text,
                metadata={"category": "List"}
            ))

            
            # Still accumulate for Title-List-Group summary
            if current_title:
                buffer_content.append(el.text)

        else:
            # Flush title-list buffer if it has accumulated list items
            if current_title and buffer_content:
                full_text = f"The number of {current_title} examples is \"{len(buffer_content)}\""
                grouped_docs.append(Document(
                    page_content=full_text,
                    metadata={"category": "Title-List-Group"}
                ))
                buffer_content = []

            if el.category == "Table":
                # Convert each table cell into its own narrative Document
                try:
                    df = pd.read_html(StringIO(el.metadata.text_as_html), header=0)[0]
                    

                    for _, row in df.iterrows():
                        row_values = list(row.items())
                        row_label = row_values[0][1]  # First column = row label
                        rest = row_values[1:]          # Remaining = column + value pairs

                        for col, val in rest:
                            sentence = f"The '{row_label} {col}' value is '{val}'."
                            grouped_docs.append(Document(
                                page_content=sentence,
                                metadata={"category": "NarrativeText"}
                            ))
                except Exception:
                    # Fallback: append raw table text if parsing fails
                    grouped_docs.append(Document(
                        page_content=el.text,
                        metadata={"category": "Table"}
                    ))

            else:
                # NarrativeText and everything else — raw text, no prefix
                grouped_docs.append(Document(
                    page_content=el.text,
                    metadata={"category": el.category}
                ))

    # Flush any remaining title-list group at end of loop
    if current_title and buffer_content:
        full_text = f"The number of {current_title} examples is \"{len(buffer_content)}\""
        grouped_docs.append(Document(
            page_content=full_text,
            metadata={"category": "Title-List-Group"}
        ))

    return grouped_docs


# ─────────────────────────────────────────
# SPLITTING LOGIC
# ─────────────────────────────────────────

def split_documents(grouped_docs: list[Document]) -> list[Document]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=200, # 800
        chunk_overlap=0, # 100
        separators=["\n\n", "\n", "."]
    )

    final_chunks = []

    for doc in grouped_docs:
        if doc.metadata["category"] == "NarrativeText" and len(doc.page_content) > 200:
            # Only split long narrative texts
            splits = text_splitter.split_documents([doc])
            final_chunks.extend(splits)
        else:
            # Keep atomic docs as-is: List, Title-List-Group, table narratives
            final_chunks.append(doc)

    return final_chunks


# ─────────────────────────────────────────
# ELEMENT TO WINDOWS (FOR QA)
# ─────────────────────────────────────────

def process_elements_to_windows(elements) -> list[str]:
    grouped_docs = group_elements(elements)
    final_chunks = split_documents(grouped_docs)
    return [doc.page_content for doc in final_chunks if doc.page_content.strip()]


# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────
@router.post("/qa/docx")
async def qa_from_docx(file: UploadFile = File(...)):
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported.")

    async def event_generator():
        tmp_path = None
        try:
            # Read and write inside the generator so streaming starts immediately
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                contents = await file.read()
                tmp.write(contents)
                tmp_path = tmp.name

            elements = partition_docx(filename=tmp_path)
            windows = process_elements_to_windows(elements)

            """
            chunk_size = 10

            for i in range(0, len(windows), chunk_size):
                window_chunk = windows[i:i + chunk_size]

                generated_qa = generate_qa_batch_t5(window_chunk)

                for qa in generated_qa:
                    print(qa)
                    obj = parse_line(qa)
                    if obj:
                        yield json.dumps(obj) + "\n"
            """


            for window in windows:
                generated_qa = generate_qa(window)
                obj = parse_line(generated_qa)
                if obj:
                    yield json.dumps(obj) + "\n"


        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.post("/qa/txt")
async def qa_from_txt(file: UploadFile = File(...)):
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported.")

    async def event_generator():
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
                contents = await file.read()
                tmp.write(contents)
                tmp_path = tmp.name

            elements = partition_text(filename=tmp_path)
            windows = process_elements_to_windows(elements)
            for window in windows:
                generated_qa = generate_qa_sequences(window)

                for qa in generated_qa:
                    print(qa)
                    obj = parse_line(qa)

                    if obj:
                        yield json.dumps(obj) + "\n"

        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")