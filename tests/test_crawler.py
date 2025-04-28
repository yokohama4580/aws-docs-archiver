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


class TestAWSDocsCrawler(unittest.TestCase):
    """
    AWSドキュメントクローラーのテストクラス
    """
    
    def setUp(self):
        """
        テスト前の準備
        """
        self.crawler = AWSDocsCrawler(service_paths=["/ja_jp/test/"])
        
        # テスト用のHTMLコンテンツ
        self.test_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>AWS Test Document</title>
        </head>
        <body>
            <h1>AWS Test Document</h1>
            <p>This is a test document.</p>
            <a href="/ja_jp/test/page1.html">Link 1</a>
            <a href="/ja_jp/test/page2.html">Link 2</a>
            <a href="https://docs.aws.amazon.com/ja_jp/test/page3.html">Link 3</a>
            <a href="https://example.com">External Link</a>
        </body>
        </html>
        """
    
    @patch('crawler.aws_docs_crawler.requests.Session')
    def test_fetch_page(self, mock_session):
        """
        fetch_pageメソッドのテスト
        """
        # モックの設定
        mock_response = MagicMock()
        mock_response.text = self.test_html
        mock_response.raise_for_status.return_value = None
        
        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        # クローラーのセッションを設定
        self.crawler.session = mock_session_instance
        
        # テスト対象メソッドを実行
        result = self.crawler.fetch_page("https://docs.aws.amazon.com/ja_jp/test/")
        
        # アサーション
        self.assertEqual(result, self.test_html)
        mock_session_instance.get.assert_called_once_with(
            "https://docs.aws.amazon.com/ja_jp/test/",
            timeout=30
        )
    
    @patch('crawler.aws_docs_crawler.extract_links_from_page')
    @patch('crawler.aws_docs_crawler.AWSDocsCrawler.process_page')
    @patch('crawler.aws_docs_crawler.AWSDocsCrawler.fetch_page')
    def test_crawl(self, mock_fetch_page, mock_process_page, mock_extract_links):
        """
        crawlメソッドのテスト
        """
        # モックの設定
        mock_fetch_page.return_value = self.test_html
        
        page_content = PageContent(
            url="https://docs.aws.amazon.com/ja_jp/test/",
            html_content=self.test_html,
            title="AWS Test Document",
            timestamp=datetime.now()
        )
        
        mock_process_page.return_value = (page_content, True)
        mock_extract_links.return_value = [
            "https://docs.aws.amazon.com/ja_jp/test/page1.html",
            "https://docs.aws.amazon.com/ja_jp/test/page2.html"
        ]
        
        # テスト対象メソッドを実行（最大1ページ、深さ0でテスト）
        result = self.crawler.crawl(max_pages=1, max_depth=0)
        
        # アサーション
        self.assertEqual(result["total_pages"], 1)
        self.assertEqual(result["changed_pages"], 1)
        mock_process_page.assert_called_once()


if __name__ == '__main__':
    unittest.main()