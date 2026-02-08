
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

        image1 = changeImageSize(1280, 720, youtube).convert("RGBA")

        gradient = Image.new("RGBA", image1.size, (0, 0, 0, 255))
        enhancer = ImageEnhance.Brightness(image1.filter(ImageFilter.GaussianBlur(5)))
        blurred = enhancer.enhance(0.3)
        background = Image.alpha_composite(gradient, blurred)

        draw = ImageDraw.Draw(background)
        font_path_main = "ShrutixMusic/assets/font3.ttf"
        font_path_small = "ShrutixMusic/assets/font2.ttf"

        player = Image.open("ShrutixMusic/assets/nand.png").convert("RGBA").resize((1280, 720))
        overlay_box = get_overlay_content_box(player)
        content_x1, content_y1, content_x2, content_y2 = overlay_box
        background.paste(player, (0, 0), player)

        box_w = content_x2 - content_x1
        box_h = content_y2 - content_y1

        thumb_size = int(box_h * 0.66)
        thumb_margin_x = int(box_w * 0.05)
        thumb_x = content_x1 + thumb_margin_x
        thumb_y = content_y1 + (box_h - thumb_size) // 2

        mask = Image.new("L", (thumb_size, thumb_size), 0)
        draw_mask = ImageDraw.Draw(mask)
        radius = int(thumb_size * 0.25)
        draw_mask.rounded_rectangle([(0, 0), (thumb_size, thumb_size)], radius=radius, fill=255)

        thumb_square = youtube.resize((thumb_size, thumb_size))
        thumb_square.putalpha(mask)
        background.paste(thumb_square, (thumb_x, thumb_y), thumb_square)

        text_x = thumb_x + thumb_size + int(box_w * 0.05)
        max_text_width = content_x2 - text_x - int(box_w * 0.05)

        title_y = content_y1 + int(box_h * 0.18)
        info_y = title_y + int(box_h * 0.22)
        time_y = content_y2 - int(box_h * 0.24)

        def truncate_text(text, max_chars=30):
            return (text[: max_chars - 3] + "...") if len(text) > max_chars else text

        short_title = truncate_text(title, max_chars=40)
        short_channel = truncate_text(channel, max_chars=28)

        title_font = fit_text(draw, short_title, max_text_width, font_path_main, 48, 26)
        draw.text((text_x, title_y), short_title, (255, 255, 255), font=title_font)

        info_text = f"{short_channel} • {views}"
        info_font = ImageFont.truetype(font_path_small, 26)
        draw.text((text_x, info_y), info_text, (215, 215, 215), font=info_font)

        time_font = ImageFont.truetype(font_path_small, 28)
        duration_text = duration if ":" in duration else f"00:{duration.zfill(2)}"
        time_display = f"00:30 / {duration_text}"
        draw.text((text_x, time_y), time_display, (215, 215, 215), font=time_font)

        rocky_font = ImageFont.truetype(font_path_main, 32)
        rocky_text = "Rocky Music"
        rocky_w, rocky_h = draw.textsize(rocky_text, font=rocky_font)
        rocky_x = content_x1 + int(box_w * 0.04)
        rocky_y = content_y1 + int(box_h * 0.08) - rocky_h // 2
        draw.text((rocky_x, rocky_y), rocky_text, (255, 255, 255), font=rocky_font)

        watermark_font = ImageFont.truetype(font_path_small, 24)
        watermark_text = "@mrrockytg"
        text_size = draw.textsize(watermark_text, font=watermark_font)
        x = background.width - text_size[0] - 25
        y = background.height - text_size[1] - 25
        for dx in (-1, 1):
            for dy in (-1, 1):
                draw.text((x + dx, y + dy), watermark_text, font=watermark_font, fill=(0, 0, 0, 180))
        draw.text((x, y), watermark_text, font=watermark_font, fill=(255, 255, 255, 240))

        try:
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
        except:
            pass

        tpath = f"cache/{videoid}.png"
        background.save(tpath)
        return tpath

    except Exception as e:
        print(f"[get_thumb Error] {e}")
        traceback.print_exc()
        return None
