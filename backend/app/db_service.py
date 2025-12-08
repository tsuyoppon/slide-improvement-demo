"""
DynamoDB 操作サービス
"""
import os
from typing import List, Optional
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key, Attr
from .models import QuizSession, UserStats, UserDailyActivity, _utc_now_iso

# 環境変数から設定を取得
SESSION_TABLE_NAME = os.environ.get("SESSION_TABLE_NAME")
USER_STATS_TABLE_NAME = os.environ.get("USER_STATS_TABLE_NAME")
USER_DAILY_ACTIVITY_TABLE_NAME = os.environ.get("USER_DAILY_ACTIVITY_TABLE_NAME")

# DynamoDB クライアント
dynamodb = boto3.resource("dynamodb")


def _decimal_to_float(obj):
    """DynamoDB の Decimal 型を float に変換"""
    if isinstance(obj, list):
        return [_decimal_to_float(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: _decimal_to_float(value) for key, value in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj


def _float_to_decimal(obj):
    """float を DynamoDB の Decimal 型に変換"""
    if isinstance(obj, list):
        return [_float_to_decimal(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: _float_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj


class SessionService:
    """クイズセッション操作サービス"""
    
    def __init__(self):
        if not SESSION_TABLE_NAME:
            raise ValueError("SESSION_TABLE_NAME environment variable is not set")
        self.table = dynamodb.Table(SESSION_TABLE_NAME)
    
    def save_session(self, session: QuizSession) -> None:
        """セッションを保存"""
        item = _float_to_decimal(session.model_dump())
        self.table.put_item(Item=item)
    
    def get_user_sessions(
        self,
        user_id: str,
        limit: int = 50,
        start_key: Optional[dict] = None
    ) -> tuple[List[QuizSession], Optional[dict]]:
        """
        ユーザーのセッション履歴を取得（新しい順）
        
        Returns:
            (sessions, last_evaluated_key) のタプル
        """
        query_params = {
            "KeyConditionExpression": Key("user_id").eq(user_id),
            "Limit": limit,
            "ScanIndexForward": False  # 降順（新しい順）
        }
        
        if start_key:
            query_params["ExclusiveStartKey"] = start_key
        
        response = self.table.query(**query_params)
        
        sessions = [
            QuizSession(**_decimal_to_float(item))
            for item in response.get("Items", [])
        ]
        
        last_key = response.get("LastEvaluatedKey")
        
        return sessions, last_key
    
    def get_recent_sessions(self, user_id: str, limit: int = 5) -> List[QuizSession]:
        """最近のセッションを取得"""
        sessions, _ = self.get_user_sessions(user_id, limit=limit)
        return sessions


class StatsService:
    """ユーザー統計操作サービス"""
    
    def __init__(self):
        if not USER_STATS_TABLE_NAME:
            raise ValueError("USER_STATS_TABLE_NAME environment variable is not set")
        self.table = dynamodb.Table(USER_STATS_TABLE_NAME)
    
    def get_user_stats(self, user_id: str) -> Optional[UserStats]:
        """ユーザー統計を取得"""
        response = self.table.get_item(Key={"user_id": user_id})
        
        if "Item" not in response:
            return None
        
        return UserStats(**_decimal_to_float(response["Item"]))
    
    def update_user_stats(self, stats: UserStats, session: Optional[QuizSession] = None) -> None:
        """ユーザー統計を更新"""
        if session and session.questions:
            for question in session.questions:
                if not question.improvements:
                    continue
                for improvement in question.improvements:
                    label = improvement.label
                    if not label:
                        continue
                    item_stats = stats.improvement_item_stats.setdefault(
                        label,
                        {"correct": 0, "attempts": 0},
                    )
                    item_stats["attempts"] += 1
                    if improvement.is_correct:
                        item_stats["correct"] += 1

        item = _float_to_decimal(stats.model_dump())
        self.table.put_item(Item=item)
    
    def get_or_create_stats(self, user_id: str) -> UserStats:
        """ユーザー統計を取得、存在しなければ新規作成"""
        stats = self.get_user_stats(user_id)
        
        if stats is None:
            stats = UserStats(user_id=user_id)
            self.update_user_stats(stats)
        
        return stats

    def increment_access(self, user_id: str, accessed_at: Optional[str] = None) -> UserStats:
        """アクセス回数を原子的にインクリメントし、最終アクセス日時を更新"""
        ts = accessed_at or _utc_now_iso()
        response = self.table.update_item(
            Key={"user_id": user_id},
            UpdateExpression=(
                "SET access_count = if_not_exists(access_count, :zero) + :inc, "
                "last_access_at = :ts, updated_at = :ts"
            ),
            ExpressionAttributeValues={
                ":inc": Decimal(1),
                ":zero": Decimal(0),
                ":ts": _float_to_decimal(ts),
            },
            ReturnValues="ALL_NEW",
        )
        return UserStats(**_decimal_to_float(response["Attributes"]))


class DailyActivityService:
    """ユーザーの日別アクセス集計サービス"""

    def __init__(self):
        if not USER_DAILY_ACTIVITY_TABLE_NAME:
            raise ValueError("USER_DAILY_ACTIVITY_TABLE_NAME environment variable is not set")
        self.table = dynamodb.Table(USER_DAILY_ACTIVITY_TABLE_NAME)

    def increment_daily_login(self, user_id: str, date_str: str) -> UserDailyActivity:
        """日別ログイン回数を原子的にインクリメント"""
        response = self.table.update_item(
            Key={"user_id": user_id, "date": date_str},
            UpdateExpression="SET login_count = if_not_exists(login_count, :zero) + :inc, updated_at = :now",
            ExpressionAttributeValues={
                ":inc": Decimal(1),
                ":zero": Decimal(0),
                ":now": _float_to_decimal(_utc_now_iso()),
            },
            ReturnValues="ALL_NEW",
        )

        return UserDailyActivity(**_decimal_to_float(response["Attributes"]))

    def list_by_date(self, date_str: str, limit: int = 200) -> List[UserDailyActivity]:
        """指定日付の全ユーザー分を取得（簡易のため Scan を使用）"""
        response = self.table.scan(
            FilterExpression=Attr("date").eq(date_str),
            Limit=limit,
        )
        return [UserDailyActivity(**_decimal_to_float(item)) for item in response.get("Items", [])]
