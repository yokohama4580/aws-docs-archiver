#!/usr/bin/env python3
"""
AWS CDKアプリケーション - AWSドキュメントアーカイブシステムのインフラ定義
"""
from aws_cdk import (
    App,
    Stack,
    Duration,
    Environment,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    RemovalPolicy
)
from constructs import Construct


class AwsDocsArchiverStack(Stack):
    """
    AWSドキュメントアーカイブシステムのインフラスタック
    """
    def __init__(self, scope: Construct, construct_id: str, env=None, **kwargs) -> None:
        super().__init__(scope, construct_id, env=env, **kwargs)

        # S3バケット - ドキュメントコンテンツ保存用
        docs_bucket = s3.Bucket(
            self, "DocumentContentBucket",
            bucket_name="aws-docs-archive-content",
            versioned=True,  # バージョニングを有効化
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ArchiveOldVersions",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(30)
                        )
                    ]
                )
            ],
            removal_policy=RemovalPolicy.RETAIN  # スタック削除時にバケットを保持
        )

        # DynamoDBテーブル - メタデータ管理用
        metadata_table = dynamodb.Table(
            self, "DocumentMetadataTable",
            table_name="aws-docs-archive-metadata",
            partition_key=dynamodb.Attribute(
                name="url",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN  # スタック削除時にテーブルを保持
        )

        # Lambda関数 - クローラー実行用
        crawler_lambda = lambda_.Function(
            self, "DocumentCrawlerFunction",
            function_name="aws-docs-crawler",
            runtime=lambda_.Runtime.PYTHON_3_9,
            code=lambda_.Code.from_asset("../crawler"),
            handler="aws_docs_crawler.lambda_handler",
            timeout=Duration.minutes(15),
            memory_size=1024,
            environment={
                "S3_BUCKET_NAME": docs_bucket.bucket_name,
                "DYNAMODB_TABLE_NAME": metadata_table.table_name
            }
        )

        # Lambda関数にS3とDynamoDBへのアクセス権限を付与
        docs_bucket.grant_read_write(crawler_lambda)
        metadata_table.grant_read_write_data(crawler_lambda)

        # Lambda用のIAMポリシーを追加
        crawler_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:ListBucket",
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Scan"
                ],
                resources=[
                    docs_bucket.bucket_arn,
                    f"{docs_bucket.bucket_arn}/*",
                    metadata_table.table_arn
                ]
            )
        )

        # EventBridgeルール - 毎日実行するスケジュール
        daily_schedule = events.Rule(
            self, "DailyCrawlSchedule",
            rule_name="aws-docs-daily-crawl",
            schedule=events.Schedule.cron(
                minute="0",
                hour="3",  # 日本時間12:00頃（UTC 03:00）
                day="*",
                month="*",
                year="*"
            )
        )

        # スケジュールにLambdaをターゲットとして追加
        daily_schedule.add_target(targets.LambdaFunction(crawler_lambda))


app = App()

# 環境変数から環境情報を取得（デフォルトはdev）
env_name = app.node.try_get_context('env') or 'dev'

# 環境ごとの設定
environments = {
    'dev': Environment(
        account=app.node.try_get_context('dev_account') or '123456789012',
        region=app.node.try_get_context('dev_region') or 'ap-northeast-1'
    ),
    'prod': Environment(
        account=app.node.try_get_context('prod_account') or '123456789012',
        region=app.node.try_get_context('prod_region') or 'ap-northeast-1'
    )
}

# 環境に基づいたスタック名
stack_name = f"AwsDocsArchiverStack-{env_name}"

# スタックをデプロイ
AwsDocsArchiverStack(app, stack_name, env=environments.get(env_name))

app.synth()