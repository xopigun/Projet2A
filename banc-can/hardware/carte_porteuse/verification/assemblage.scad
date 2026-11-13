// Carte porteuse v0.2 et encombrement des modules enfichés (repère de l'export KiCad : x = X-100, y = 100-Y).
module boite(x0, x1, y0, y1, z0, z1) { translate([x0 - 100, 100 - y1, z0]) cube([x1 - x0, y1 - y0, z1 - z0]); }
color("darkgreen") import("carte.stl");
color("steelblue", 0.45) { boite(109.8, 128.3, 106.1, 156.4, 11.0, 12.6); boite(115.2, 122.9, 104.9, 110.5, 12.6, 15.6); }
color("white", 0.8) boite(105.4, 132.7, 159.5, 161.1, 1.0, 29.0);
color("black") boite(106.0, 132.0, 161.1, 162.5, 6.0, 25.0);
color("royalblue", 0.8) boite(93.6, 95.2, 117.3, 138.5, 1.0, 17.6);
color("orange", 0.8) { boite(85.0, 98.9, 103.0, 103.6, 4, 4.6); boite(85, 98.9, 108.0, 108.6, 4, 4.6); boite(85, 98.9, 113.0, 113.6, 4, 4.6);
                        boite(139.6, 155.0, 103.0, 103.6, 4, 4.6); boite(139.6, 155, 108.0, 108.6, 4, 4.6); boite(139.6, 155, 113.0, 113.6, 4, 4.6); }
color("red") boite(130.2, 132.8, 118.0, 122.6, 4.1, 10.1);
