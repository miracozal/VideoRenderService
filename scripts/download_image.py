import ipaddress
import socket
import sys
import urllib.parse
import urllib.request


MAX_BYTES = 10 * 1024 * 1024
MAX_REDIRECTS = 3


def validate_public_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Image URL must use HTTP or HTTPS.")

    for result in socket.getaddrinfo(parsed.hostname, parsed.port):
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            raise ValueError("Image URL resolves to a private or reserved address.")


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self) -> None:
        self.redirects = 0

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        self.redirects += 1
        if self.redirects > MAX_REDIRECTS:
            raise ValueError("Image URL contains too many redirects.")

        validate_public_url(new_url)
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


def download(url: str, output_path: str) -> None:
    validate_public_url(url)
    opener = urllib.request.build_opener(SafeRedirectHandler())
    request = urllib.request.Request(url, headers={"User-Agent": "VideoRenderService/1.0"})

    with opener.open(request, timeout=20) as response:
        content_type = response.headers.get_content_type()
        if not content_type.startswith("image/"):
            raise ValueError("URL did not return an image.")

        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_BYTES:
            raise ValueError("Image is larger than 10 MB.")

        total = 0
        with open(output_path, "wb") as output:
            while chunk := response.read(64 * 1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("Image is larger than 10 MB.")
                output.write(chunk)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: download_image.py <url> <output_path>")

    download(sys.argv[1], sys.argv[2])
