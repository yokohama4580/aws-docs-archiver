"""
ユーティリティ関数
"""
import logging
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import hashlib
import json
import boto3
import botocore.exceptions
from bs4 import BeautifulSoup

from crawler.constants import (
    AWS_DOCS_BASE_URL, 
    DYNAMODB_TABLE_NAME, 
    S3_BUCKET_NAME,
    USER_AGENT
)
from crawler.models import PageContent, PageMetadata, PageVersion


# ロガー設定
logger = logging.getLogger(__name__)


def setup_logging(level=logging.INFO):
    """
    ロギングの設定
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def extract_page_title(html_content: str) -> str:
    """
    HTMLコンテンツからページタイトルを抽出
    
    Args:
        html_content: HTMLコンテンツ
        
    Returns:
        抽出したページタイトル
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    title_tag = soup.find('title')
    if title_tag:
        return title_tag.text.strip()
    return "Unknown Title"


def extract_links_from_page(html_content: str, base_url: str) -> List[str]:
    """
    HTMLコンテンツから関連するリンクを抽出
    
    Args:
        html_content: HTMLコンテンツ
        base_url: ベースURL
        
    Returns:
        抽出したリンクのリスト
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    links = []
    
    # 全てのaタグを検索
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        
        # 相対URLを絶対URLに変換
        if href.startswith('/'):
            href = f"{base_url}{href}"
        
        # 同じドメイン内のAWSドキュメントリンクのみを収集
        if href.startswith(AWS_DOCS_BASE_URL):
            links.append(href)
    
    return links


def save_content_to_s3(
    page_content: PageContent, 
    bucket_name: str = S3_BUCKET_NAME
) -> Optional[str]:
    """
    ページコンテンツをS3に保存
    
    Args:
        page_content: 保存するページコンテンツ
        bucket_name: S3バケット名
        
    Returns:
        S3バージョンID
    """
    try:
        s3 = boto3.client('s3')
        
        # URLをS3のオブジェクトキーに変換
        url_key = page_content.url.replace(AWS_DOCS_BASE_URL, '').strip('/')
        if not url_key:
            url_key = 'index'
            
        # 日付ベースのパス
        date_prefix = page_content.timestamp.strftime('%Y/%m/%d')
        
        # キーの形式：YYYY/MM/DD/url-path.html
        object_key = f"{date_prefix}/{url_key}.html"
        
        # S3に保存
        response = s3.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=page_content.html_content.encode('utf-8'),
            ContentType='text/html',
            Metadata={
                'url': page_content.url,
                'title': page_content.title,
                'timestamp': page_content.timestamp.isoformat(),
                'content_hash': page_content.content_hash
            }
        )
        
        return response.get('VersionId')
        
    except botocore.exceptions.ClientError as e:
        logger.error(f"S3保存エラー: {e}")
        return None


def get_page_metadata_from_dynamodb(
    url: str, 
    table_name: str = DYNAMODB_TABLE_NAME
) -> Optional[PageMetadata]:
    """
    DynamoDBからページメタデータを取得
    
    Args:
        url: ページURL
        table_name: DynamoDBテーブル名
        
    Returns:
        ページメタデータ、存在しない場合はNone
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name)
        
        response = table.get_item(Key={'url': url})
        
        if 'Item' in response:
            return PageMetadata.from_dict(response['Item'])
        return None
        
    except botocore.exceptions.ClientError as e:
        logger.error(f"DynamoDB取得エラー: {e}")
        return None


def save_page_metadata_to_dynamodb(
    metadata: PageMetadata, 
    table_name: str = DYNAMODB_TABLE_NAME
) -> bool:
    """
    ページメタデータをDynamoDBに保存
    
    Args:
        metadata: 保存するメタデータ
        table_name: DynamoDBテーブル名
        
    Returns:
        成功したかどうか
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name)
        
        table.put_item(Item=metadata.to_dict())
        return True
        
    except botocore.exceptions.ClientError as e:
        logger.error(f"DynamoDB保存エラー: {e}")
        return False


def rate_limit(min_interval: float = 1.0):
    """
    リクエスト間隔を制限するデコレータ
    
    Args:
        min_interval: 最小リクエスト間隔（秒）
    """
    last_time = [0.0]
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            current_time = time.time()
            elapsed = current_time - last_time[0]
            
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
                
            result = func(*args, **kwargs)
            last_time[0] = time.time()
            return result
        return wrapper
    return decorator