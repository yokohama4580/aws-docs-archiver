"""
データモデル定義
"""
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional


@dataclass
class PageContent:
    """
    クロールしたページのコンテンツを表すクラス
    """
    url: str
    html_content: str
    title: str
    timestamp: datetime
    content_hash: str = None

    def __post_init__(self):
        """
        コンテンツのハッシュを計算
        """
        if self.content_hash is None:
            self.content_hash = hashlib.sha256(
                self.html_content.encode('utf-8')
            ).hexdigest()
    
    def to_dict(self) -> Dict:
        """
        DynamoDBに保存するためにディクショナリに変換
        """
        return {
            'url': self.url,
            'title': self.title,
            'timestamp': self.timestamp.isoformat(),
            'content_hash': self.content_hash
        }
    
    @staticmethod
    def from_dict(data: Dict, html_content: str = None) -> 'PageContent':
        """
        ディクショナリからPageContentオブジェクトを作成
        """
        return PageContent(
            url=data['url'],
            html_content=html_content or '',
            title=data['title'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            content_hash=data.get('content_hash')
        )


@dataclass
class PageVersion:
    """
    ページの特定バージョンを表すクラス
    """
    url: str
    version_id: str  # S3のバージョンID
    timestamp: datetime
    content_hash: str
    title: str
    
    def to_dict(self) -> Dict:
        """
        DynamoDBに保存するためにディクショナリに変換
        """
        return {
            'url': self.url,
            'version_id': self.version_id,
            'timestamp': self.timestamp.isoformat(),
            'content_hash': self.content_hash,
            'title': self.title
        }


@dataclass
class PageMetadata:
    """
    ページのメタデータを表すクラス（DynamoDBに保存）
    """
    url: str
    title: str
    first_seen: datetime
    last_updated: datetime
    current_content_hash: str
    versions: List[Dict]  # PageVersionのディクショナリのリスト
    
    def to_dict(self) -> Dict:
        """
        DynamoDBに保存するためにディクショナリに変換
        """
        return {
            'url': self.url,
            'title': self.title,
            'first_seen': self.first_seen.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'current_content_hash': self.current_content_hash,
            'versions': self.versions
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'PageMetadata':
        """
        ディクショナリからPageMetadataオブジェクトを作成
        """
        return PageMetadata(
            url=data['url'],
            title=data['title'],
            first_seen=datetime.fromisoformat(data['first_seen']),
            last_updated=datetime.fromisoformat(data['last_updated']),
            current_content_hash=data['current_content_hash'],
            versions=data.get('versions', [])
        )
    
    def add_version(self, version: PageVersion):
        """
        新しいバージョンを追加
        """
        self.versions.append(version.to_dict())
        self.last_updated = version.timestamp
        self.current_content_hash = version.content_hash