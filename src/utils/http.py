"""
HTTP 客户端封装
- User-Agent 轮换
- SSL 兼容（部分政府网站证书老旧）
- 自动重试 + 编码检测
"""

import random
import time
import ssl
import httpx

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 2
RETRY_DELAY = 3


class HttpClient:
    """带重试和 UA 轮换的 HTTP 客户端"""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, verify_ssl: bool = True):
        self.timeout = timeout
        self.verify_ssl = verify_ssl

    def _get_client(self) -> httpx.Client:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        verify = self.verify_ssl
        return httpx.Client(
            headers=headers,
            timeout=self.timeout,
            follow_redirects=True,
            http2=False,
            verify=verify,
        )

    def get(self, url: str, encoding: str | None = None) -> str:
        """GET 请求，自动重试"""
        client = self._get_client()
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            # 第二次重试尝试降级 SSL
            if attempt == 2 and self.verify_ssl:
                client = httpx.Client(
                    headers=client.headers,
                    timeout=self.timeout,
                    follow_redirects=True,
                    http2=False,
                    verify=False,
                )

            try:
                resp = client.get(url)
                resp.raise_for_status()
                if encoding:
                    resp.encoding = encoding
                elif resp.encoding is None or resp.encoding == "ISO-8859-1":
                    resp.encoding = self._detect_encoding(resp.content)
                return resp.text
            except httpx.HTTPStatusError as e:
                if e.response.status_code in [403, 404, 410]:
                    raise RuntimeError(f"HTTP {e.response.status_code}: {url}")
                last_error = e
            except (httpx.RequestError, httpx.TimeoutException, ssl.SSLError) as e:
                last_error = e

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        raise RuntimeError(f"HTTP GET failed after {MAX_RETRIES} attempts: {url} — {last_error}")

    @staticmethod
    def _detect_encoding(content: bytes) -> str:
        head = content[:1024]
        for enc in [b"gbk", b"gb2312", b"gb18030", b"utf-8", b"utf8"]:
            if enc in head.lower():
                return enc.decode("ascii")
        return "utf-8"
