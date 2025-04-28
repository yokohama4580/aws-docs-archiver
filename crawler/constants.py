"""
AWSドキュメントクローラーの定数
"""

# AWSドキュメントのベースURL
AWS_DOCS_BASE_URL = "https://docs.aws.amazon.com"

# 主要なサービスカテゴリ
AWS_SERVICES_PATHS = [
    "/ja_jp/ec2/",
    "/ja_jp/s3/",
    "/ja_jp/lambda/",
    "/ja_jp/dynamodb/",
    "/ja_jp/rds/",
    "/ja_jp/cloudformation/",
]

# クロール間隔（秒）
CRAWL_INTERVAL_SECONDS = 86400  # 24時間 = 1日

# ロギング設定
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"

# DynamoDBテーブル名
DYNAMODB_TABLE_NAME = "aws-docs-archive-metadata"

# S3バケット名
S3_BUCKET_NAME = "aws-docs-archive-content"

# ユーザーエージェント
USER_AGENT = "AWS-Docs-Archiver/1.0"