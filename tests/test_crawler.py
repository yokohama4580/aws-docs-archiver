"""
AWSドキュメントクローラーのテスト
"""
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import hashlib

from crawler.aws_docs_crawler import AWSDocsCrawler
from crawler.models import PageContent, PageMetadata, PageVersion
from crawler.utils import extract_links_from_page, extract_page_title


class TestAWSDocsCrawler(unittest.TestCase):
    """
    AWSドキュメントクローラーのテストクラス
    """
    
    def setUp(self):
        """
        テスト前の準備
        """
        # 実際のEC2ドキュメントへのパスを指定
        self.test_url = "https://docs.aws.amazon.com/ja_jp/AWSEC2/latest/UserGuide/concepts.html"
        self.crawler = AWSDocsCrawler(service_paths=["/ja_jp/AWSEC2/latest/UserGuide/concepts.html"])
    
    def test_fetch_page(self):
        """
        fetch_pageメソッドのテスト - 実際のAWSドキュメントページを取得
        """
        # 実際のページを取得
        html_content = self.crawler.fetch_page(self.test_url)
        
        # アサーション
        self.assertIsNotNone(html_content)
        self.assertIsInstance(html_content, str)
        self.assertGreater(len(html_content), 1000)  # ページには十分な内容があるはず
        
        # タイトルの検証
        title = extract_page_title(html_content)
        self.assertIsNotNone(title)
        self.assertGreater(len(title), 5)  # タイトルは一定以上の長さがあるはず
    
    def test_extract_links(self):
        """
        リンク抽出機能のテスト - 実際のページからリンクを抽出
        """
        # 実際のページを取得
        html_content = self.crawler.fetch_page(self.test_url)
        
        # リンクを抽出
        links = extract_links_from_page(html_content, "https://docs.aws.amazon.com")
        
        # アサーション
        self.assertIsNotNone(links)
        self.assertIsInstance(links, list)
        self.assertGreater(len(links), 3)  # いくつかのリンクがあるはず
        
        # すべてのリンクがAWS Docsドメイン内であることを確認
        for link in links:
            self.assertTrue(link.startswith("https://docs.aws.amazon.com"))
    
    @patch('crawler.aws_docs_crawler.get_page_metadata_from_dynamodb')
    @patch('crawler.aws_docs_crawler.save_content_to_s3')
    @patch('crawler.aws_docs_crawler.save_page_metadata_to_dynamodb')
    def test_crawl_real_page(self, mock_save_metadata, mock_save_content, mock_get_metadata):
        """
        実際のEC2ドキュメントページをクロールするテスト
        モックを使用してAWSサービス（DynamoDBとS3）へのアクセスをシミュレート
        """
        # モックの設定
        mock_get_metadata.return_value = None  # メタデータが存在しない状態をシミュレート
        mock_save_content.return_value = "test-version-id-123"  # S3保存が成功したことをシミュレート
        mock_save_metadata.return_value = True  # DynamoDBへの保存が成功したことをシミュレート
        
        # テスト対象メソッドを実行（最大1ページ、深さ0でテスト）
        result = self.crawler.crawl(max_pages=1, max_depth=0)
        
        # アサーション
        self.assertIsNotNone(result)
        self.assertEqual(result["total_pages"], 1)
        self.assertEqual(result["changed_pages"], 1)  # 新規ページなので変更があったとみなされる
        self.assertIn("duration_seconds", result)
        self.assertGreater(result["duration_seconds"], 0)
        
        # モックが適切に呼ばれたかを確認
        mock_get_metadata.assert_called_once_with(self.test_url)
        mock_save_content.assert_called_once()
        mock_save_metadata.assert_called_once()


if __name__ == '__main__':
    unittest.main()