from PIL import Image, ImageDraw


im = Image.new(mode='RGBA', size=(957-516, 28), color=(244, 223, 255, 255))
draw = ImageDraw.Draw(im) 

# draw repeated parallelograms to create a striped pattern on the progress bar that go from bottom left to top right, each one is 7 wide and there are 29 pixels of space between them

for i in range(0, 957-516, 36):
    draw.polygon([(i, 0), (i+7, 0), (i+29, 28), (i+22, 28)], fill=(241, 216, 255, 255))

# make them go from top left to bottom right
im = im.transpose(Image.FLIP_TOP_BOTTOM)


im.save('pbar.png')