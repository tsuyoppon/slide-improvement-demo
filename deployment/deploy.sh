#!/bin/bash
set -euo pipefail

# Add Homebrew to PATH (for Apple Silicon Mac)
export PATH="/opt/homebrew/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 Lambda 関数のビルド & デプロイを開始します"
echo ""

# SAM ビルド
echo "📦 SAM ビルド中..."
cd "$SCRIPT_DIR"
sam build

echo ""
echo "✅ ビルド完了"
echo ""

# SAM デプロイ
echo "☁️  AWS にデプロイ中..."
sam deploy

echo ""
echo "🎉 デプロイ完了！"
echo ""

# API エンドポイントを表示
echo "📋 デプロイされた API:"
aws cloudformation describe-stacks \
    --stack-name slidequiz-api \
    --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
    --output text

echo ""
echo "🔍 新しいエンドポイント:"
echo "  POST /api/session/save   - セッション保存（要認証）"
echo "  GET  /api/history         - 履歴取得（要認証）"
echo "  GET  /api/stats           - 統計取得（要認証）"
