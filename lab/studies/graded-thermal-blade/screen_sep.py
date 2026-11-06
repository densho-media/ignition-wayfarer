import ship, radmc as m, sys
# Gray view-factor style screen: fraction of a cool section's emission absorbed by HOT (black-ish HOT=0.9), vs separation
for s in [2,10,20,40,60,90]:
    sc=m.Scene(); ship.base(sc, rings=False, tanks=False, casing_to=ship.HOT_FRONT+s+25)
    x0=ship.HOT_FRONT+s
    ship.section_plates(sc,'C',m.GRAY90,440,x0,x0+21, r0=ship.R0+3)
    sc.compile(); G=sc.trace('C',n=60000,bands=[0])
    print(s, 'G_C->HOT', round(G[0,sc.names.index('HOT')],5), 'space', round(G[0,-1],3), flush=True)
