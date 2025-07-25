from PIL import Image
from io import BytesIO
from fastapi import HTTPException


def convert_to_jpg(file_stream):
    """将图片转换为JPG格式"""
    try:
        img = Image.open(file_stream)
        # 处理透明背景（转换为RGB模式）
        if img.mode in ("RGBA", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        # 调整尺寸（可选）
        max_size = (1024, 768)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        output = BytesIO()
        img.save(output, format="JPEG", quality=85)
        output.seek(0)
        return output
    except Exception as e:
        raise HTTPException(400, f": {str(e)}")
