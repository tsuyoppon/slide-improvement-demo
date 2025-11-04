import os
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from mangum import Mangum

from .schemas import QuizItem, GradeRequest, GradeResult, RowResult
from .data_loader import load_quizzes, UI_IMPROVEMENTS
from .auth import get_current_user
from .models import (
    QuizSession,
    SaveSessionRequest,
    SessionHistoryResponse,
    UserStatsResponse,
    QuestionResult,
)
from .db_service import SessionService, StatsService


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


# ========================================
# 認証が必要なエンドポイント
# ========================================

@app.post("/api/session/save")
async def save_quiz_session(
    request: SaveSessionRequest,
    user: dict = Depends(get_current_user)
) -> dict:
    """
    クイズセッションを保存
    
    Authorization: Bearer <id_token> ヘッダーが必要
    """
    user_id = user["sub"]  # Cognito の user_id
    
    # リクエストから正解数を計算
    total_questions = len(request.questions)
    correct_answers = sum(1 for q in request.questions if q.is_correct)
    
    # セッションオブジェクトを作成
    session = QuizSession.create_new(
        user_id=user_id,
        total_questions=total_questions,
        correct_answers=correct_answers,
        questions=request.questions,
        session_start_ts=request.session_start_ts,
        time_spent_seconds=request.time_spent_seconds
    )
    
    # DynamoDB に保存
    session_service = SessionService()
    session_service.save_session(session)
    
    # ユーザー統計を更新
    stats_service = StatsService()
    user_stats = stats_service.get_or_create_stats(user_id)
    user_stats.update_with_session(session)
    stats_service.update_user_stats(user_stats)
    
    return {
        "success": True,
        "session_id": session.session_end_ts,
        "score": session.score_percentage
    }


@app.get("/api/history", response_model=SessionHistoryResponse)
async def get_session_history(
    user: dict = Depends(get_current_user),
    limit: int = 50
) -> SessionHistoryResponse:
    """
    ユーザーのクイズ実行履歴を取得
    
    Authorization: Bearer <id_token> ヘッダーが必要
    """
    user_id = user["sub"]
    
    session_service = SessionService()
    sessions, _ = session_service.get_user_sessions(user_id, limit=limit)
    
    return SessionHistoryResponse(
        sessions=sessions,
        total_count=len(sessions)
    )


@app.get("/api/stats", response_model=UserStatsResponse)
async def get_user_stats(
    user: dict = Depends(get_current_user)
) -> UserStatsResponse:
    """
    ユーザーの統計情報と最近のセッションを取得
    
    Authorization: Bearer <id_token> ヘッダーが必要
    """
    user_id = user["sub"]
    
    stats_service = StatsService()
    session_service = SessionService()
    
    user_stats = stats_service.get_or_create_stats(user_id)
    recent_sessions = session_service.get_recent_sessions(user_id, limit=5)
    
    return UserStatsResponse(
        stats=user_stats,
        recent_sessions=recent_sessions
    )


handler = Mangum(app)
