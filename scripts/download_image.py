import ipaddress
import os
import random
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


MAX_BYTES = 10 * 1024 * 1024
MAX_REDIRECTS = 5
MAX_ATTEMPTS = 4

SCRIPT_VERSION = "2.0"

RETRYABLE_HTTP_CODES = {
    403,
    408,
    425,
    429,
    500,
    502,
    503,
    504,
}


class NonImageResponseError(ValueError):
    pass


def validate_public_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(
            "Image URL must use HTTP or HTTPS."
        )

    try:
        results = socket.getaddrinfo(
            parsed.hostname,
            parsed.port
        )
    except socket.gaierror as exc:
        raise ValueError(
            f"Image host could not be resolved: {parsed.hostname}"
        ) from exc

    if not results:
        raise ValueError(
            "Image URL host did not resolve to an address."
        )

    for result in results:
        address = ipaddress.ip_address(
            result[4][0]
        )

        if not address.is_global:
            raise ValueError(
                "Image URL resolves to a private or reserved address."
            )


class SafeRedirectHandler(
    urllib.request.HTTPRedirectHandler
):
    def __init__(self) -> None:
        super().__init__()
        self.redirects = 0

    def redirect_request(
        self,
        request,
        file_pointer,
        code,
        message,
        headers,
        new_url
    ):
        self.redirects += 1

        if self.redirects > MAX_REDIRECTS:
            raise ValueError(
                "Image URL contains too many redirects."
            )

        validate_public_url(new_url)

        return super().redirect_request(
            request,
            file_pointer,
            code,
            message,
            headers,
            new_url
        )


def looks_like_image(data: bytes) -> bool:

    # JPEG
    if data.startswith(b"\xff\xd8\xff"):
        return True

    # PNG
    if data.startswith(
        b"\x89PNG\r\n\x1a\n"
    ):
        return True

    # GIF
    if data.startswith(
        (b"GIF87a", b"GIF89a")
    ):
        return True

    # BMP
    if data.startswith(b"BM"):
        return True

    # TIFF
    if data.startswith(
        (b"II*\x00", b"MM\x00*")
    ):
        return True

    # WEBP
    if (
        len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12] == b"WEBP"
    ):
        return True

    # AVIF / HEIF
    if (
        len(data) >= 16
        and data[4:8] == b"ftyp"
    ):
        known_brands = (
            b"avif",
            b"avis",
            b"heic",
            b"heix",
            b"hevc",
            b"hevx",
            b"mif1",
            b"msf1",
        )

        brand = data[8:12]
        compatible = data[8:64]

        if (
            brand in known_brands
            or any(
                item in compatible
                for item in known_brands
            )
        ):
            return True

    return False


def safe_preview(data: bytes) -> str:
    text = data[:300].decode(
        "utf-8",
        errors="replace"
    )

    return " ".join(
        text.split()
    )[:240]


def build_request(
    url: str
) -> urllib.request.Request:

    parsed = urllib.parse.urlparse(url)

    referer = (
        f"{parsed.scheme}://{parsed.netloc}/"
    )

    return urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/151.0.0.0 "
                "Safari/537.36"
            ),

            "Accept": (
                "image/avif,"
                "image/webp,"
                "image/apng,"
                "image/*,"
                "*/*;q=0.8"
            ),

            "Accept-Language": (
                "tr-TR,tr;q=0.9,"
                "en-US;q=0.8,"
                "en;q=0.7"
            ),

            "Cache-Control":
                "no-cache",

            "Pragma":
                "no-cache",

            "Referer":
                referer,
        },
    )


