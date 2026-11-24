from PIL import Image, ImageDraw, ImageFilter
S=800
bg=Image.new('RGB',(S,S),(0,0,0)); d=ImageDraw.Draw(bg)
for y in range(S):   # небо: голубой → тёплый светлый
    t=y/S; d.line([(0,y),(S,y)],fill=(int(120+120*t),int(190+50*t),int(245-25*t)))
glow=Image.new('L',(S,S),0); ImageDraw.Draw(glow).ellipse((90,60,710,680),fill=170); glow=glow.filter(ImageFilter.GaussianBlur(90))
bg=Image.composite(Image.new('RGB',(S,S),(255,247,215)),bg,glow)
im=Image.open('el/el/g1_Барсик_likuet2.png').convert('RGBA'); im=im.crop(im.getbbox())
# голова, лапки у щёк и шарф — верхние ~55 % фигуры
top=im.crop((0,0,im.width,int(im.height*0.56)))
k=640/top.width; top=top.resize((int(top.width*k),int(top.height*k)),Image.LANCZOS)
x=(S-top.width)//2; y=S-top.height+40
bg.paste(top,(x,y),top)
mask=Image.new('L',(S,S),0); ImageDraw.Draw(mask).ellipse((0,0,S,S),fill=255)
out=Image.new('RGBA',(S,S),(0,0,0,0)); out.paste(bg,(0,0),mask)
ImageDraw.Draw(out).ellipse((6,6,S-6,S-6),outline=(255,255,255,255),width=14)
out.save('out/avatar.png'); out.convert('RGB').resize((88,88),Image.LANCZOS).save('out/avatar_88.png'); out.convert('RGB').resize((40,40),Image.LANCZOS).save('out/avatar_40.png')
print(top.size)
