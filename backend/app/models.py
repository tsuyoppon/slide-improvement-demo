"""
DynamoDB モデル定義
"""
from datetime import datetime, UTC
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    """UTC現在時刻をISO8601のZ表記で返す"""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ImprovementItemResult(BaseModel):
    """改善項目ごとの解答状況"""
    label: str
    answered: bool
    correct: bool
    is_correct: bool


class QuestionResult(BaseModel):
    """個別の問題結果"""
    question_id: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    time_spent_seconds: Optional[int] = None
    improvements: List[ImprovementItemResult] = Field(default_factory=list)


class QuizSession(BaseModel):
    """クイズセッション（1回分の実行結果）"""
    user_id: str
    session_end_ts: str  # ISO 8601 形式のタイムスタンプ（RANGE キー）
    session_start_ts: str  # ISO 8601 形式のタイムスタンプ
    quiz_type: str = "slide_improvement"  # クイズの種類
    total_questions: int
    correct_answers: int
    score_percentage: float
    time_spent_seconds: Optional[int] = None
    questions: List[QuestionResult]
    
    @classmethod
    def create_new(
        cls,
        user_id: str,
        total_questions: int,
        correct_answers: int,
        questions: List[QuestionResult],
        session_start_ts: Optional[str] = None,
        time_spent_seconds: Optional[int] = None
    ) -> "QuizSession":
        """新しいセッションを作成"""
        now = _utc_now_iso()
        
        return cls(
            user_id=user_id,
            session_end_ts=now,
            session_start_ts=session_start_ts or now,
            total_questions=total_questions,
            correct_answers=correct_answers,
            score_percentage=round((correct_answers / total_questions * 100), 2),
            time_spent_seconds=time_spent_seconds,
            questions=questions
        )


class UserStats(BaseModel):
    """ユーザーの集計統計 + アクセス情報"""
    user_id: str
    total_sessions: int = 0
    total_questions_answered: int = 0
    total_correct_answers: int = 0
    average_score: float = 0.0
    best_score: float = 0.0
    last_quiz_date: Optional[str] = None
    # アクセス集計
    access_count: int = 0
    last_access_at: Optional[str] = None
    updated_at: str = Field(default_factory=_utc_now_iso)
    improvement_item_stats: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    
    def update_with_session(self, session: QuizSession) -> None:
        """セッション結果で統計を更新"""
        self.total_sessions += 1
        self.total_questions_answered += session.total_questions
        self.total_correct_answers += session.correct_answers
        
        # 平均スコアを再計算
        self.average_score = round(
            (self.total_correct_answers / self.total_questions_answered * 100), 2
        )
        
        # ベストスコアを更新
        if session.score_percentage > self.best_score:
            self.best_score = session.score_percentage
        
        # 最終受験日を更新
        self.last_quiz_date = session.session_end_ts
        self.updated_at = _utc_now_iso()

    def update_access(self, accessed_at: Optional[str] = None) -> None:
        """アクセス時に呼び出し、回数と最終日時を更新"""
        self.access_count += 1
        self.last_access_at = accessed_at or _utc_now_iso()
        self.updated_at = _utc_now_iso()


class SaveSessionRequest(BaseModel):
    """セッション保存リクエスト"""
    session_start_ts: Optional[str] = None
    time_spent_seconds: Optional[int] = None
    questions: List[QuestionResult]


class SessionHistoryResponse(BaseModel):
    """セッション履歴レスポンス"""
    sessions: List[QuizSession]
    total_count: int


class UserStatsResponse(BaseModel):
    """ユーザー統計レスポンス"""
    stats: UserStats
    recent_sessions: List[QuizSession]


class UserDailyActivity(BaseModel):
    """ユーザーの日別アクティビティ（ログイン/アクセス）"""
    user_id: str
    date: str  # YYYY-MM-DD
    login_count: int = 0
    updated_at: str = Field(default_factory=_utc_now_iso)
