import os
import re
import random
import aiohttp
import aiofiles
import traceback

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from youtubesearchpython.__future__ import VideosSearch


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
    """Returns bounding box (x1, y1, x2, y2) of the semi-transparent content box in overlay."""
    alpha = overlay_img.split()[-1]  # Extract alpha channel
    threshold = 20
    binary = alpha.point(lambda p: 255 if p > threshold else 0)
    return binary.getbbox()

async def get_thumb(videoid: str):
    url = f"https://www.youtube.com/watch?v={videoid}"
    try:
        results = VideosSearch(url, limit=1)
        result = (await results.next())["result"][0]

        title = re.sub(r"\W+", " ", result.get("title", "Unsupported Title")).title()
        duration = result.get("duration", "00:00")
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        views = result.get("viewCount", {}).get("short", "Unknown Views")
        channel = result.get("channel", {}).get("name", "Unknown Channel")

        # Download thumbnail
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    async with aiofiles.open(f"cache/thumb{videoid}.png", mode="wb") as f:
                        await f.write(await resp.read())

        youtube = Image.open(f"cache/thumb{videoid}.png")
        image1 = changeImageSize(1280, 720, youtube).convert("RGBA")

        # Create blurred background
        gradient = Image.new("RGBA", image1.size, (0, 0, 0, 255))
        enhancer = ImageEnhance.Brightness(image1.filter(ImageFilter.GaussianBlur(5)))
        blurred = enhancer.enhance(0.3)
        background = Image.alpha_composite(gradient, blurred)

        draw = ImageDraw.Draw(background)
        font_path = "ShrutixMusic/assets/font3.ttf"

        # Overlay and bounding box detection
        player = Image.open("ShrutixMusic/assets/nand.png").convert("RGBA").resize((1280, 720))
        overlay_box = get_overlay_content_box(player)  # (x1, y1, x2, y2)
        content_x1, content_y1, content_x2, content_y2 = overlay_box
        background.paste(player, (0, 0), player)

        # 🎯 Album Art Position (dynamically inside content box)
        thumb_size = int((content_y2 - content_y1) * 0.55)
        thumb_x = content_x1 + 76
        thumb_y = content_y1 + ((content_y2 - content_y1 - thumb_size) // 2) + 40

        mask = Image.new('L', (thumb_size, thumb_size), 0)
        draw_mask = ImageDraw.Draw(mask)
        radius = int(thumb_size * 0.25)
        draw_mask.rounded_rectangle([(0, 0), (thumb_size, thumb_size)], radius=radius, fill=255)

        thumb_square = youtube.resize((thumb_size, thumb_size))
        thumb_square.putalpha(mask)
        background.paste(thumb_square, (thumb_x, thumb_y), thumb_square)

        # 📝 Dynamic Text Positions
        text_x = thumb_x + thumb_size + 30
        title_y = thumb_y + 10
        info_y = title_y + int(thumb_size * 0.33)
        time_y = info_y + int(thumb_size * 0.28)

        def truncate_text(text, max_chars=30):
            return (text[:max_chars - 3] + "...") if len(text) > max_chars else text

        short_title = truncate_text(title, max_chars=20)
        short_channel = truncate_text(channel, max_chars=20)

        title_font = fit_text(draw, short_title, 600, font_path, 42, 28)
        draw.text((text_x, title_y), short_title, (255, 255, 255), font=title_font)

        info_text = f"{short_channel} • {views}"
        info_font = ImageFont.truetype("ShrutixMusic/assets/font2.ttf", 22)
        draw.text((text_x, info_y), info_text, (200, 200, 200), font=info_font)

        time_font = ImageFont.truetype("ShrutixMusic/assets/font2.ttf", 26)
        duration_text = duration if ":" in duration else f"00:{duration.zfill(2)}"
        time_display = f"00:00 / {duration_text}"
        draw.text((text_x, time_y), time_display, (200, 200, 200), font=time_font)

        # Watermark
        watermark_font = ImageFont.truetype("ShrutixMusic/assets/font2.ttf", 24)
        watermark_text = "@WTF_WhyMeeh"
        text_size = draw.textsize(watermark_text, font=watermark_font)
        x = background.width - text_size[0] - 25
        y = background.height - text_size[1] - 25
        for dx in (-1, 1):
            for dy in (-1, 1):
                draw.text((x + dx, y + dy), watermark_text, font=watermark_font, fill=(0, 0, 0, 180))
        draw.text((x, y), watermark_text, font=watermark_font, fill=(255, 255, 255, 240))

        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass

        tpath = f"cache/{videoid}.png"
        background.save(tpath)
        return tpath

    except Exception as e:
        print(f"[get_thumb Error] {e}")
        traceback.print_exc()
        return None
