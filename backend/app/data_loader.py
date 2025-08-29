import csv
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set


# UI 表示用の改善項目（順序固定）
UI_IMPROVEMENTS: List[str] = [
    "ピクトグラムを挿入する",
    "小見出し(基本図解も)を追加する",
    "文字の強調",
    "領域の強調",
    "スライドタイトル（T1）、スライドメッセージ（T2)を追加する",
    "応用図解を使う（グリッド構造にする等）",
    "文章を箇条書きにする",
    "評価を加える",
    "左から右の流れ、上から下の流れ",
    "MECEかどうか",
]

# UI ラベル -> CSV カラム名
LABEL_TO_COL = {
    "ピクトグラムを挿入する": "ch1",
    "小見出し(基本図解も)を追加する": "ch2",
    "文字の強調": "ch3",
    "領域の強調": "ch4",
    "スライドタイトル（T1）、スライドメッセージ（T2)を追加する": "ch5",
    "応用図解を使う（グリッド構造にする等）": "ch6",
    "文章を箇条書きにする": "ch7",
    "評価を加える": "ch8",
    "左から右の流れ、上から下の流れ": "ch9",
    "MECEかどうか": "ch10",
}


@dataclass
class QuizDef:
    id: str
    improvements: List[str]
    correct: Set[str]
    image_relpath: Optional[str]  # STATIC_DIR からの相対パス（URL は /static/<relpath>）


def _truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _normalize_headers(headers: List[str]) -> List[str]:
    return [h.replace("\ufeff", "").strip() for h in headers]


def _find_image_relpath(static_dir: str, quiz_id: str, images_dir_env: Optional[str]) -> Optional[str]:
    """static_dir 配下で見つかった画像への相対パスを返す。見つからなければ None。
    優先順位:
      1) IMAGES_DIR/quiz_id.png
      2) static_dir/quiz_id.png
      3) static_dir/**/quiz_id.png（サブディレクトリ探索、深さ1）
    """
    candidates: List[str] = []
    if images_dir_env:
        candidates.append(os.path.join(images_dir_env, f"{quiz_id}.png"))
    candidates.append(os.path.join(static_dir, f"{quiz_id}.png"))

    # 深さ1のサブディレクトリも見る
    try:
        for name in os.listdir(static_dir):
            sub = os.path.join(static_dir, name)
            if os.path.isdir(sub):
                candidates.append(os.path.join(sub, f"{quiz_id}.png"))
    except FileNotFoundError:
        pass

    for p in candidates:
        if os.path.isfile(p):
            try:
                rel = os.path.relpath(p, static_dir)
                # relpath が .. で始まるなら static_dir 外なので無効
                if not rel.startswith(".."):  # under static_dir
                    return rel.replace("\\", "/")
            except Exception:
                continue
    return None


def load_quizzes(static_dir: str, csv_path: str, images_dir_env: Optional[str] = None) -> Dict[str, QuizDef]:
    quizzes: Dict[str, QuizDef] = {}
    if not os.path.isfile(csv_path):
        return quizzes

    with open(csv_path, "r", encoding="utf-8", errors="replace", newline="") as f:
        rdr = csv.reader(f)
        try:
            headers = _normalize_headers(next(rdr))
        except StopIteration:
            return quizzes

        # 列インデックスを引けるように
        idx = {h: i for i, h in enumerate(headers)}
        id_key = "ID" if "ID" in idx else ("id" if "id" in idx else None)
        if id_key is None:
            # BOM 付きのケース
            for k in list(idx.keys()):
                if k.lower().endswith("id"):
                    id_key = k
                    break
        if id_key is None:
            return quizzes

        for row in rdr:
            if not row:
                continue
            quiz_id = str(row[idx[id_key]]).strip()
            if not quiz_id:
                continue

            correct: Set[str] = set()
            for label in UI_IMPROVEMENTS:
                col = LABEL_TO_COL[label]
                j = idx.get(col)
                val = row[j] if j is not None and j < len(row) else "0"
                if _truthy(val):
                    correct.add(label)

            image_rel = _find_image_relpath(static_dir, quiz_id, images_dir_env)

            quizzes[quiz_id] = QuizDef(
                id=quiz_id,
                improvements=list(UI_IMPROVEMENTS),
                correct=correct,
                image_relpath=image_rel,
            )

    return quizzes

