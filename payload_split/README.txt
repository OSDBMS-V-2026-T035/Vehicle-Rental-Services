ModuMove payload split
======================

The supplied chassis and payload STL files were measured directly.

Chassis STL: 280 x 220 x 6 mm, bounds X=-140..140, Y=-110..110, Z=0..6.
Payload STL: 280 x 220 x 11 mm, bounds X=-140..140, Y=-110..110, Z=0..11.

The payload is split across X=0 with an alternating Japanese-style puzzle/finger
joint. The joint has approximately 0.5 mm clearance and alternating 16 mm
deep fingers. Slide the two halves together along X; do not force them down
through the joint. Adhesive or two small underside fasteners can be added if
the AMR will see impact loads.

Printable envelopes:
  Left:  148 x 220 x 11 mm
  Right: 147.5 x 220 x 11 mm

Print the two payload files with their original Z=0 face on the bed. For the
assembled AMR, translate both payload halves upward by 6 mm so the payload
bottom sits on the chassis top. The included
ModuMove_AMR_Chassis_Payload_Assembly_Reference.stl is a visual assembly
reference and is not intended as one-piece printing.

Note: the requested nominal 250 x 196 x 5.4 mm dimensions do not match the
provided STL geometry; the files measure 280 x 220 mm in footprint. The output
preserves the supplied STL envelope so it matches the supplied chassis.
