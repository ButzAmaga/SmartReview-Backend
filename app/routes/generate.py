
from io import StringIO
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from langchain_text_splitters import NLTKTextSplitter, RecursiveCharacterTextSplitter, SpacyTextSplitter
from app.ml import generate_qa, generate_qa_batch_t5, generate_qa_batch_t5_v2, generate_qa_sequences
import json
from app.utils import parse_line, parse_line_w_context
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from unstructured.partition.docx import partition_docx
from unstructured.partition.text import partition_text
import tempfile, os, json
import pandas as pd
from langchain_core.documents import Document
import asyncio
from concurrent.futures import ThreadPoolExecutor





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

SHORT_ITEM_THRESHOLD = 40  # characters — tune this to your data

# ── Tunable knobs ────────────────────────────────────────────────────────────
MIN_WORDS            = 5    # fewer words → likely a label, not a sentence
TITLE_CASE_RATIO     = 0.7  # fraction of words starting uppercase → title-like
SIGNAL_THRESHOLD     = 1    # how many signals must fire to drop the element
                             # set to 2 for a more permissive filter

TERMINAL_PUNCTUATION = frozenset(".!?")
LEAD_IN_PUNCTUATION  = frozenset(":")


def _has_terminal_punctuation(text: str) -> bool:
    """Real sentences end with . ! or ?"""
    return text.rstrip()[-1] in TERMINAL_PUNCTUATION if text.rstrip() else False


def _is_low_word_count(text: str) -> bool:
    """Very short spans are labels, page markers, or stub headers."""
    return len(text.split()) <= MIN_WORDS


def _is_title_cased(text: str) -> bool:
    """
    If most words start with a capital, the element looks like a heading.
    Skips single-char words (a, I, etc.) to avoid false positives.
    """
    words = [w for w in text.split() if len(w) > 1]
    if not words:
        return False
    capitalised = sum(1 for w in words if w[0].isupper())
    return (capitalised / len(words)) >= TITLE_CASE_RATIO


def _is_lead_in(text: str) -> bool:
    """'The following includes:' — ends with colon, meaning content follows."""
    return text.rstrip()[-1] in LEAD_IN_PUNCTUATION if text.rstrip() else False


def _score_signals(text: str) -> int:
    """Count how many structural signals fire."""
    stripped = text.strip()
    score = 0
    if not _has_terminal_punctuation(stripped): score += 1
    if _is_low_word_count(stripped):            score += 1
    if _is_title_cased(stripped):               score += 1
    if _is_lead_in(stripped):                   score += 1
    return score


def is_false_narrative(text: str) -> bool:
    """
    Returns True when a NarrativeText element is structurally
    indistinguishable from a heading, page marker, or lead-in phrase.

    No hardcoded word lists or regex — purely structural signals.
    """
    return _score_signals(text.strip()) >= SIGNAL_THRESHOLD

