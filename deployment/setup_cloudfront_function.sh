#!/bin/bash
set -euo pipefail

# Add Homebrew to PATH (for Apple Silicon Mac)
export PATH="/opt/homebrew/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DISTRIBUTION_ID="E1WZVBMLVMQONC"
FUNCTION_NAME="slidequiz-uri-rewrite"

echo "📋 CloudFront Function を作成・更新します"
echo "Distribution ID: $DISTRIBUTION_ID"
echo "Function Name: $FUNCTION_NAME"

# 既存の関数をチェック
echo ""
echo "🔍 既存の関数を確認中..."
FUNCTION_EXISTS=$(aws cloudfront list-functions --query "FunctionList.Items[?Name=='$FUNCTION_NAME'].Name" --output text 2>/dev/null || echo "")

if [ -z "$FUNCTION_EXISTS" ]; then
    echo "✨ 新規作成します"
    
    # CloudFront Function を作成
    FUNCTION_ARN=$(aws cloudfront create-function \
        --name "$FUNCTION_NAME" \
        --function-config Comment="Redirect /login to Cognito and rewrite directory URIs",Runtime="cloudfront-js-2.0" \
        --function-code fileb://"$SCRIPT_DIR/cloudfront-function.js" \
        --query "FunctionSummary.FunctionMetadata.FunctionARN" \
        --output text)
    
    echo "✅ 関数を作成しました: $FUNCTION_ARN"
else
    echo "♻️  既存の関数を更新します"
    CURRENT_ETAG=$(aws cloudfront describe-function --name "$FUNCTION_NAME" --query "ETag" --output text)
    UPDATE_RESULT=$(aws cloudfront update-function \
        --name "$FUNCTION_NAME" \
        --if-match "$CURRENT_ETAG" \
        --function-config Comment="Redirect /login to Cognito and rewrite directory URIs",Runtime="cloudfront-js-2.0" \
        --function-code fileb://"$SCRIPT_DIR/cloudfront-function.js" \
        --query "FunctionSummary.FunctionMetadata.FunctionARN" \
        --output text)
    FUNCTION_ARN=$UPDATE_RESULT
    echo "✅ 関数コードを更新しました: $FUNCTION_ARN"
fi

# 関数を公開するためにETagを取得
echo ""
echo "📤 関数を公開中..."
ETAG=$(aws cloudfront describe-function --name "$FUNCTION_NAME" --query "ETag" --output text)

PUBLISH_RESULT=$(aws cloudfront publish-function \
    --name "$FUNCTION_NAME" \
    --if-match "$ETAG" \
    --query "FunctionSummary.{ARN:FunctionMetadata.FunctionARN,Stage:FunctionMetadata.Stage}" \
    --output json)

FUNCTION_ARN=$(echo "$PUBLISH_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['ARN'])")

echo "✅ 関数を公開しました"
echo "ARN: $FUNCTION_ARN"

# CloudFront ディストリビューションに関数を関連付け
echo ""
echo "🔗 CloudFront ディストリビューションに関数を関連付けます..."

# 現在の設定を取得
CONFIG_FILE=$(mktemp)
ETAG_FILE=$(mktemp)

aws cloudfront get-distribution-config \
    --id "$DISTRIBUTION_ID" \
    --query "DistributionConfig" \
    --output json > "$CONFIG_FILE"

aws cloudfront get-distribution-config \
    --id "$DISTRIBUTION_ID" \
    --query "ETag" \
    --output text > "$ETAG_FILE"

DIST_ETAG=$(cat "$ETAG_FILE")

# FunctionAssociations を更新（Python で JSON を編集）
python3 << EOF
import json

with open('$CONFIG_FILE', 'r') as f:
    config = json.load(f)

# DefaultCacheBehavior に FunctionAssociations を追加
if 'FunctionAssociations' not in config['DefaultCacheBehavior']:
    config['DefaultCacheBehavior']['FunctionAssociations'] = {
        'Quantity': 0
    }

# Items キーが存在しない場合は作成
if 'Items' not in config['DefaultCacheBehavior']['FunctionAssociations']:
    config['DefaultCacheBehavior']['FunctionAssociations']['Items'] = []

# 既存の関数があれば削除
items = config['DefaultCacheBehavior']['FunctionAssociations']['Items']
items = [item for item in items if item.get('FunctionARN') != '$FUNCTION_ARN']

# 新しい関数を追加
items.append({
    'FunctionARN': '$FUNCTION_ARN',
    'EventType': 'viewer-request'
})

config['DefaultCacheBehavior']['FunctionAssociations']['Items'] = items
config['DefaultCacheBehavior']['FunctionAssociations']['Quantity'] = len(items)

with open('$CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=2)
EOF

# 設定を更新
aws cloudfront update-distribution \
    --id "$DISTRIBUTION_ID" \
    --distribution-config file://"$CONFIG_FILE" \
    --if-match "$DIST_ETAG" > /dev/null

echo "✅ ディストリビューションを更新しました"

# クリーンアップ
rm -f "$CONFIG_FILE" "$ETAG_FILE"

echo ""
echo "🎉 完了しました！"
echo ""
echo "⚠️  注意:"
echo "   - CloudFront の更新には数分かかる場合があります"
echo "   - キャッシュをクリアすることをお勧めします:"
echo "   aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths '/*'"
echo ""
echo "🧪 テスト:"
echo "   https://app2.rubato.co/auth/callback/"
