# -*- coding: utf-8 -*-
"""v3.26 需求：生成 8 个「md」主题应用图标候选，供用户挑选。

输出：
  icons_md/icon1.png ~ icon8.png   256x256 预览图
  icons_md/icon1.ico ~ icon8.ico   含 16~256 全尺寸（后续打包 exe 用）
  icons_md/preview.html            明暗双底色预览页
用 venv 解释器运行：python _gen_icons.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "icons_md")
os.makedirs(OUT, exist_ok=True)

S = 256                      # 画布边长
R = 52                       # 圆角半径（macOS 风格大圆角）
FONT = r"C:\Windows\Fonts\arialbd.ttf"      # Arial Bold
FONT_R = r"C:\Windows\Fonts\segoeuib.ttf"   # Segoe UI Bold


def base_canvas():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def rounded(draw, fill):
    draw.rounded_rectangle([4, 4, S - 4, S - 4], radius=R, fill=fill)


def vgrad(draw, c1, c2):
    """竖向渐变圆角底。c1 顶 / c2 底。"""
    grad = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(4, S - 4):
        t = (y - 4) / (S - 8)
        gd.line([(4, y), (S - 4, y)],
                fill=tuple(int(a + (b - a) * t) for a, b in zip(c1, c2)))
    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([4, 4, S - 4, S - 4], radius=R, fill=255)
    return grad, mask


def center_text(draw, xy, text, font, fill, dy=0):
    draw.text((xy[0], xy[1] + dy), text, font=font, fill=fill, anchor="mm")


def save(img, name):
    img.save(os.path.join(OUT, name + ".png"))
    img.save(os.path.join(OUT, name + ".ico"),
             sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                    (64, 64), (128, 128), (256, 256)])


# ---------- 1. 经典蓝：蓝色圆角方块 + 白色粗体 MD ----------
img = base_canvas()
d = ImageDraw.Draw(img)
rounded(d, "#0052d9")
center_text(d, (128, 130), "MD", ImageFont.truetype(FONT, 104), "white")
save(img, "icon1")

# ---------- 2. 文档折角：白色文档纸 + 蓝色 MD ----------
img = base_canvas()
d = ImageDraw.Draw(img)
rounded(d, "#ffffff")
d.rounded_rectangle([4, 4, S - 4, S - 4], radius=R, outline="#d8dce2", width=4)
# 文档纸（带右上折角）
d.rounded_rectangle([62, 40, 194, 216], radius=14, fill="#eef2f7",
                    outline="#c9d3de", width=4)
d.polygon([(152, 40), (194, 40), (194, 82)], fill="#c9d3de")  # 折角
d.polygon([(152, 40), (194, 82), (152, 82)], fill="#e8edf3")
center_text(d, (128, 136), "MD", ImageFont.truetype(FONT, 72), "#0052d9")
save(img, "icon2")

# ---------- 3. 天空蓝渐变：淡蓝→天蓝渐变 + 白 MD ----------
img = base_canvas()
grad, mask = vgrad(ImageDraw.Draw(img), (158, 209, 255, 255), (74, 168, 242, 255))
img.paste(grad, (0, 0), mask)
d = ImageDraw.Draw(img)
center_text(d, (128, 130), "MD", ImageFont.truetype(FONT, 104), "white")
save(img, "icon3")

# ---------- 4. 暗夜青：深色底 + 青色 MD + 光标条 ----------
img = base_canvas()
d = ImageDraw.Draw(img)
rounded(d, "#16191d")
center_text(d, (128, 118), "MD", ImageFont.truetype(FONT, 96), "#38b28c")
d.rounded_rectangle([76, 182, 180, 198], radius=8, fill="#38b28c")  # 光标条
save(img, "icon4")

# ---------- 5. Markdown 风：白底 + 黑 M + 下箭头 ----------
img = base_canvas()
d = ImageDraw.Draw(img)
rounded(d, "#ffffff")
d.rounded_rectangle([4, 4, S - 4, S - 4], radius=R, outline="#24292f", width=6)
center_text(d, (100, 130), "M", ImageFont.truetype(FONT, 112), "#24292f")
# 下箭头（与 M 等高的粗箭头）
d.rounded_rectangle([160, 74, 184, 140], radius=6, fill="#24292f")
d.polygon([(140, 138), (204, 138), (172, 186)], fill="#24292f")
save(img, "icon5")

# ---------- 6. 活力橙：橙渐变 + 白色小写 md ----------
img = base_canvas()
grad, mask = vgrad(ImageDraw.Draw(img), (255, 157, 66, 255), (255, 106, 0, 255))
img.paste(grad, (0, 0), mask)
d = ImageDraw.Draw(img)
center_text(d, (128, 130), "md", ImageFont.truetype(FONT, 108), "white")
save(img, "icon6")

# ---------- 7. 清新绿：绿色底 + 白 MD + 铅笔 ----------
img = base_canvas()
d = ImageDraw.Draw(img)
rounded(d, "#2f9e44")
center_text(d, (118, 122), "MD", ImageFont.truetype(FONT, 88), "white")
# 右下角小铅笔（斜杆 + 笔尖）
p = ImageDraw.Draw(img)
p.polygon([(166, 196), (216, 146), (232, 162), (182, 212)], fill="white")
p.polygon([(166, 196), (182, 212), (158, 220)], fill="#dff0e3")
save(img, "icon7")

# ---------- 8. 极简白：白底细边 + 蓝色 MD + 蓝下划线 ----------
img = base_canvas()
d = ImageDraw.Draw(img)
rounded(d, "#ffffff")
d.rounded_rectangle([4, 4, S - 4, S - 4], radius=R, outline="#d8dce2", width=4)
center_text(d, (128, 116), "MD", ImageFont.truetype(FONT_R, 96), "#0052d9")
d.rounded_rectangle([78, 178, 178, 192], radius=7, fill="#0052d9")
save(img, "icon8")

# ---------- 预览页 ----------
NAMES = [
    ("icon1", "1 · 经典蓝", "蓝色圆角方块 + 白色粗体 MD，与主题强调色一致"),
    ("icon2", "2 · 文档折角", "白色文档纸 + 蓝色 MD，突出「文档」属性"),
    ("icon3", "3 · 天空蓝渐变", "淡蓝→天蓝渐变底 + 白 MD，清新通透"),
    ("icon4", "4 · 暗夜青", "深色底 + 青色 MD + 光标条，暗色主题同款"),
    ("icon5", "5 · Markdown 风", "官方 Markdown 意象：M + 下箭头"),
    ("icon6", "6 · 活力橙", "橙色渐变 + 小写 md，轻快亲和"),
    ("icon7", "7 · 清新绿", "绿色底 + 白 MD + 铅笔，强调「写作」"),
    ("icon8", "8 · 极简白", "白底细边 + 蓝 MD + 下划线，克制简洁"),
]
cards = []
for fid, title, desc in NAMES:
    cards.append(f"""
    <div class="card">
      <div class="imgs"><img src="{fid}.png" alt="{title}"><img class="dark" src="{fid}.png" alt="{title}"></div>
      <h3>{title}</h3><p>{desc}</p>
    </div>""")
html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>mdEditor 应用图标候选（v3.26）</title>
<style>
  body {{ font-family: "Segoe UI", "Microsoft YaHei", sans-serif; background:#f5f6f8; margin:0; padding:32px; }}
  h1 {{ font-size:22px; color:#1f2328; }}
  .tip {{ color:#6b7280; font-size:14px; margin-bottom:24px; }}
  .grid {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:20px; }}
  .card {{ background:#fff; border:1px solid #e6e8eb; border-radius:12px; padding:18px; }}
  .imgs {{ display:flex; gap:14px; align-items:center; }}
  .imgs img {{ width:96px; height:96px; border-radius:16px; }}
  .imgs .dark {{ background:#16191d; }}
  h3 {{ font-size:15px; margin:12px 0 4px; color:#1f2328; }}
  p {{ font-size:12px; color:#6b7280; margin:0; line-height:1.5; }}
</style></head><body>
<h1>mdEditor 应用图标候选（共 8 个，任选其一）</h1>
<div class="tip">左侧为浅色底上的效果，右侧为深色底上的效果。选定后回复编号（如「用 icon3」），
我将把它接入窗口标题栏图标与 exe 打包图标。</div>
<div class="grid">{''.join(cards)}</div>
</body></html>"""
with open(os.path.join(OUT, "preview.html"), "w", encoding="utf-8") as f:
    f.write(html)

print("done:", sorted(os.listdir(OUT)))
