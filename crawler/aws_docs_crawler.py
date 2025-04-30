"""
AWSドキュメントクローラー
"""
import logging
import time
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple
import json
import requests
from bs4 import BeautifulSoup

from crawler.constants import (
    AWS_DOCS_BASE_URL,
    AWS_SERVICES_PATHS,
    USER_AGENT,
    CRAWL_INTERVAL_SECONDS
)
from crawler.models import PageContent, PageMetadata, PageVersion
from crawler.utils import (
    setup_logging,
    extract_page_title,
    extract_links_from_page,
    save_content_to_s3,
    get_page_metadata_from_dynamodb,
    save_page_metadata_to_dynamodb,
    rate_limit
)


logger = logging.getLogger(__name__)


class AWSDocsCrawler:
    """
    AWS公式ドキュメントをクロールし、変更があれば保存するクローラー
    """
    
    def __init__(self, service_paths: List[str] = None):
        """
        初期化
        
        Args:
            service_paths: クロールするAWSサービスのパスリスト。指定しない場合はデフォルトリスト。
        """
        self.service_paths = service_paths or AWS_SERVICES_PATHS
        self.base_url = AWS_DOCS_BASE_URL
        self.visited_urls = set()
        self.session = requests.Session()
        # ユーザーエージェント設定
        self.session.headers.update({
            'User-Agent': USER_AGENT
        })
        setup_logging()
    
    @rate_limit(min_interval=1.0)
    def fetch_page(self, url: str) -> Optional[str]:
        """
        URLからページコンテンツを取得
        
        Args:
            url: 取得するURL
            
        Returns:
            ページのHTMLコンテンツ、失敗した場合はNone
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"ページ取得エラー {url}: {e}")
            return None
    
    def process_page(self, url: str) -> Tuple[Optional[PageContent], bool]:
        """
        ページを処理し、必要に応じて保存
        
        Args:
            url: 処理するページのURL
            
        Returns:
            (ページコンテンツ, 変更があったかどうか)のタプル
        """
        # ページコンテンツを取得
        html_content = self.fetch_page(url)
        if not html_content:
            return None, False
        
        # ページのタイトルを取得
        title = extract_page_title(html_content)
        
        # 現在のタイムスタンプ（ログ・記録用）
        current_time = datetime.now()
        
        # ページコンテンツオブジェクトを作成
        page_content = PageContent(
            url=url,
            html_content=html_content,
            title=title,
            timestamp=current_time  # 処理時刻を記録
        )
        
        # 既存のメタデータを取得
        existing_metadata = get_page_metadata_from_dynamodb(url)
        
        # 変更があるかチェック - コンテンツハッシュで比較
        is_changed = True
        if existing_metadata:
            is_changed = existing_metadata.current_content_hash != page_content.content_hash
        
        # 変更がある場合、または初めて見るページの場合のみ保存する
        if is_changed:
            logger.info(f"変更検出または新規ページ: {url}")
            
            # S3にコンテンツを保存
            version_id = save_content_to_s3(page_content)
            if not version_id:
                logger.error(f"S3保存失敗: {url}")
                return page_content, False
            
            # 更新のタイムスタンプは変更が確認された時点のもの
            update_time = current_time
            
            # バージョン情報を作成
            page_version = PageVersion(
                url=url,
                version_id=version_id,
                timestamp=update_time,
                content_hash=page_content.content_hash,
                title=title
            )
            
            # メタデータを更新
            if existing_metadata:
                existing_metadata.add_version(page_version)
                metadata = existing_metadata
            else:
                # 新規ページの場合
                metadata = PageMetadata(
                    url=url,
                    title=title,
                    first_seen=update_time,
                    last_updated=update_time,
                    current_content_hash=page_content.content_hash,
                    versions=[page_version.to_dict()]
                )
            
            # DynamoDBにメタデータを保存
            if save_page_metadata_to_dynamodb(metadata):
                logger.info(f"メタデータ保存成功: {url}")
            else:
                logger.error(f"メタデータ保存失敗: {url}")
        else:
            logger.info(f"変更なし: {url}")
        
        return page_content, is_changed
    
    def crawl(self, max_pages: int = 100, max_depth: int = 3) -> Dict[str, int]:
        """
        AWSドキュメントのクロールを実行
        
        Args:
            max_pages: クロールする最大ページ数
            max_depth: クロールする最大深度
            
        Returns:
            統計情報を含むディクショナリ
        """
        start_time = time.time()
        queue = [(f"{self.base_url}{path}", 0) for path in self.service_paths]
        self.visited_urls.clear()
        
        total_pages = 0
        changed_pages = 0
        
        while queue and total_pages < max_pages:
            # キューから次のURLと深さを取得
            url, depth = queue.pop(0)
            
            # 既に訪問済みのURLはスキップ
            if url in self.visited_urls:
                continue
            
            # URLを訪問済みとしてマーク
            self.visited_urls.add(url)
            
            logger.info(f"クロール中: {url} (深さ {depth})")
            
            # ページを処理
            page_content, is_changed = self.process_page(url)
            total_pages += 1
            
            if is_changed and page_content:
                changed_pages += 1
            
            # 最大深度に達していなければ、リンクを抽出してキューに追加
            if page_content and depth < max_depth:
                links = extract_links_from_page(page_content.html_content, self.base_url)
                
                # まだ訪問していないリンクをキューに追加
                for link in links:
                    if link not in self.visited_urls:
                        queue.append((link, depth + 1))
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 統計情報
        stats = {
            "total_pages": total_pages,
            "changed_pages": changed_pages,
            "duration_seconds": duration,
            "visited_urls": len(self.visited_urls)
        }
        
        logger.info(f"クロール完了。統計情報: {json.dumps(stats)}")
        return stats


def lambda_handler(event, context):
    """
    AWS Lambda用のハンドラー関数
    """
    logger.info("AWSドキュメントクローラーを開始")
    crawler = AWSDocsCrawler()
    stats = crawler.crawl()
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "クロール成功",
            "stats": stats
        })
    }


if __name__ == "__main__":
    setup_logging()
    crawler = AWSDocsCrawler()
    crawler.crawl()