def group_elements(elements) -> list[Document]:
    grouped_docs = []
    buffer_content = []
    current_title = ""

    for el in elements:
        if el.category == "Title" or el.category == "Header":
            # Flush any pending title-list group before starting a new title
            if current_title and buffer_content:
                grouped_docs.extend(
                    _flush_title_list_group(current_title, buffer_content)
                )

            # Start new title, reset buffer
            current_title = el.text
            buffer_content = []

        elif el.category == "ListItem":
            if current_title:
                buffer_content.append(el.text)
            else:
                # No title context — just emit as a plain List doc
                grouped_docs.append(Document(
                    page_content=el.text,
                    metadata={"category": "List"}
                ))

        else:
            # Flush only if the title actually accumulated list items
            # If current_title exists but buffer is empty, the title had no list — discard it
            if current_title and buffer_content:
                grouped_docs.extend(
                    _flush_title_list_group(current_title, buffer_content)
                )
            # Either way, reset title state — title with no list items is dropped
            buffer_content = []
            current_title = ""

            if el.category == "Table":
                try:
                    df = pd.read_html(StringIO(el.metadata.text_as_html), header=0)[0]

                    if is_matrix_table(df):
                        for _, row in df.iterrows():
                            row_values = list(row.items())
                            row_label = row_values[0][1]
                            rest = row_values[1:]
                            for col, val in rest:
                                sentence = f"The '{row_label} {col}' value is '{val}'."
                                grouped_docs.append(Document(
                                    page_content=sentence,
                                    metadata={"category": "NarrativeText"}
                                ))
                    else:
                        headers = [str(col) for col in df.columns]

                        for row_idx, (_, row) in enumerate(df.iterrows(), start=1):
                            row_parts = [
                                f"the {header} is {value}"
                                for header, value in zip(headers, row.values)
                            ]

                            sentence = f"In row {row_idx} the data are, " + ", ".join(row_parts) + "."

                            grouped_docs.append(
                                Document(
                                    page_content=sentence,
                                    metadata={"category": "NarrativeText"}
                                )
                            )
                except Exception:
                    
                    grouped_docs.append(Document(
                        page_content=el.text,
                        metadata={"category": "Table"}
                    ))

                # ── Was: append every NarrativeText unconditionally
                # ── Now: skip elements that look like false narratives
            if (el.category == "NarrativeText" or el.category == "UncategorizedText") and is_false_narrative(el.text):
                pass   # silently drop page markers, lead-ins, stub headers

            else:
                grouped_docs.append(Document(
                    page_content=el.text,
                    metadata={"category": el.category}
                ))

    # Flush any remaining — only if title had list items
    if current_title and buffer_content:
        grouped_docs.extend(
            _flush_title_list_group(current_title, buffer_content)
        )

    return grouped_docs

def _flush_title_list_group(title: str, items: list[str]) -> list[Document]:
    """
    Decides how to render a title + its list items based on item length.

    Long items  → count summary doc + one doc per item
    Short items → single collapsed sentence
    """
    docs = []
    is_short_list = all(len(item) <= SHORT_ITEM_THRESHOLD for item in items)

    if is_short_list:
        # Collapsed: "X value are 'a, b, c'"
        joined = ", ".join(items)
        sentence = f"{title} value are '{joined}'."
        docs.append(Document(
            page_content=sentence,
            metadata={"category": "Title-List-Group"}
        ))
    else:
        # Count summary
        docs.append(Document(
            page_content=f"The number of content in {title} is {len(items)}.",
            metadata={"category": "Title-List-Group"}
        ))
        # Individual items
        for item in items:
            docs.append(Document(
                page_content=item,
                metadata={"category": "List"}
            ))

    return docs

def is_matrix_table(df: pd.DataFrame) -> bool:
    if df.shape[1] < 2:
        return False
    first_col = df.iloc[:, 0]
    if first_col.dtype != object:
        return False
    if first_col.nunique() != len(first_col):
        return False

    def is_numeric_string(val):
        try:
            float(str(val).replace(",", ""))
            return True
        except ValueError:
            return False

    if first_col.apply(is_numeric_string).any():
        return False
    rest = df.iloc[:, 1:]
    numeric_cols = rest.apply(pd.to_numeric, errors="coerce").notna().all()
    if numeric_cols.sum() < len(rest.columns) / 2:
        return False
    return True
# ─────────────────────────────────────────
# SPLITTING LOGIC
# ─────────────────────────────────────────

def split_documents(grouped_docs: list[Document]) -> list[Document]:
    text_splitter = SpacyTextSplitter(
        pipeline="en_core_web_sm", # The model package we downloaded
        chunk_size=300,             # Target character size optimized for QA pairs
        chunk_overlap=0            # Set overlap if you want shared context between chunks
    )

    final_chunks = []

    for doc in grouped_docs:
        if doc.metadata["category"] == "NarrativeText" and len(doc.page_content) > 300:
            # Only split long narrative texts
            splits = text_splitter.split_documents([doc])


            # filter out false narratives
            # splits = [split for split in splits if not _is_low_word_count(split)]
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
    return [doc.page_content for doc in final_chunks if doc.page_content.strip() and not _is_low_word_count(doc.page_content)]



# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────
@router.post("/qa/docx/v1")
async def qa_from_docx_v1(file: UploadFile = File(...)):
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

            
            
            queue = asyncio.Queue()
            loop = asyncio.get_event_loop()

            # Define the heavy work in a sync function
            def produce_qa(windows):
                chunk_size = 5

                for i in range(0, len(windows), chunk_size):
                    window_chunk = windows[i:i + chunk_size]

                    
                    res = generate_qa_batch_t5_v2(window_chunk)
                   
                    loop.call_soon_threadsafe(queue.put_nowait, res)

                loop.call_soon_threadsafe(queue.put_nowait, None) # Sentinel to stop

            # Run producer in a thread pool
            worker = loop.run_in_executor(ThreadPoolExecutor(), produce_qa, windows)

            while True:
                try:
                    # Wait for 1 second for a result
                    items = await asyncio.wait_for(queue.get(), timeout=1.0)
                    if items is None: break
                    
                    for item in items:
                        obj = parse_line(item)
                        if obj:
                            yield json.dumps(obj) + "\n"

                except asyncio.TimeoutError:
                    # This is the "waiting" state - yield a heartbeat
                    yield "\n" 

            await worker

        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")



@router.post("/qa/docx/v2")
async def qa_from_docx_v2(file: UploadFile = File(...)):
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

            
            
            queue = asyncio.Queue()
            loop = asyncio.get_event_loop()

            # Define the heavy work in a sync function
            def produce_qa(windows):
                chunk_size = 5

                for i in range(0, len(windows), chunk_size):
                    window_chunk = windows[i:i + chunk_size]
                    raw_results = generate_qa_batch_t5_v2(window_chunk)

                    # Combine the Q:A string with the C: context string
                    res = []
                    for raw, window in zip(raw_results, window_chunk):
                        if raw:
                            # Append the context marker and the window content
                            combined = f"{raw.strip()} C: {window.strip()}"
                            res.append(combined)

                    loop.call_soon_threadsafe(queue.put_nowait, res)

                loop.call_soon_threadsafe(queue.put_nowait, None) # Sentinel to stop

            # Run producer in a thread pool
            worker = loop.run_in_executor(ThreadPoolExecutor(), produce_qa, windows)

            while True:
                try:
                    # Wait for 1 second for a result
                    items = await asyncio.wait_for(queue.get(), timeout=1.0)
                    if items is None: break
                    
                    for item in items:
                        obj = parse_line_w_context(item)
                        if obj:
                            yield json.dumps(obj) + "\n"

                except asyncio.TimeoutError:
                    # This is the "waiting" state - yield a heartbeat
                    yield "\n" 

            await worker

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

            queue = asyncio.Queue()
            loop = asyncio.get_event_loop()

            # Define the heavy work in a sync function
            def produce_qa(windows):
                chunk_size = 5

                for i in range(0, len(windows), chunk_size):
                    window_chunk = windows[i:i + chunk_size]
                    raw_results = generate_qa_batch_t5_v2(window_chunk)

                    # Combine the Q:A string with the C: context string
                    res = []
                    for raw, window in zip(raw_results, window_chunk):
                        if raw:
                            # Append the context marker and the window content
                            combined = f"{raw.strip()} C: {window.strip()}"
                            res.append(combined)
                    
                    loop.call_soon_threadsafe(queue.put_nowait, res)


                loop.call_soon_threadsafe(queue.put_nowait, None) # Sentinel to stop

            # Run producer in a thread pool
            worker = loop.run_in_executor(ThreadPoolExecutor(), produce_qa, windows)

            while True:
                try:
                    # Wait for 1 second for a result
                    items = await asyncio.wait_for(queue.get(), timeout=1.0)
                    if items is None: break
                    
                    for item in items:
                        obj = parse_line_w_context(item)
                        print(obj)
                        if obj:
                            yield json.dumps(obj) + "\n"

                except asyncio.TimeoutError:
                    # This is the "waiting" state - yield a heartbeat
                    yield "\n" 

            await worker

        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")