from typing import List, Optional
from pydantic import BaseModel


class QuizItem(BaseModel):
    id: str
    image_url: Optional[str]
    improvements: List[str]


class GradeRequest(BaseModel):
    quiz_id: str
    selected: List[str]


class RowResult(BaseModel):
    item: str
    answered: bool
    correct: bool
    is_wrong: bool


class GradeResult(BaseModel):
    score: int
    total: int
    rows: List[RowResult]

