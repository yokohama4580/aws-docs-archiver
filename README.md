# AWS Documentation Archiver

AWS公式ドキュメントをクロールし、日次で変更を確認して保存するシステム。過去の特定時点のAWSドキュメント情報を参照することができるようになります。

## 主な機能

- AWS公式ドキュメントの日次クロール
- ドキュメント変更の検出と保存
- 過去の時点でのドキュメント参照
- 変更履歴の管理

## アーキテクチャ

- クローラーコンポーネント: Python + AWS Lambda
- ストレージ: S3 + DynamoDB
- インフラ: AWS CDK (Python)

## 開発環境セットアップ

1. リポジトリをクローン
```
git clone https://github.com/yokohama4580/aws-docs-archiver.git
cd aws-docs-archiver
```

2. 依存関係のインストール
```
pip install -r requirements.txt
```

3. テスト実行
```
pytest tests/
```

## CI/CDワークフロー

このプロジェクトではGitHub ActionsとAWS OIDC認証を使用したCI/CDパイプラインを実装しています。

### CI (継続的インテグレーション)
- コードの静的解析（pylint）
- ユニットテスト実行（pytest）
- コードカバレッジ計測
- CDKのセキュリティスキャン

### CD (継続的デプロイ)
- GitHub ActionsからのOIDC認証によるAWS環境への安全なデプロイ
- 開発環境(dev)への自動デプロイ
- 本番環境(prod)への手動承認デプロイ

## AWS環境のセットアップ

### OIDC認証のセットアップ

AWS環境でGitHub ActionsからのOIDC認証を有効にするには:

1. AWS IAM Identity Providerの作成
2. IAMロールの設定
3. 信頼ポリシーの設定

詳細な設定手順については`docs/aws-oidc-setup.md`を参照してください。

## セットアップ手順

準備中...