def download_once(
    url: str,
    output_path: str
) -> None:

    validate_public_url(url)

    opener = urllib.request.build_opener(
        SafeRedirectHandler()
    )

    request = build_request(url)

    temp_path = (
        output_path + ".part"
    )

    try:

        with opener.open(
            request,
            timeout=30
        ) as response:

            status = getattr(
                response,
                "status",
                response.getcode()
            )

            final_url = response.geturl()

            content_type = (
                response.headers
                .get(
                    "Content-Type",
                    ""
                )
                .split(
                    ";",
                    1
                )[0]
                .strip()
                .lower()
            )

            content_length = (
                response.headers.get(
                    "Content-Length"
                )
            )

            print(
                "Image response: "
                f"status={status}, "
                f"content-type="
                f"{content_type or 'unknown'}, "
                f"content-length="
                f"{content_length or 'unknown'}, "
                f"final-url={final_url}"
            )

            if content_length:

                try:
                    declared_size = int(
                        content_length
                    )
                except ValueError:
                    declared_size = None

                if (
                    declared_size
                    is not None
                    and declared_size
                    > MAX_BYTES
                ):
                    raise ValueError(
                        "Image is larger than 10 MB."
                    )

            total = 0

            first_bytes = bytearray()

            with open(
                temp_path,
                "wb"
            ) as output:

                while True:

                    chunk = response.read(
                        64 * 1024
                    )

                    if not chunk:
                        break

                    if (
                        len(first_bytes)
                        < 1024
                    ):

                        needed = (
                            1024
                            - len(first_bytes)
                        )

                        first_bytes.extend(
                            chunk[:needed]
                        )

                    total += len(chunk)

                    if total > MAX_BYTES:
                        raise ValueError(
                            "Image is larger than 10 MB."
                        )

                    output.write(chunk)

            if total == 0:
                raise NonImageResponseError(
                    "Image URL returned an empty response."
                )

            body_start = bytes(
                first_bytes
            )

            #
            # Content-Type header'ına
            # tek başına güvenmiyoruz.
            #
            # Gerçek dosya JPEG/PNG/WEBP
            # vs. ise kabul ediyoruz.
            #
            if not looks_like_image(
                body_start
            ):

                preview = safe_preview(
                    body_start
                )

                raise NonImageResponseError(
                    "URL did not return a usable image. "
                    f"status={status}, "
                    f"content-type="
                    f"{content_type or 'unknown'}, "
                    f"final-url={final_url}, "
                    f"body-preview={preview!r}"
                )

            os.replace(
                temp_path,
                output_path
            )

            print(
                "Downloaded image successfully: "
                f"{total} bytes "
                f"-> {output_path}"
            )

    except Exception:

        try:
            os.remove(
                temp_path
            )
        except FileNotFoundError:
            pass

        raise


def download(
    url: str,
    output_path: str
) -> None:

    print(
        f"download_image.py "
        f"version {SCRIPT_VERSION}"
    )

    last_error = None

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1
    ):

        try:

            print(
                "Image download attempt "
                f"{attempt}/"
                f"{MAX_ATTEMPTS}"
            )

            download_once(
                url,
                output_path
            )

            return

        except urllib.error.HTTPError as exc:

            last_error = exc

            content_type = (
                "unknown"
            )

            if exc.headers:
                content_type = (
                    exc.headers.get(
                        "Content-Type",
                        "unknown"
                    )
                )

            preview = ""

            try:
                preview = safe_preview(
                    exc.read(300)
                )
            except Exception:
                pass

            print(
                "HTTP error while downloading image: "
                f"status={exc.code}, "
                f"content-type={content_type}, "
                f"body-preview={preview!r}",
                file=sys.stderr
            )

            if (
                exc.code
                not in
                RETRYABLE_HTTP_CODES
                or attempt
                == MAX_ATTEMPTS
            ):
                break

        except (
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            NonImageResponseError,
        ) as exc:

            last_error = exc

            print(
                "Temporary image "
                "download failure: "
                f"{exc}",
                file=sys.stderr
            )

            if (
                attempt
                == MAX_ATTEMPTS
            ):
                break

        delay = min(
            2 ** attempt,
            10
        )

        delay += random.uniform(
            0.0,
            0.75
        )

        print(
            "Retrying image download "
            f"in {delay:.1f}s...",
            file=sys.stderr
        )

        time.sleep(
            delay
        )

    raise RuntimeError(
        "Image download failed after "
        f"{MAX_ATTEMPTS} attempts. "
        f"Last error: {last_error}"
    ) from last_error


if __name__ == "__main__":

    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: "
            "download_image.py "
            "<url> "
            "<output_path>"
        )

    download(
        sys.argv[1],
        sys.argv[2]
    )
