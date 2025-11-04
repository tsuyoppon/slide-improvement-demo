"""
DynamoDB モデル定義
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class QuestionResult(BaseModel):
    """個別の問題結果"""
    question_id: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    time_spent_seconds: Optional[int] = None


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
        now = datetime.utcnow().isoformat() + "Z"
        
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
    """ユーザーの集計統計"""
    user_id: str
    total_sessions: int = 0
    total_questions_answered: int = 0
    total_correct_answers: int = 0
    average_score: float = 0.0
    best_score: float = 0.0
    last_quiz_date: Optional[str] = None
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
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
        self.updated_at = datetime.utcnow().isoformat() + "Z"


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
