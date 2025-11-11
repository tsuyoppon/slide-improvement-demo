# サーバーレスデプロイ手順（Lambda + API Gateway + S3 + CloudFront）

このドキュメントでは、FastAPI バックエンドを AWS Lambda + API Gateway へ、静的アセット（CSV・画像・フロントエンド）を S3/CloudFront へ配置する手順を説明します。全体を通して CLI ベースで再現性を確保する構成です。

## 1. 事前準備（ローカル環境）

1. **AWS CLI インストール**
   - macOS: Homebrew が未導入の場合は下記コマンドでインストールしてください。
     ```bash
     /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
     ```
     - Apple Silicon(macOS 11+) の場合はインストール後に `echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile`、`eval "$ (/opt/homebrew/bin/brew shellenv)"` を実行してパスを通します。
     - Intel Mac の場合は `echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile`、`eval "$(/usr/local/bin/brew shellenv)"`。
   - Homebrew インストール後: `brew install awscli`
   - Homebrew を使いたくない場合は、公式 PKG (https://docs.aws.amazon.com/ja_jp/cli/latest/userguide/getting-started-install.html#cliv2-mac-install) をダウンロードして実行する方法も利用できます。
   - Windows (Chocolatey): `choco install awscli`
   - Linux: `curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && unzip awscliv2.zip && sudo ./aws/install`
2. **AWS SAM CLI インストール**
   - macOS (Homebrew): `brew tap aws/tap && brew install aws-sam-cli`
   - Windows (MSI): https://github.com/aws/aws-sam-cli/releases からインストーラをダウンロード
   - Linux: `brew install aws/tap/aws-sam-cli` または公式ドキュメントの ZIP 手順
3. **インストール確認**
   ```bash
   aws --version
   sam --version
   ```
4. **AWS 認証情報の設定**
   - `aws configure` を実行し、IAM ユーザーの Access Key / Secret Key、リージョン、出力形式を入力します。
   - プロファイルを複数使いたい場合は `aws configure --profile <name>` を利用します。
5. **Docker と Python 3.12**
   - Docker Desktop などが起動していること、`python3 --version` が 3.12 系であることを確認してください（SAM のビルドで利用）。
   - ローカルで `uvicorn` を用いた検証を行う場合は `pip install -r backend/requirements-dev.txt` を実行して開発用依存関係を追加してください（Lambda パッケージには含めていません）。

## 2. 静的アセット（CSV・画像）を S3 に配置

1. S3 バケットを新規作成（例: `slidequiz-assets`）。バージョニング有効化を推奨します。
2. クイズ CSV (`Rubato_labels_converted_trial4.csv`) を任意のプレフィックスにアップロード（例: `data/Rubato_labels_converted_trial4.csv`）。
3. クイズ画像を同バケット内のプレフィックスにアップロード（例: `images/12345.png`）。ファイル名は「クイズID.拡張子」を統一します。
4. 後述する CloudFront で配信する場合、バケットのパブリックアクセスはブロックしたままで構いません（OAC/OAI を利用）。

## 3. CloudFront で画像／フロントエンドを配信

1. CloudFront ディストリビューションを作成し、オリジンに手順2で作成した S3 バケットを指定します。
2. ビヘイビアを設定し、`/images/*` をS3バケットへルーティング。必要に応じて OAC を作成し S3 バケットポリシーを更新します。
3. 静的フロントエンド（`index.html` 等）を別バケットに配置する場合、同じディストリビューションで別オリジンとして追加するか、別ディストリビューションを用意します。
4. 作成後、CloudFront の URL（例: `https://d2i6vi3986p0t3.cloudfront.net`）を控え、画像配信パス（例: `https://d2i6vi3986p0t3.cloudfront.net/images`）を `IMAGES_BASE_URL` として利用します。

### CloudFront Function での `/login` リダイレクト

- `deployment/cloudfront-function.js` では、`/login` へのアクセスを Cognito Hosted UI に 302 リダイレクトし、その他のディレクトリアクセスには `index.html` を付与します。
- 更新後に `deployment/setup_cloudfront_function.sh` を実行すると、関数コードの更新・公開とディストリビューションへの関連付けが行われます（CloudFront の反映には数分かかる場合があります）。
- Cognito の Hosted UI URL を変更する場合は、同ファイル内の `cognitoLoginUrl` を編集し、再度スクリプトを実行してください。

## 4. SAM テンプレートで API をデプロイ

1. プロジェクトルートで以下を実行します。
   ```bash
   cd deployment
   sam build
    # SAM はリポジトリ全体をコピーするため、ローカルに残している大容量ファイルを除外します。
    rm -rf .aws-sam/build/SlideQuizFunction/学習用画像_* || true
    rm -f .aws-sam/build/SlideQuizFunction/Rubato_labels_converted_trial4.csv || true
    rm -f .aws-sam/build/SlideQuizFunction/*.pdf || true
   sam deploy \
     --guided \
     --stack-name slidequiz-api \
     --parameter-overrides \
         CsvBucketName=slidequiz-assets \
         CsvObjectKey=data/Rubato_labels_converted_trial4.csv \
         ImagesBaseUrl=https://d2i6vi3986p0t3.cloudfront.net/images \
         ImageExtension=png \
         ProvisionedConcurrency=1
   ```
2. `--guided` では以下が質問されます。
   - 使用リージョン
   - デプロイ用アーティファクト S3 バケット（未作成の場合は自動作成を許可）
   - IAM ロールの作成可否（初回は`Y`を選択）
   - 以降も `sam deploy` で同じスタックを更新できます。

   上記コマンド例では、`IMAGES_BASE_URL` に今回作成した CloudFront のパス（`https://d2i6vi3986p0t3.cloudfront.net/images`）を指定しています。ディストリビューションが別の URL になる場合は読み替えてください。

## 5. デプロイ確認と動作テスト

1. `sam deploy` の出力に `ApiUrl` が表示されます。ブラウザまたは `curl` で `<ApiUrl>/api/health` を確認し、`{"status": "ok"}` が返ることを確認します。
2. `index.html` をホスティングしているバケット/CloudFront からフロントエンドを表示し、以下を行います。
   - `window.API_BASE = '<ApiUrl>'` を設定（スクリプト挿入やビルド時に埋め込み）
   - クイズ画像が CloudFront から読み込めるか確認
   - 回答～採点が正常に動作するか確認
3. CloudWatch Logs (`/aws/lambda/<FunctionName>`) でエラーがないか確認します。

## 6. 運用 TIPS

- **プロビジョンドコンカレンシー**: `ProvisionedConcurrency` パラメータで調整。0 にすると完全サーバーレス（コールドスタート有り）になります。
- **CSV 更新**: S3 のファイルを差し替えるだけでOK。Lambda内部でキャッシュしないため、新しいコンテナ起動時に最新がロードされます。
- **権限**: SAM テンプレートで Lambda 実行ロールに `S3ReadPolicy` を付与しています。別バケットを参照する場合はテンプレートを更新してください。
- **静的フロントのCORS**: APIドメインとフロントドメインが異なる場合、`template.yaml` の `CorsConfiguration` を適宜制限してください。

以上で CLI を用いたサーバーレス分離構成のセットアップが完了します。
