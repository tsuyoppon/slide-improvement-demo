import os
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from mangum import Mangum

from .schemas import QuizItem, GradeRequest, GradeResult, RowResult
from .data_loader import load_quizzes, UI_IMPROVEMENTS


# Dev CORS (allow all for local testing)
app = FastAPI(title="Slide Quiz API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Configure static directory for images
STATIC_DIR = os.getenv("STATIC_DIR", os.path.abspath("."))
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


CSV_PATH_ENV = os.getenv("CSV_PATH")
IMAGES_DIR_ENV = os.getenv("IMAGES_DIR")
IMAGES_BASE_URL = os.getenv("IMAGES_BASE_URL")
IMAGE_EXTENSION = os.getenv("IMAGE_EXTENSION", "png")
CSV_S3_BUCKET = os.getenv("CSV_S3_BUCKET")
CSV_S3_KEY = os.getenv("CSV_S3_KEY")


def _fetch_csv_from_s3(bucket: str, key: str) -> Optional[str]:
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("boto3 is required to fetch CSV from S3") from exc

    try:
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = obj["Body"].read()
        return data.decode("utf-8", errors="replace")
    except (BotoCoreError, ClientError) as exc:
        print(f"[warn] Failed to fetch CSV from s3://{bucket}/{key}: {exc}")
    except Exception as exc:  # pragma: no cover
        print(f"[warn] Unexpected error fetching CSV from S3: {exc}")
    return None

# Discover CSV default path
def _default_csv_path() -> Optional[str]:
    if CSV_PATH_ENV and os.path.isfile(CSV_PATH_ENV):
        return CSV_PATH_ENV
    # Try repo root (two levels up from this file)
    here = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(here, "..", ".."))
    candidates = [
        os.path.join(repo_root, "Rubato_labels_converted_trial4.csv"),
        os.path.join(os.getcwd(), "Rubato_labels_converted_trial4.csv"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


# Load quizzes from CSV
CSV_TEXT: Optional[str] = None
if CSV_S3_BUCKET and CSV_S3_KEY:
    CSV_TEXT = _fetch_csv_from_s3(CSV_S3_BUCKET, CSV_S3_KEY)

CSV_PATH = _default_csv_path()
_QUIZZES = load_quizzes(
    STATIC_DIR,
    CSV_PATH,
    IMAGES_DIR_ENV,
    csv_text=CSV_TEXT,
    images_base_url=IMAGES_BASE_URL,
    image_extension=IMAGE_EXTENSION,
)
DEFAULT_QUIZ_ID: Optional[str] = next(iter(_QUIZZES.keys()), None)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/quiz", response_model=QuizItem)
def get_quiz() -> QuizItem:
    # Return the first loaded quiz as default
    quiz_id = DEFAULT_QUIZ_ID or ""
    q = _QUIZZES.get(quiz_id)
    if not q:
        # Fallback to a minimal empty quiz to avoid crash
        return QuizItem(id="", image_url=None, improvements=list(UI_IMPROVEMENTS))
    image_url = q.image_url or (f"/static/{q.image_relpath}" if q.image_relpath else None)
    return QuizItem(id=q.id, image_url=image_url, improvements=list(q.improvements))


@app.post("/api/grade", response_model=GradeResult)
def grade(payload: GradeRequest) -> GradeResult:
    q = _QUIZZES.get(payload.quiz_id)
    if not q:
        return GradeResult(score=0, total=0, rows=[])

    selected = set(payload.selected)
    rows: List[RowResult] = []
    for item in q.improvements:
        answered = item in selected
        correct = item in q.correct
        is_wrong = answered != correct
        rows.append(RowResult(item=item, answered=answered, correct=correct, is_wrong=is_wrong))

    score = sum(1 for r in rows if not r.is_wrong)
    return GradeResult(score=score, total=len(rows), rows=rows)


@app.get("/api/quiz/{quiz_id}", response_model=QuizItem)
def get_quiz_by_id(quiz_id: str) -> QuizItem:
    q = _QUIZZES.get(quiz_id)
    if not q:
        return QuizItem(id=quiz_id, image_url=None, improvements=list(UI_IMPROVEMENTS))
    image_url = q.image_url or (f"/static/{q.image_relpath}" if q.image_relpath else None)
    return QuizItem(id=q.id, image_url=image_url, improvements=list(q.improvements))


@app.get("/api/quiz_ids", response_model=List[str])
def list_quiz_ids() -> List[str]:
    return list(_QUIZZES.keys())


handler = Mangum(app)
