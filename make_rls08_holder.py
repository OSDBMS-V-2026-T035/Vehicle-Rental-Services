from pathlib import Path
import struct
import numpy as np
from shapely.geometry import Polygon, box
from shapely.ops import unary_union, triangulate

OUT=Path('hardware_kit'); OUT.mkdir(exist_ok=True)

def write_stl(path, tris):
    tris=np.round(np.asarray(tris,dtype=np.float32).reshape(-1,3,3),6)
    nrm=np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]); ln=np.linalg.norm(nrm,axis=1); ok=ln>1e-10; nrm[ok]/=ln[ok,None]
    with Path(path).open('wb') as f:
        f.write(b'RLS08 universal chassis holder'.ljust(80,b' ')); f.write(struct.pack('<I',len(tris)))
        for n,t in zip(nrm,tris): f.write(struct.pack('<3f',*n)); f.write(struct.pack('<9f',*t.reshape(-1))); f.write(struct.pack('<H',0))

def slot(cx,cy,length,width):
    r=width/2; straight=length-width
    return unary_union([box(cx-straight/2, cy-r, cx+straight/2, cy+r),
                        Polygon([(cx+straight/2+r*np.cos(2*np.pi*i/32),cy+r*np.sin(2*np.pi*i/32)) for i in range(32)]),
                        Polygon([(cx-straight/2+r*np.cos(2*np.pi*i/32),cy+r*np.sin(2*np.pi*i/32)) for i in range(32)])])

def extrude(poly,z0,z1):
    out=[]
    geoms=list(poly.geoms) if hasattr(poly,'geoms') else [poly]
    for p in geoms:
        if p.geom_type!='Polygon': continue
        for q in triangulate(p):
            if not p.covers(q.representative_point()): continue
            c=list(q.exterior.coords)[:3]
            bot=np.array([[x,y,z0] for x,y in c]); top=np.array([[x,y,z1] for x,y in c])
            out += [bot[[0,2,1]],top]
        loops=[list(p.exterior.coords)[:-1]]+[list(r.coords)[:-1] for r in p.interiors]
        for loop in loops:
            for i in range(len(loop)):
                x,y=loop[i]; x2,y2=loop[(i+1)%len(loop)]
                a=np.array([x,y,z0]); b=np.array([x2,y2,z0]); c=np.array([x2,y2,z1]); d=np.array([x,y,z1])
                face=np.array([a,b,c,d]); out += [face[[0,1,2]],face[[0,2,3]]]
    return out

def cub(x0,x1,y0,y1,z0,z1):
    v=np.array([[x0,y0,z0],[x1,y0,z0],[x1,y1,z0],[x0,y1,z0],[x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]])
    return [v[list(i)] for i in [(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]]

def drilled_bar(yc):
    w,d,h=136,5.5,3
    shell=[(-w/2,yc-d/2),(w/2,yc-d/2),(w/2,yc+d/2),(-w/2,yc+d/2)]
    rings=[]
    for x in (-50,50):
        rings.append([(x+2.6*np.cos(2*np.pi*i/32),yc+2.6*np.sin(2*np.pi*i/32)) for i in range(32)])
    return extrude(Polygon(shell,rings),0,3)

# The frame accepts either the 120x26 mm manual version or the 126x26 mm
# retail version of the board.  Its clear pocket is 128x29 mm.
# One continuous top frame. The two long sides have Ø5.2 mm M4-clearance
# holes; the chassis' own slots provide the final adjustment.
outer=[(-68,-20),(68,-20),(68,20),(-68,20)]
inner=[(-64,-14.5),(64,-14.5),(64,14.5),(-64,14.5)]
holes=[inner]
for x in (-50,50):
    for y in (-17.25,17.25):
        holes.append([(x+2.6*np.cos(2*np.pi*i/32),y+2.6*np.sin(2*np.pi*i/32)) for i in range(32)])
parts=extrude(Polygon(outer,holes),0,3)

# Side guards and lower PCB support ledges. The middle remains open so the
# eight IR emitters/receivers can see the floor.
parts += cub(-68,-64,-14.5,14.5,3,8)
parts += cub(64,68,-14.5,14.5,3,8)
parts += cub(-64,64,-20,-14.5,3,8)
parts += cub(-64,64,14.5,20,3,8)
parts += cub(-64,64,-14.5,-11.5,5,6.5)
parts += cub(-64,64,11.5,14.5,5,6.5)

write_stl(OUT/'RLS08_Chassis_Undermount_Holder.stl',parts)

(OUT/'RLS08_Chassis_Undermount_Holder_README.txt').write_text('''RLS08 chassis under-mount holder\n================================\n\nDesigned for the SmartElex RLS08 board shown in the supplied photos.\nThe pocket accepts either the 120x26 mm manual dimension or the 126x26 mm\nretail dimension. The PCB sits in the side ledges; the central underside is\nopen for the eight IR sensors.\n\nPrint one holder. Attach the top frame to the underside/front of the old\n250x196x5.4 mm chassis using four M4 screws and washers through the 18x5.2 mm\nadjustment slots. Slide the holder sideways/fore-aft before tightening.\nInstall the board with the sensor/IR side facing the floor. Keep the sensor\nface approximately 3-5 mm above the floor; verify this with the wheel and\nchassis installed before final tightening.\n\nThe PCB size and hole pattern vary across RLS08 listings, so this is a\nclearance/retaining frame rather than a hard screw-through-PCB clamp. Use a\nsmall cable tie or two drops of removable adhesive only if the PCB rattles.\n''')
print('created',OUT/'RLS08_Chassis_Undermount_Holder.stl')
