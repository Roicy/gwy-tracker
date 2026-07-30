"""
HTTP 客户端封装
- User-Agent 轮换
- 自动重试
- 超时控制
"""

import random
import time
import httpx

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

DEFAULT_TIMEOUT = 30  # 秒
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒


class HttpClient:
    """带重试和 UA 轮换的 HTTP 客户端"""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        return httpx.Client(
            headers=headers,
            timeout=self.timeout,
            follow_redirects=True,
            http2=False,  # 政府网站大多不支持 HTTP/2
        )

    def get(self, url: str, encoding: str | None = None) -> str:
        """GET 请求，自动重试，返回解码后的文本"""
        client = self._get_client()
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = client.get(url)
                resp.raise_for_status()
                # 自动检测编码
                if encoding:
                    resp.encoding = encoding
                elif resp.encoding is None or resp.encoding == "ISO-8859-1":
                    # 政府网站常用 GBK/GB2312
                    resp.encoding = self._detect_encoding(resp.content)
                return resp.text
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in [403, 404, 503]:
                    break  # 不重试这些状态码
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)

        raise RuntimeError(f"HTTP GET failed after {MAX_RETRIES} attempts: {url} — {last_error}")

    @staticmethod
    def _detect_encoding(content: bytes) -> str:
        """从 HTML meta 标签检测编码，默认 utf-8"""
        # 快速检查前 1024 字节
        head = content[:1024]
        for enc in [b"gbk", b"gb2312", b"gb18030", b"utf-8", b"utf8"]:
            if enc in head.lower():
                return enc.decode("ascii")
        return "utf-8"

    def close(self):
        if self._client:
            self._client.close()
