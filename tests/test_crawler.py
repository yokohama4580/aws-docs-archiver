"""
AWSドキュメントクローラーのテスト
"""
import os
import unittest
from unittest.mock import patch, MagicMock, call
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
        
        # モックテスト用のHTMLコンテンツ
        self.mock_html_v1 = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>AWS Mock Document</title>
        </head>
        <body>
            <h1>AWS Mock Document</h1>
            <p>Version 1 of the document.</p>
            <a href="/ja_jp/test/page1.html">Link 1</a>
        </body>
        </html>
        """
        
        # 更新されたコンテンツ（Version 2）
        self.mock_html_v2 = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>AWS Mock Document</title>
        </head>
        <body>
            <h1>AWS Mock Document</h1>
            <p>Version 2 of the document - content updated.</p>
            <a href="/ja_jp/test/page1.html">Link 1</a>
            <a href="/ja_jp/test/page2.html">New Link</a>
        </body>
        </html>
        """
        
        # 変更がないコンテンツ（Version 1と同じコンテンツハッシュ）
        self.mock_html_unchanged = self.mock_html_v1
    
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
    
    @patch('crawler.aws_docs_crawler.AWSDocsCrawler.fetch_page')
    @patch('crawler.aws_docs_crawler.get_page_metadata_from_dynamodb')
    @patch('crawler.aws_docs_crawler.save_content_to_s3')
    @patch('crawler.aws_docs_crawler.save_page_metadata_to_dynamodb')
    def test_page_content_changed_detection(self, mock_save_metadata, mock_save_content, 
                                        mock_get_metadata, mock_fetch_page):
        """
        コンテンツ変更検出テスト - モックページとメタデータを使用して、
        ページの内容が更新された場合に正しく変更を検出して保存するかをテスト
        """
        # モックURL
        mock_url = "https://docs.aws.amazon.com/ja_jp/mock/page.html"
        test_crawler = AWSDocsCrawler(service_paths=["/ja_jp/mock/page.html"])
        
        # テスト用のタイムスタンプ
        first_time = datetime(2025, 4, 1, 10, 0, 0)
        second_time = datetime(2025, 4, 2, 10, 0, 0)
        
        # 1回目のクロール - 初回アクセス（メタデータなし）
        mock_fetch_page.return_value = self.mock_html_v1
        
        # 初回はメタデータがない
        mock_get_metadata.return_value = None
        mock_save_content.return_value = "version-id-1"
        mock_save_metadata.return_value = True
        
        # テストの実行（最大1ページ、深さ0）
        with patch('crawler.aws_docs_crawler.datetime') as mock_datetime:
            mock_datetime.now.return_value = first_time
            result1 = test_crawler.crawl(max_pages=1, max_depth=0)
        
        # 初回クロールの検証
        self.assertEqual(result1["changed_pages"], 1)
        mock_save_content.assert_called_once()
        mock_save_metadata.assert_called_once()
        
        # 保存されたオブジェクトを取得
        saved_metadata_args = mock_save_metadata.call_args[0][0]
        self.assertEqual(saved_metadata_args.current_content_hash, 
                        PageContent(url=mock_url, html_content=self.mock_html_v1, 
                                    title="AWS Mock Document", timestamp=first_time).content_hash)
        
        # モックをリセット
        mock_fetch_page.reset_mock()
        mock_get_metadata.reset_mock()
        mock_save_content.reset_mock()
        mock_save_metadata.reset_mock()
        
        # 2回目のクロール - 更新されたコンテンツ
        mock_fetch_page.return_value = self.mock_html_v2
        
        # 2回目は既存のメタデータがある状態
        existing_metadata = PageMetadata(
            url=mock_url,
            title="AWS Mock Document",
            first_seen=first_time,
            last_updated=first_time,
            current_content_hash=PageContent(url=mock_url, html_content=self.mock_html_v1, 
                                            title="AWS Mock Document", timestamp=first_time).content_hash,
            versions=[
                PageVersion(
                    url=mock_url,
                    version_id="version-id-1",
                    timestamp=first_time,
                    content_hash=PageContent(url=mock_url, html_content=self.mock_html_v1, 
                                            title="AWS Mock Document", timestamp=first_time).content_hash,
                    title="AWS Mock Document"
                ).to_dict()
            ]
        )
        mock_get_metadata.return_value = existing_metadata
        mock_save_content.return_value = "version-id-2"
        mock_save_metadata.return_value = True
        
        # テストの実行
        with patch('crawler.aws_docs_crawler.datetime') as mock_datetime:
            mock_datetime.now.return_value = second_time
            result2 = test_crawler.crawl(max_pages=1, max_depth=0)
        
        # 変更があるので保存される
        self.assertEqual(result2["changed_pages"], 1)
        mock_save_content.assert_called_once()
        mock_save_metadata.assert_called_once()
        
        # 保存されるメタデータを検証
        saved_metadata_args = mock_save_metadata.call_args[0][0]
        self.assertEqual(saved_metadata_args.current_content_hash, 
                        PageContent(url=mock_url, html_content=self.mock_html_v2, 
                                    title="AWS Mock Document", timestamp=second_time).content_hash)
        self.assertEqual(len(saved_metadata_args.versions), 2)  # バージョン数が2になっている
    
    @patch('crawler.aws_docs_crawler.AWSDocsCrawler.fetch_page')
    @patch('crawler.aws_docs_crawler.get_page_metadata_from_dynamodb')
    @patch('crawler.aws_docs_crawler.save_content_to_s3')
    @patch('crawler.aws_docs_crawler.save_page_metadata_to_dynamodb')
    def test_no_changes_detected(self, mock_save_metadata, mock_save_content, 
                                mock_get_metadata, mock_fetch_page):
        """
        変更なしの検出テスト - ページ内容が変わっていない場合は保存されないことを検証
        """
        # モックURL
        mock_url = "https://docs.aws.amazon.com/ja_jp/mock/page.html"
        test_crawler = AWSDocsCrawler(service_paths=["/ja_jp/mock/page.html"])
        
        # テスト用のタイムスタンプ
        first_time = datetime(2025, 4, 1, 10, 0, 0)
        second_time = datetime(2025, 4, 2, 10, 0, 0)
        
        # 1回目のクロール（初回）
        mock_fetch_page.return_value = self.mock_html_v1
        mock_get_metadata.return_value = None
        mock_save_content.return_value = "version-id-1"
        mock_save_metadata.return_value = True
        
        # テストの実行
        with patch('crawler.aws_docs_crawler.datetime') as mock_datetime:
            mock_datetime.now.return_value = first_time
            result1 = test_crawler.crawl(max_pages=1, max_depth=0)
        
        # 初回は保存されている
        self.assertEqual(result1["changed_pages"], 1)
        
        # 最初に保存されたコンテンツのハッシュを計算
        content_hash_v1 = PageContent(url=mock_url, html_content=self.mock_html_v1, 
                                    title="AWS Mock Document", timestamp=first_time).content_hash
        
        # モックをリセット
        mock_fetch_page.reset_mock()
        mock_get_metadata.reset_mock()
        mock_save_content.reset_mock()
        mock_save_metadata.reset_mock()
        
        # 2回目のクロール - 変更なしのコンテンツ
        mock_fetch_page.return_value = self.mock_html_unchanged
        
        # 2回目は既存のメタデータがある状態
        existing_metadata = PageMetadata(
            url=mock_url,
            title="AWS Mock Document",
            first_seen=first_time,
            last_updated=first_time,
            current_content_hash=content_hash_v1,
            versions=[
                PageVersion(
                    url=mock_url,
                    version_id="version-id-1",
                    timestamp=first_time,
                    content_hash=content_hash_v1,
                    title="AWS Mock Document"
                ).to_dict()
            ]
        )
        mock_get_metadata.return_value = existing_metadata
        
        # テストの実行
        with patch('crawler.aws_docs_crawler.datetime') as mock_datetime:
            mock_datetime.now.return_value = second_time
            result2 = test_crawler.crawl(max_pages=1, max_depth=0)
        
        # 変更がないので保存されない
        self.assertEqual(result2["changed_pages"], 0)
        mock_save_content.assert_not_called()
        mock_save_metadata.assert_not_called()


if __name__ == '__main__':
    unittest.main()