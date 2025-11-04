#!/bin/bash
set -euo pipefail

# Add Homebrew to PATH (for Apple Silicon Mac)
export PATH="/opt/homebrew/bin:$PATH"

# S3 に認証コールバックページをアップロードするスクリプト

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BUCKET_NAME=$(cat "$SCRIPT_DIR/.bucket_name" 2>/dev/null || echo "slidequiz-assets-20250918231053")

echo "📦 S3 バケット: $BUCKET_NAME"
echo "📁 アップロード元: $REPO_DIR/auth/callback/index.html"

# AWS CLI が利用可能かチェック
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI が見つかりません。インストールしてください:"
    echo "   brew install awscli"
    exit 1
fi

# ファイルの存在確認
if [ ! -f "$REPO_DIR/auth/callback/index.html" ]; then
    echo "❌ auth/callback/index.html が見つかりません"
    exit 1
fi

echo "⬆️  アップロード中..."

# S3 にアップロード
aws s3 cp "$REPO_DIR/auth/callback/index.html" \
    "s3://$BUCKET_NAME/auth/callback/index.html" \
    --content-type "text/html; charset=utf-8" \
    --cache-control "max-age=300" \
    --metadata-directive REPLACE

echo "✅ アップロード完了"

# アップロード確認
echo ""
echo "📋 アップロードされたファイル:"
aws s3 ls "s3://$BUCKET_NAME/auth/callback/"

echo ""
echo "🌐 アクセスURL:"
CLOUDFRONT_DOMAIN=$(cat "$SCRIPT_DIR/.cloudfront_domain" 2>/dev/null || echo "unknown")
echo "   https://$CLOUDFRONT_DOMAIN/auth/callback/"

echo ""
echo "⚠️  注意: CloudFront のキャッシュをクリアする必要がある場合があります"
echo "   aws cloudfront create-invalidation --distribution-id <DISTRIBUTION_ID> --paths '/auth/callback/*'"
