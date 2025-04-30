# AWS OIDC認証のセットアップガイド

このガイドでは、GitHub ActionsからAWSリソースにアクセスするためのOIDC認証の設定方法を説明します。OIDCを使用することで、GitHub ActionsワークフローでAWS認証情報を直接保存する必要がなくなります。

## 1. AWS IAM Identity Providerの作成

1. AWSマネジメントコンソールにログインし、IAMサービスに移動します
2. 左側のナビゲーションから「IDプロバイダ」を選択します
3. 「プロバイダを追加」をクリックします
4. プロバイダの種類として「OpenID Connect」を選択します
5. 以下の情報を入力します：
   - プロバイダのURL: `https://token.actions.githubusercontent.com`
   - 対象者: `sts.amazonaws.com`
6. 「プロバイダを追加」をクリックして保存します

## 2. IAMロールの作成

### 開発環境用ロール

1. IAMコンソールで「ロール」に移動し、「ロールを作成」をクリックします
2. 信頼されたエンティティタイプとして「ウェブアイデンティティ」を選択します
3. アイデンティティプロバイダとして、先ほど作成したGitHub用のOIDCプロバイダを選択します
4. 対象者に「sts.amazonaws.com」が設定されていることを確認します
5. （オプション）条件を追加します：
   ```
   "StringLike": {
     "token.actions.githubusercontent.com:sub": "repo:yokohama4580/aws-docs-archiver:ref:refs/heads/main"
   }
   ```
6. 「次へ」をクリックします
7. アクセス許可ポリシーには、CDKデプロイに必要な権限を付与します（例：`AdministratorAccess`または適切に制限されたポリシー）
8. ロール名に「GitHubActions-DevRole」などの識別しやすい名前を入力し、作成します
9. 作成したロールのARNをメモします（例：`arn:aws:iam::123456789012:role/GitHubActions-DevRole`）

### 本番環境用ロール

上記の手順と同様に、本番環境用のIAMロールも作成します。ロール名は「GitHubActions-ProdRole」などとし、必要に応じて条件をさらに制限します。

## 3. GitHub Secretsの設定

1. GitHubリポジトリで「Settings」→「Secrets and variables」→「Actions」に移動します
2. 以下の秘密情報を追加します：
   - `DEV_AWS_ROLE_ARN`: 開発環境用ロールのARN
   - `PROD_AWS_ROLE_ARN`: 本番環境用ロールのARN

## 4. GitHub Environmentsの設定

1. GitHubリポジトリで「Settings」→「Environments」に移動します
2. 「New environment」をクリックし、「dev」という名前で環境を作成します
3. 必要に応じて承認者や保護ルールを設定します
4. 同様に「prod」環境も作成し、こちらには必ず承認者を設定します

## 5. CD設定の確認

これで、`.github/workflows/cd.yml`ファイルで定義されたワークフローが、GitHub ActionsからAWSへのOIDC認証を使用してデプロイを実行できるようになります。ワークフロー内では以下のように認証が設定されています：

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ secrets.DEV_AWS_ROLE_ARN }}
    aws-region: ap-northeast-1
```

## トラブルシューティング

OIDC認証に問題が発生した場合は、以下を確認してください：

1. IAM Identity Providerの設定が正しいか
2. IAMロールの信頼ポリシーが適切か
3. GitHub Secretsに正しいロールARNが設定されているか
4. GitHub Actionsのワークフローに`permissions: id-token: write`が設定されているか