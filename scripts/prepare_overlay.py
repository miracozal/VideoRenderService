#!/usr/bin/env python3
"""Prepare safe text assets and a branded FFmpeg filter graph."""

from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path


ASSETS = Path("assets")
FONT_REGULAR = os.environ.get(
    "FONT_REGULAR", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
)
FONT_BOLD = os.environ.get(
    "FONT_BOLD", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
)


THEMES = {
    "a101": ("A101", "E31E24", "FFFFFF"),
    "bim": ("BİM", "F2C300", "20252B"),
    "sok": ("ŞOK", "F5C400", "20252B"),
    "şok": ("ŞOK", "F5C400", "20252B"),
    "migros": ("MİGROS", "F58220", "FFFFFF"),
    "trendyol": ("TRENDYOL", "F27A1A", "FFFFFF"),
    "hepsiburada": ("HEPSİBURADA", "F56600", "FFFFFF"),
    "gratis": ("GRATİS", "E5007D", "FFFFFF"),
}


def clean(value: str, limit: int) -> str:
    return " ".join(value.split())[:limit]


def write_text(name: str, value: str) -> None:
    (ASSETS / name).write_text(value, encoding="utf-8")


def parse_discount_percent(value: str) -> int | None:
    match = re.search(r"\d+(?:[.,]\d+)?", value)
    if not match:
        return None

    return max(0, min(100, round(float(match.group(0).replace(",", ".")))))


def discount_palette(percentage: int | None) -> tuple[str, str, str]:
    if percentage is None or percentage < 25:
        return "B9E2F2", "173B4D", "315D72"
    if percentage < 50:
        return "98D3B1", "123B2A", "2C5C47"
    if percentage <= 75:
        return "F2D66B", "453A0C", "6A5915"
    return "E76F73", "FFFFFF", "FFE2E3"


def text_filter(
    file_name: str,
    *,
    color: str,
    size: int,
    x: str,
    y: int,
    bold: bool = False,
    line_spacing: int = 8,
) -> str:
    font = FONT_BOLD if bold else FONT_REGULAR
    return (
        f"drawtext=fontfile={font}:textfile=assets/{file_name}:"
        f"expansion=none:fontcolor={color}:fontsize={size}:"
        f"line_spacing={line_spacing}:x={x}:y={y}"
    )


def build_filter(
    accent: str,
    market_text: str,
    badge_background: str,
    badge_text: str,
    badge_muted_text: str,
    has_discount: bool,
    fade_out_start: float,
) -> str:
    chains = [
        "[0:v]scale=1200:2134:force_original_aspect_ratio=increase:flags=lanczos,"
        "crop=1080:1920,gblur=sigma=52,eq=brightness=0.16:saturation=0.34[background]",
        "[background]"
        "drawbox=x=0:y=0:w=1080:h=1920:color=0xF2F0EC@0.91:t=fill,"
        f"drawbox=x=0:y=0:w=1080:h=18:color=0x{accent}@1:t=fill,"
        "drawbox=x=82:y=390:w=932:h=862:color=0x20252B@0.11:t=fill,"
        "drawbox=x=66:y=374:w=932:h=862:color=white@1:t=fill,"
        f"drawbox=x=66:y=374:w=932:h=10:color=0x{accent}@1:t=fill[base]",
        "[0:v]scale=820:790:force_original_aspect_ratio=decrease:flags=lanczos,"
        "unsharp=5:5:0.48:5:5:0.0,pad=860:820:(ow-iw)/2:(oh-ih)/2:color=white[product]",
    ]

    video_filters = [
        "[base][product]overlay=(W-w)/2:405:shortest=1",
        text_filter(
            "brand.txt", color="0x20252B", size=31, x="70", y=72, bold=True
        ),
        text_filter(
            "eyebrow.txt", color="0x65707C", size=27, x="70", y=130, bold=True
        ),
        f"drawbox=x=70:y=196:w=360:h=82:color=0x{accent}@1:t=fill",
        text_filter(
            "market.txt", color=f"0x{market_text}", size=38, x="92", y=216, bold=True
        ),
        text_filter(
            "product_name.txt",
            color="0x20252B",
            size=47,
            x="70",
            y=1294,
            bold=True,
            line_spacing=12,
        ),
        text_filter(
            "quantity.txt", color="0x68727D", size=29, x="70", y=1424
        ),
    ]

    if has_discount:
        video_filters.extend(
            [
                text_filter(
                    "original_label.txt",
                    color="0x68727D",
                    size=24,
                    x="70",
                    y=1481,
                    bold=True,
                ),
                text_filter(
                    "original_price.txt",
                    color="0x35404A",
                    size=34,
                    x="238",
                    y=1482,
                    bold=True,
                ),
                "drawbox=x=78:y=1542:w=932:h=190:color=0x20252B@0.10:t=fill",
                "drawbox=x=70:y=1534:w=940:h=190:color=white@1:t=fill",
                f"drawbox=x=70:y=1534:w=10:h=190:color=0x{accent}@1:t=fill",
                text_filter(
                    "current_label.txt",
                    color="0x68727D",
                    size=23,
                    x="98",
                    y=1560,
                    bold=True,
                ),
                text_filter(
                    "current_price.txt",
                    color="0x20252B",
                    size=68,
                    x="96",
                    y=1600,
                    bold=True,
                ),
                f"drawbox=x=742:y=1556:w=236:h=146:color=0x{badge_background}@1:t=fill",
                text_filter(
                    "discount_percent.txt",
                    color=f"0x{badge_text}",
                    size=52,
                    x="(1720-text_w)/2",
                    y=1572,
                    bold=True,
                ),
                text_filter(
                    "discount_label.txt",
                    color=f"0x{badge_muted_text}",
                    size=21,
                    x="(1720-text_w)/2",
                    y=1648,
                    bold=True,
                ),
                f"drawbox=x=70:y=1747:w=9:h=48:color=0x{badge_background}@1:t=fill",
                text_filter(
                    "savings.txt",
                    color="0x35404A",
                    size=28,
                    x="98",
                    y=1752,
                    bold=True,
                ),
            ]
        )
    else:
        video_filters.extend(
            [
                "drawbox=x=78:y=1526:w=932:h=210:color=0x20252B@0.10:t=fill",
                "drawbox=x=70:y=1518:w=940:h=210:color=white@1:t=fill",
                f"drawbox=x=70:y=1518:w=10:h=210:color=0x{accent}@1:t=fill",
                text_filter(
                    "current_label.txt",
                    color="0x68727D",
                    size=26,
                    x="102",
                    y=1551,
                    bold=True,
                ),
                text_filter(
                    "current_price.txt",
                    color="0x20252B",
                    size=78,
                    x="98",
                    y=1600,
                    bold=True,
                ),
            ]
        )

    video_filters.extend(
        [
            text_filter(
                "disclaimer.txt", color="0x707A84", size=23, x="70", y=1812
            ),
            text_filter(
                "website.txt", color="0x20252B", size=30, x="70", y=1855, bold=True
            ),
            f"fade=t=in:st=0:d=0.38,fade=t=out:st={fade_out_start:.2f}:d=0.55,format=yuv420p[v]",
        ]
    )

    audio_filter = (
        f"[1:a]afade=t=in:st=0:d=0.25,"
        f"afade=t=out:st={fade_out_start:.2f}:d=0.55[a]"
    )
    return ";".join([*chains, ",".join(video_filters), audio_filter])


