from PIL import Image, ImageDraw, ImageFont
import os

# Colors from the site: deep blue gradient, gold accent
bg_color = (0, 78, 146)  # #004e92
accent_color = (255, 215, 0)  # #ffd700

size = (64, 64)
img = Image.new('RGBA', size, bg_color)
draw = ImageDraw.Draw(img)

# Draw a gold circle in the center
circle_radius = 24
center = (size[0] // 2, size[1] // 2)
draw.ellipse([
    (center[0] - circle_radius, center[1] - circle_radius),
    (center[0] + circle_radius, center[1] + circle_radius)
], fill=accent_color)

# Draw a white "F" for Family
try:
    font = ImageFont.truetype("arial.ttf", 32)
except:
    font = ImageFont.load_default()
text = "F"
bbox = draw.textbbox((0, 0), text, font=font)
text_width = bbox[2] - bbox[0]
text_height = bbox[3] - bbox[1]
text_pos = (center[0] - text_width // 2, center[1] - text_height // 2)
draw.text(text_pos, text, font=font, fill="white")

# Ensure output directory exists
os.makedirs("static/images", exist_ok=True)
img.save("static/images/favicon.png", format="PNG")
print("Favicon created at static/images/favicon.png")
