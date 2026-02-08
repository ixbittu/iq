import os
import re
import random
import aiohttp
import aiofiles
import traceback

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from py_yt import VideosSearch
from config import YOUTUBE_IMG_URL


def changeImageSize(maxWidth, maxHeight, image):
    ratio = min(maxWidth / image.size[0], maxHeight / image.size[1])
    newSize = (int(image.size[0] * ratio), int(image.size[1] * ratio))
    return image.resize(newSize, Image.ANTIALIAS)


def truncate(text, max_chars=50):
    words = text.split()
    text1, text2 = "", ""
    for word in words:
        if len(text1 + " " + word) <= max_chars and not text2:
            text1 += " " + word
        else:
            text2 += " " + word
    return [text1.strip(), text2.strip()]


def fit_text(draw, text, max_width, font_path, start_size, min_size):
    size = start_size
    while size >= min_size:
        font = ImageFont.truetype(font_path, size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 1
    return ImageFont.truetype(font_path, min_size)


def get_overlay_content_box(overlay_img: Image.Image) -> tuple:
    alpha = overlay_img.split()[-1]
    threshold = 20
    binary = alpha.point(lambda p: 255 if p > threshold else 0)
    return binary.getbbox()


async def get_thumb(videoid: str):
    url = f"https://www.youtube.com/watch?v={videoid}"
    thumb_path = f"cache/thumb{videoid}.png"
    youtube = None
    try:
        try:
            results = VideosSearch(url, limit=1)
            result = (await results.next())["result"][0]
            title = re.sub(r"\W+", " ", result.get("title", "Unsupported Title")).title()
            duration = result.get("duration", "00:00")
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            views = result.get("viewCount", {}).get("short", "Unknown Views")
            channel = result.get("channel", {}).get("name", "Unknown Channel")
        except Exception:
            title = "Unknown Title"
            duration = "00:30"
            thumbnail = YOUTUBE_IMG_URL
            views = "Views"
            channel = "Youtube"

        try:
            if thumbnail.startswith("http"):
                async with aiohttp.ClientSession() as session:
                    async with session.get(thumbnail) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(thumb_path, mode="wb") as f:
                                await f.write(await resp.read())
                        else:
                            raise RuntimeError("Thumbnail download failed")
                youtube = Image.open(thumb_path)
            else:
                youtube = Image.open(thumbnail)
        except Exception:
            youtube = None

        if youtube is None:
            try:
                youtube = Image.open(YOUTUBE_IMG_URL)
            except Exception:
                youtube = Image.new("RGB", (1280, 720), (20, 20, 20))

        image1 = changeImageSize(1280, 720, youtube).convert("RGBA")
        gradient = Image.new("RGBA", image1.size, (0, 0, 0, 255))
        enhancer = ImageEnhance.Brightness(image1.filter(ImageFilter.GaussianBlur(5)))
        blurred = enhancer.enhance(0.3)
        background = Image.alpha_composite(gradient, blurred)

        draw = ImageDraw.Draw(background)
        font_path_main = "ShrutixMusic/assets/font3.ttf"
        font_path_small = "ShrutixMusic/assets/font2.ttf"

        player = Image.open("ShrutixMusic/assets/rocky.png").convert("RGBA").resize((1280, 720))
        overlay_box = get_overlay_content_box(player)
        content_x1, content_y1, content_x2, content_y2 = overlay_box
        background.paste(player, (0, 0), player)

        box_w = content_x2 - content_x1
        box_h = content_y2 - content_y1

        pad_x = int(box_w * 0.05)
        pad_y = int(box_h * 0.12)

        inner_x1 = content_x1 + pad_x
        inner_x2 = content_x2 - pad_x
        inner_y1 = content_y1 + pad_y
        inner_y2 = content_y2 - pad_y

        max_thumb_h = int((inner_y2 - inner_y1) * 0.75)
        max_thumb_w = int((inner_x2 - inner_x1) * 0.32)
        thumb_size = min(max_thumb_h, max_thumb_w)

        thumb_x = inner_x1 - int(box_w * 0.01)
        if thumb_x < content_x1 + 2:
            thumb_x = content_x1 + 2

        thumb_y = inner_y1 + ((inner_y2 - inner_y1) - thumb_size) // 2 + int(box_h * 0.015)
        if thumb_y < inner_y1:
            thumb_y = inner_y1
        if thumb_y + thumb_size > inner_y2:
            thumb_y = inner_y2 - thumb_size

        mask = Image.new("L", (thumb_size, thumb_size), 0)
        draw_mask = ImageDraw.Draw(mask)
        radius = int(thumb_size * 0.25)
        draw_mask.rounded_rectangle([(0, 0), (thumb_size, thumb_size)], radius=radius, fill=255)

        thumb_square = youtube.resize((thumb_size, thumb_size))
        thumb_square.putalpha(mask)
        background.paste(thumb_square, (thumb_x, thumb_y), thumb_square)

        thumb_color_raw = thumb_square.resize((1, 1)).getpixel((0, 0))
        if len(thumb_color_raw) >= 3:
            r, g, b = thumb_color_raw[:3]
        else:
            r, g, b = thumb_color_raw[0], thumb_color_raw[0], thumb_color_raw[0]
        thumb_color = (max(r, 80), max(g, 80), max(b, 80))

        text_x = thumb_x + thumb_size + int(box_w * 0.035)
        if text_x >= inner_x2 - 10:
            text_x = inner_x2 - 10

        max_text_width = inner_x2 - text_x

        def truncate_text(text, max_chars):
            text = text.strip()
            return (text[: max_chars - 3] + "...") if len(text) > max_chars else text

        short_title = truncate_text(title, max_chars=52)
        short_channel = truncate_text(channel, max_chars=30)

        title_y = inner_y1 + int((inner_y2 - inner_y1) * 0.12)

        title_font = fit_text(
            draw,
            short_title,
            max_text_width,
            font_path_main,
            start_size=46,
            min_size=24,
        )
        draw.text((text_x, title_y), short_title, (255, 255, 255), font=title_font)

        line_gap = 6
        info_y = title_y + title_font.size + line_gap
        info_text = f"{short_channel} • {views}"
        info_font = fit_text(
            draw,
            info_text,
            max_text_width,
            font_path_small,
            start_size=26,
            min_size=18,
        )
        if info_y < title_y + title_font.size + 2:
            info_y = title_y + title_font.size + 2
        draw.text((text_x, info_y), info_text, (215, 215, 215), font=info_font)

        time_font = ImageFont.truetype(font_path_small, 28)
        duration_text = duration if ":" in duration else f"00:{duration.zfill(2)}"

        def parse_hms(t: str) -> int:
            try:
                parts = [int(x) for x in t.split(":")]
                if len(parts) == 3:
                    h, m, s = parts
                elif len(parts) == 2:
                    h = 0
                    m, s = parts
                else:
                    h = 0
                    m = 0
                    s = parts[0]
                return h * 3600 + m * 60 + s
            except Exception:
                return 0

        total_seconds = parse_hms(duration_text)
        current_seconds = 30
        if total_seconds > 0:
            progress_ratio = max(0.0, min(1.0, current_seconds / total_seconds))
        else:
            progress_ratio = 0.2

        time_y = inner_y2 - time_font.size
        duration_display = f"00:30 / {duration_text}"
        draw.text((text_x, time_y), duration_display, (215, 215, 215), font=time_font)

        bar_margin_y = 12
        bar_available_y_top = info_y + info_font.size + bar_margin_y
        bar_available_y_bottom = time_y - bar_margin_y
        bar_height = max(4, int((inner_y2 - inner_y1) * 0.018))
        bar_height = min(bar_height, max(3, bar_available_y_bottom - bar_available_y_top))
        if bar_height < 3:
            bar_height = 3
        if bar_available_y_bottom - bar_available_y_top <= bar_height + 2:
            bar_available_y_top = info_y + info_font.size + 4
            bar_available_y_bottom = time_y - 4
        bar_y = bar_available_y_top + (bar_available_y_bottom - bar_available_y_top - bar_height) // 2
        bar_x1 = text_x
        bar_x2 = inner_x2
        bar_width = max(10, bar_x2 - bar_x1)

        track_radius = bar_height // 2
        track_bbox = [bar_x1, bar_y, bar_x1 + bar_width, bar_y + bar_height]
        draw.rounded_rectangle(track_bbox, radius=track_radius, fill=(255, 255, 255, 60))

        filled_width = int(bar_width * progress_ratio)
        if filled_width > 0:
            fill_bbox = [bar_x1, bar_y, bar_x1 + filled_width, bar_y + bar_height]
            draw.rounded_rectangle(fill_bbox, radius=track_radius, fill=thumb_color)

        rocky_font = ImageFont.truetype(font_path_main, 32)
        rocky_text = "Rocky Music"
        rocky_w, rocky_h = draw.textsize(rocky_text, font=rocky_font)
        rocky_x = content_x1 + int(box_w * 0.04)
        rocky_y = content_y1 + int(box_h * 0.07) - rocky_h // 2
        if rocky_y < content_y1:
            rocky_y = content_y1
        if rocky_y + rocky_h > content_y2:
            rocky_y = content_y2 - rocky_h
        draw.text((rocky_x, rocky_y), rocky_text, (255, 255, 255), font=rocky_font)

        watermark_font = ImageFont.truetype(font_path_small, 24)
        watermark_text = "@mrrockytg"
        wm_w, wm_h = draw.textsize(watermark_text, font=watermark_font)
        wx = background.width - wm_w - 25
        wy = background.height - wm_h - 25
        for dx in (-1, 1):
            for dy in (-1, 1):
                draw.text(
                    (wx + dx, wy + dy),
                    watermark_text,
                    font=watermark_font,
                    fill=(0, 0, 0, 180),
                )
        draw.text((wx, wy), watermark_text, font=watermark_font, fill=(255, 255, 255, 240))

        try:
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
        except Exception:
            pass

        tpath = f"cache/{videoid}.png"
        background.save(tpath)
        return tpath

    except Exception as e:
        print(f"[get_thumb Error] {e}")
        traceback.print_exc()
        return None