def main() -> None:
    ASSETS.mkdir(exist_ok=True)

    market = clean(os.environ.get("MARKET", ""), 30).lower()
    product = clean(os.environ.get("PRODUCT_NAME", ""), 150)
    quantity = clean(os.environ.get("QUANTITY", ""), 50)
    current_price = clean(
        os.environ.get("CURRENT_PRICE") or os.environ.get("PRICE", ""), 30
    )
    original_price = clean(os.environ.get("ORIGINAL_PRICE", ""), 30)
    discount_amount = clean(os.environ.get("DISCOUNT_AMOUNT", ""), 30)
    discount_percent = clean(os.environ.get("DISCOUNT_PERCENT", ""), 10)
    duration = int(os.environ.get("DURATION_SECONDS", "10"))

    market_label, accent, market_text = THEMES.get(
        market, ("MARKET FIRSATI", "20C997", "FFFFFF")
    )
    badge_background, badge_text, badge_muted_text = discount_palette(
        parse_discount_percent(discount_percent)
    )
    has_discount = bool(
        original_price and discount_amount and discount_percent and current_price
    )

    wrapped_product = textwrap.TextWrapper(
        width=31,
        max_lines=2,
        placeholder="…",
        break_long_words=False,
        break_on_hyphens=False,
    ).fill(product or "Öne çıkan kampanyalı ürün")

    write_text("brand.txt", "İNDİRİM SERVİSİ")
    write_text("eyebrow.txt", "GÜNÜN FIRSATI")
    write_text("market.txt", market_label)
    write_text("product_name.txt", wrapped_product)
    write_text("quantity.txt", quantity)
    write_text("original_label.txt", "Normal fiyat")
    write_text("original_price.txt", original_price)
    write_text(
        "current_label.txt", "İndirimli fiyat" if has_discount else "Güncel fiyat"
    )
    write_text("current_price.txt", current_price or "Fiyatı inceleyin")
    write_text("discount_percent.txt", discount_percent)
    write_text("discount_label.txt", "İNDİRİM")
    write_text("savings.txt", f"{discount_amount} tasarruf")
    write_text(
        "disclaimer.txt", "Kampanya ve stok bilgileri mağazaya göre değişebilir."
    )
    write_text("website.txt", "indirimservisi.com")

    fade_out_start = max(0.4, duration - 0.6)
    (ASSETS / "filter_complex.txt").write_text(
        build_filter(
            accent,
            market_text,
            badge_background,
            badge_text,
            badge_muted_text,
            has_discount,
            fade_out_start,
        ),
        encoding="utf-8",
    )

    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a", encoding="utf-8") as env_file:
            env_file.write(f"ACCENT_COLOR=0x{accent}\n")
            env_file.write(f"HAS_DISCOUNT={'true' if has_discount else 'false'}\n")


if __name__ == "__main__":
    main()
