from PIL import Image, ImageSequence, ImageDraw
from io import BytesIO 


__all__ = (
    'generate_rank_card',
)

AV_WIDTH = 205 
AV_CORNER = (93, 34)
LVL_CORNER = (329, 142)
LVL_HEIGHT = 229 - 142
PBAR_CORNER = (320, 253)
PBAR_FULL_SIZE = (760-320, 270-252)

numbers = {}
for i in range(10):
    im = Image.open(f'assets/{i}.png')
    newy = LVL_HEIGHT 
    newx = round(im.size[0] * (newy / im.size[1]))
    im = im.resize((newx, newy))
    numbers[str(i)] = im 


pbar = Image.open('assets/pbar.png').convert(mode='RGBA')
frame1 = Image.open('assets/frame1.png').convert(mode='RGBA')
frame2 = Image.open('assets/frame2.png').convert(mode='RGBA')

def generate_rank_card(level, av_file, percent):
    save_kwargs = {
        "format": "GIF",
        "save_all": True, 
        "loop": 0,
        "duration": 1000,
        "optimize": False
    }

    layer = Image.new(mode='RGBA', size=frame1.size, color=(0, 0, 0, 0))

    with Image.open(av_file) as av:
        av = av.resize((AV_WIDTH, AV_WIDTH)) 

    mask = Image.new("L", av.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(0, 0), av.size], fill=255)
    layer.paste(av, AV_CORNER, mask)

    digitx = LVL_CORNER[0]
    digity = LVL_CORNER[1]

    for digit in str(level):
        im = numbers[digit]
        layer.paste(im, (digitx, digity))
        digitx += im.size[0]

    # crop the progress bar from the right based on the percent 
    pbar_crop = pbar.crop((0, 0, round(pbar.size[0] * (percent)), pbar.size[1]))
    # round the corners of pbar_crop
    mask = Image.new("L", pbar_crop.size, 0)
    draw = ImageDraw.Draw(mask)
    # draw a rounded rectangle over mask
    draw.rounded_rectangle([(0, 0), pbar_crop.size], fill=255, radius=15)
    new = Image.new(mode='RGBA', size=pbar_crop.size, color=0)
    new.paste(pbar_crop, (0, 0), mask)
    xsize = round(PBAR_FULL_SIZE[0]*percent)
    if xsize > 0:
        new = new.resize((round(PBAR_FULL_SIZE[0]*percent), PBAR_FULL_SIZE[1]))
        layer.paste(new, PBAR_CORNER, new)
    
    f1 = frame1.copy()
    f2 = frame2.copy()

    f1.paste(layer, (0, 0), layer)
    f2.paste(layer, (0, 0), layer)

    out = BytesIO()
    f1.save(out, append_images=[f2], **save_kwargs)
    out.seek(0)
    return out 

