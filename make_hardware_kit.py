from pathlib import Path
import struct
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch
from shapely.geometry import Polygon, Point
from shapely.ops import triangulate

OUT=Path('hardware_kit'); OUT.mkdir(exist_ok=True)

def write_stl(path, tris, label):
    tris=np.round(np.asarray(tris,dtype=np.float32).reshape(-1,3,3),6)
    nrm=np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]); ln=np.linalg.norm(nrm,axis=1); ok=ln>1e-10; nrm[ok]/=ln[ok,None]
    with Path(path).open('wb') as f:
        f.write((('Codex ModuMove - '+label).encode('ascii')[:80]).ljust(80,b' ')); f.write(struct.pack('<I',len(tris)))
        for n,t in zip(nrm,tris): f.write(struct.pack('<3f',*n)); f.write(struct.pack('<9f',*t.reshape(-1))); f.write(struct.pack('<H',0))

def box(x0,x1,y0,y1,z0,z1):
    v=np.array([[x0,y0,z0],[x1,y0,z0],[x1,y1,z0],[x0,y1,z0],[x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]],float)
    ids=[(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
    return [v[list(i)] for i in ids]

def ring_prism(ro,ri,h,n=48,z0=0):
    out=[]
    for i in range(n):
        a=2*np.pi*i/n; b=2*np.pi*(i+1)/n
        p=np.array([[ro*np.cos(a),ro*np.sin(a),z0],[ro*np.cos(b),ro*np.sin(b),z0],[ro*np.cos(b),ro*np.sin(b),z0+h],[ro*np.cos(a),ro*np.sin(a),z0+h]])
        out += [p[[0,1,2]],p[[0,2,3]]]
        q=np.array([[ri*np.cos(a),ri*np.sin(a),z0],[ri*np.cos(a),ri*np.sin(a),z0+h],[ri*np.cos(b),ri*np.sin(b),z0+h],[ri*np.cos(b),ri*np.sin(b),z0]])
        out += [q[[0,1,2]],q[[0,2,3]]]
        # Annular top and bottom faces close the ring.
        bot=np.array([[ro*np.cos(a),ro*np.sin(a),z0],[ro*np.cos(b),ro*np.sin(b),z0],[ri*np.cos(b),ri*np.sin(b),z0],[ri*np.cos(a),ri*np.sin(a),z0]])
        top=np.array([[ro*np.cos(a),ro*np.sin(a),z0+h],[ri*np.cos(a),ri*np.sin(a),z0+h],[ri*np.cos(b),ri*np.sin(b),z0+h],[ro*np.cos(b),ro*np.sin(b),z0+h]])
        out += [bot[[0,1,2]],bot[[0,2,3]],top[[0,1,2]],top[[0,2,3]]]
    return out

def stepped_standoff(n=48):
    """Closed stepped annulus: 11 mm flange, 8 mm body, 4.5 mm bore."""
    ro0, ro1, ri = 11.0, 8.0, 2.25
    z0, z1, z2 = 0.0, 3.0, 30.0
    out=[]
    for i in range(n):
        a=2*np.pi*i/n; b=2*np.pi*(i+1)/n
        def pt(r,ang,z): return np.array([r*np.cos(ang),r*np.sin(ang),z])
        # Outer stepped wall and inner bore wall.
        for rA,rB,za,zb in [(ro0,ro0,z0,z1),(ro1,ro1,z1,z2),(ri,ri,z2,z0)]:
            p=np.array([pt(rA,a,za),pt(rB,b,za),pt(rB,b,zb),pt(rA,a,zb)])
            out += [p[[0,1,2]],p[[0,2,3]]]
        # Bottom flange annulus.
        p=np.array([pt(ro0,a,z0),pt(ro0,b,z0),pt(ri,b,z0),pt(ri,a,z0)])
        out += [p[[0,1,2]],p[[0,2,3]]]
        # Horizontal shoulder at z=3 and top annulus.
        p=np.array([pt(ro0,a,z1),pt(ro1,a,z1),pt(ro1,b,z1),pt(ro0,b,z1)])
        out += [p[[0,1,2]],p[[0,2,3]]]
        p=np.array([pt(ro1,a,z2),pt(ro1,b,z2),pt(ri,b,z2),pt(ri,a,z2)])
        out += [p[[0,1,2]],p[[0,2,3]]]
    return out

def plate_xy(w,d,h,holes=(),z0=0):
    shell=[(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]
    rings=[]
    for x,y,r in holes:
        rings.append([(x+r*np.cos(2*np.pi*i/32),y+r*np.sin(2*np.pi*i/32)) for i in range(32)])
    poly=Polygon(shell,rings)
    out=[]
    for q in triangulate(poly):
        if not poly.covers(q.representative_point()): continue
        c=list(q.exterior.coords)[:3]
        bot=np.array([[x,y,z0] for x,y in c]); top=np.array([[x,y,z0+h] for x,y in c])
        out += [bot[[0,2,1]],top]
    # Outer and hole walls.
    loops=[shell]+rings
    for j,loop in enumerate(loops):
        for i in range(len(loop)):
            a=np.array([*loop[i],z0]); b=np.array([*loop[(i+1)%len(loop)],z0]); c=np.array([*loop[(i+1)%len(loop)],z0+h]); d0=np.array([*loop[i],z0+h])
            face=[a,b,c,d0]
            out += [np.array(face)[[0,1,2]],np.array(face)[[0,2,3]]]
    return out

def plate_xz(w,h,d,holes=(),y0=0):
    # x-z plate, thickness along Y.
    shell=[(-w/2,0),(w/2,0),(w/2,h),( -w/2,h)]
    rings=[[(x+r*np.cos(2*np.pi*i/32),z+r*np.sin(2*np.pi*i/32)) for i in range(32)] for x,z,r in holes]
    poly=Polygon(shell,rings); out=[]
    for q in triangulate(poly):
        if not poly.covers(q.representative_point()): continue
        c=list(q.exterior.coords)[:3]
        a=np.array([[x,y0,z] for x,z in c]); b=np.array([[x,y0+d,z] for x,z in c])
        out += [a[[0,2,1]],b]
    loops=[shell]+rings
    for loop in loops:
        for i in range(len(loop)):
            x,z=loop[i]; x2,z2=loop[(i+1)%len(loop)]
            a=np.array([x,y0,z]); b=np.array([x2,y0,z2]); c=np.array([x2,y0+d,z2]); d0=np.array([x,y0+d,z])
            face=[a,b,c,d0]; out += [np.array(face)[[0,1,2]],np.array(face)[[0,2,3]]]
    return out

# Universal L-bracket: print one at each of the four chassis side-slot locations.
motor=[]
motor += plate_xy(75,45,5,holes=[(-25,-14,2.25),(-25,14,2.25),(25,-14,2.25),(25,14,2.25)])
motor += plate_xz(75,55,5,holes=[(-25,25,2.75),(25,25,2.75),(-25,42,2.75),(25,42,2.75)],y0=17.5)
write_stl(OUT/'Universal_Motor_Mount_Bracket.stl',motor,'universal motor L bracket')

# Payload support post: print four, using the four outer chassis/payload holes.
post=stepped_standoff()
write_stl(OUT/'Payload_Standoff_30mm.stl',post,'payload standoff')

# Generic front sensor bracket: print one or two; it accepts small camera/ultrasonic modules.
sensor=[]
sensor += plate_xy(60,32,4,holes=[(-22,0,2.25),(22,0,2.25)])
sensor += plate_xz(60,42,4,holes=[(-22,20,2.75),(22,20,2.75),(-22,34,2.75),(22,34,2.75)],y0=14)
write_stl(OUT/'Universal_Front_Sensor_Bracket.stl',sensor,'universal front sensor bracket')

# Placement diagram based on chassis axes; front is defined as Y=-110.
fig,ax=plt.subplots(figsize=(12,8),dpi=180)
ax.add_patch(FancyBboxPatch((-140,-110),280,220,boxstyle='round,pad=0,rounding_size=10',facecolor='#eef1f4',edgecolor='#202a33',lw=2))
# Motor/wheel locations.
for i,(x,y) in enumerate([(-118,-35),(-118,35),(118,-35),(118,35)],1):
    ax.add_patch(Rectangle((x-5,y-12),10,24,facecolor='#f28e2b',edgecolor='#8a4b08'))
    ax.add_patch(Circle((np.sign(x)*148,y),24,facecolor='#555b63',edgecolor='#20242a',alpha=.9))
    ax.text(x,y,f'M{i}',ha='center',va='center',fontsize=9,weight='bold')
# Four payload standoffs selected from outer mounting pattern.
for x,y in [(-125,-95),(-125,95),(125,-95),(125,95)]:
    ax.add_patch(Circle((x,y),5,facecolor='#d62728',edgecolor='#7d1111'))
# Battery and electronics approximate bay locations.
ax.add_patch(Rectangle((-48,-30),96,42,facecolor='#4c78a8',alpha=.85,edgecolor='#163a5f'))
ax.text(0,-9,'BATTERY',ha='center',va='center',color='white',weight='bold',fontsize=10)
ax.add_patch(Rectangle((-52,25),104,32,facecolor='#9467bd',alpha=.85,edgecolor='#4b2d67'))
ax.text(0,41,'Raspberry Pi + motor driver',ha='center',va='center',color='white',weight='bold',fontsize=9)
# Front components and caster.
ax.add_patch(Rectangle((-12,-115),24,5,facecolor='#e15759',edgecolor='#8b1e1e')); ax.text(0,-119,'camera',ha='center',va='top',fontsize=9)
for x in (-48,48):
    ax.add_patch(Rectangle((x-12,-115),24,5,facecolor='#59a14f',edgecolor='#245b22')); ax.text(x,-119,'ultrasonic',ha='center',va='top',fontsize=8)
ax.add_patch(Circle((0,-128),13,facecolor='#777',edgecolor='#333')); ax.text(0,-129,'caster',ha='center',va='center',color='white',fontsize=8)
ax.add_patch(Circle((0,75),14,facecolor='#222',edgecolor='#08a8e8',lw=3)); ax.text(0,75,'LiDAR',ha='center',va='center',color='white',fontsize=8)
ax.annotate('4 drive motors + wheels\nuse orange side slots',xy=(118,35),xytext=(155,60),arrowprops=dict(arrowstyle='->',color='#8a4b08'),color='#8a4b08',bbox=dict(fc='white',ec='#f28e2b'))
ax.annotate('4 payload standoffs\nuse red holes',xy=(-125,95),xytext=(-205,135),arrowprops=dict(arrowstyle='->',color='#7d1111'),color='#7d1111',bbox=dict(fc='white',ec='#d62728'))
ax.annotate('Battery + electronics\ninside enclosure',xy=(0,35),xytext=(60,135),arrowprops=dict(arrowstyle='->',color='#4b2d67'),color='#4b2d67',bbox=dict(fc='white',ec='#9467bd'))
ax.set_xlim(-215,215); ax.set_ylim(-155,165); ax.set_aspect('equal'); ax.set_xlabel('X (mm)'); ax.set_ylabel('Y (mm)'); ax.grid(alpha=.18)
ax.set_title('ModuMove AMR — proposed component placement from supplied reference image',weight='bold')
fig.tight_layout(); fig.savefig(OUT/'component_layout.png',bbox_inches='tight')

(OUT/'README.txt').write_text('''ModuMove hardware kit\n=====================\n\nProposed placement (front = Y=-110):\n- Four drive motor/wheel positions are at the four orange side slots, approximately X=+/-118, Y=+/-35.\n- Four payload standoffs use the outer mounting holes at (+/-125,+/-95). Print 4 standoffs.\n- Battery and Raspberry Pi/motor driver sit in the protected central bay.\n- Camera and ultrasonic modules face the front edge; LiDAR sits on the upper centerline.\n- Caster is centered under the front edge.\n\nIncluded printable parts:\n- Universal_Motor_Mount_Bracket.stl: print 4; adjustable L-bracket, not a motor-specific cradle.\n- Payload_Standoff_30mm.stl: print 4; 4.5 mm through-hole, 30 mm height.\n- Universal_Front_Sensor_Bracket.stl: print 1-2 for camera/ultrasonic modules.\n\nImportant: the supplied concept image does not specify motor body size, shaft height, wheel bore, or bolt pattern. Verify those dimensions before final motor/wheel cradles are made.\n''')
print('created',list(p.name for p in OUT.iterdir()))
