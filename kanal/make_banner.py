import sys
from PIL import Image, ImageFilter, ImageDraw, ImageEnhance, ImageChops
E='el/el/'; E34='el34/el/'
W,H=2048,1152
bg=Image.open(E34+'f1_meadow_day.jpg').convert('RGB')
# фон: заполняем 2048×1152 (обрезка по центру), чуть размыт и светлее, чтобы герои читались
r=max(W/bg.width,H/bg.height); bg=bg.resize((int(bg.width*r)+1,int(bg.height*r)+1),Image.LANCZOS)
x0=(bg.width-W)//2; y0=(bg.height-H)//2; bg=bg.crop((x0,y0,x0+W,y0+H)).filter(ImageFilter.GaussianBlur(3))
bg=ImageEnhance.Brightness(bg).enhance(1.05)
# мягкое световое пятно за героями
glow=Image.new('L',(W,H),0); d=ImageDraw.Draw(glow); d.ellipse((W/2-760,H/2-300,W/2+760,H/2+330),fill=150); glow=glow.filter(ImageFilter.GaussianBlur(120))
bg=Image.composite(Image.new('RGB',(W,H),(255,246,214)),bg,glow)
def hero(name,h):
    im=Image.open(E+name+'.png').convert('RGBA'); bb=im.getbbox(); im=im.crop(bb)
    k=h/im.height; im=im.resize((int(im.width*k),h),Image.LANCZOS)
    a=im.split()[3]; pad=14
    big=Image.new('L',(im.width+2*pad,im.height+2*pad),0); big.paste(a,(pad,pad)); edge=big.filter(ImageFilter.MaxFilter(2*9+1)).filter(ImageFilter.GaussianBlur(1.5))
    st=Image.new('RGBA',big.size,(255,255,255,0)); st.putalpha(edge)
    sh=Image.new('RGBA',big.size,(60,40,20,0)); sh.putalpha(edge.point(lambda v:int(v*.35))); 
    out=Image.new('RGBA',(big.width+30,big.height+30),(0,0,0,0)); out.paste(sh,(18,22),sh); out=out.filter(ImageFilter.GaussianBlur(8)); out.paste(st,(0,0),st); out.paste(im,(pad,pad),im)
    return out
cy=H//2+10   # центр полосы, видимой на всех устройствах (1235×338 по центру)
lay=[('g4_Пик_mashet',262,-480),('g2_Рон_likuet1',272,-255),('g1_Барсик_likuet2',305,0),('g3_Филя_mashet',272,250),('g5_Топа_likuet1',270,478)]
order=[0,4,1,3,2]   # дальние — раньше, Барсик — сверху
for i in order:
    n,h,dx=lay[i]; im=hero(n,h); x=W//2+dx-im.width//2; y=cy+150-im.height+30
    bg.paste(im,(x,y),im)
# искры
d=ImageDraw.Draw(bg)
import random; random.seed(7)
for _ in range(26):
    x=random.randint(380,1670); y=random.randint(410,760)
    if abs(x-W/2)<720 and abs(y-cy)<150: continue
    s=random.randint(5,11); d.polygon([(x,y-s*2),(x+s*.5,y-s*.5),(x+s*2,y),(x+s*.5,y+s*.5),(x,y+s*2),(x-s*.5,y+s*.5),(x-s*2,y),(x-s*.5,y-s*.5)],fill=(255,250,215))
bg.save('out/banner.jpg',quality=92)
# проверка: что видно на телефоне (1235×338 по центру) и на компьютере (2048×423 по центру)
bg.crop((W//2-617,H//2-169,W//2+618,H//2+169)).save('out/banner_phone.jpg',quality=85)
bg.crop((0,H//2-211,W,H//2+212)).save('out/banner_pc.jpg',quality=85)
print('ok')
