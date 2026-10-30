"""Gus, a herring gull: white head and body, grey mantle, black wingtips with white mirrors,
a yellow bill with the red gonys spot, a pale eye with an orange ring, pink legs."""

from __future__ import annotations

import math

from mathutils import Vector

from . import lib
from . import materials as M
from .percy import feather, loft


class Gull:
    def __init__(self, col):
        self.col = col
        white = M.surface("gull_white", "#f7f6f2", rough=0.6, sheen=0.5, bump=(60.0, 0.15, "wave"))
        grey = M.surface("gull_grey", "#9aa4ad", rough=0.6, sheen=0.4, bump=(60.0, 0.15, "wave"))
        black = M.surface("gull_black", "#18181b", rough=0.5, sheen=0.4)
        bill = M.surface("gull_bill", "#f2c230", rough=0.35, coat=0.3)
        spot = M.surface("gull_spot", "#d8322b", rough=0.35)
        leg = M.surface("gull_leg", "#e9a3a0", rough=0.5, sss=0.2)
        eye = M.surface("gull_eye", "#f4e9b8", rough=0.1, coat=1.0)
        pupil = M.surface("gull_pupil", "#111111", rough=0.1, coat=1.0)
        self.root = lib.empty("gus_root", col, size=0.3)
        self.body = lib.empty("gus_body", col, parent=self.root, size=0.2)
        lib.ellipsoid("gus_body_mesh", (0.24, 0.12, 0.12), col, white, segs=24, rings=16, loc=(0, 0, 0),
                      parent=self.body,
                      warp=lambda x, y, z: (x, y * (1 - 0.35 * max(0, -x / 0.24)), z * (1 - 0.3 * max(0, -x / 0.24))))
        lib.ellipsoid("gus_tail", (0.1, 0.06, 0.02), col, white, segs=12, rings=6, loc=(-0.26, 0, 0.02),
                      parent=self.body)
        self.head = lib.empty("gus_head", col, loc=(0.2, 0, 0.12), parent=self.body, size=0.1)
        lib.ellipsoid("gus_skull", (0.075, 0.062, 0.068), col, white, segs=20, rings=12, parent=self.head)
        loft("gus_bill_upper", [(0.06, 0, 0.0), (0.1, 0, -0.002), (0.15, 0, -0.014)],
             [0.018, 0.013, 0.006], [0.012, 0.01, 0.007], col, bill, segs=12, parent=self.head)
        self.jaw = lib.empty("gus_jaw", col, loc=(0.06, 0, -0.012), parent=self.head, size=0.03)
        loft("gus_bill_lower", [(0.0, 0, 0.0), (0.05, 0, -0.004), (0.085, 0, -0.008)],
             [0.016, 0.012, 0.006], [0.008, 0.008, 0.005], col, bill, segs=10, parent=self.jaw)
        lib.ellipsoid("gus_spot", (0.009, 0.0125, 0.007), col, spot, segs=10, rings=6, loc=(0.07, 0, -0.006),
                      parent=self.jaw)
        for side in (-1, 1):
            e = lib.ellipsoid(f"gus_eye_{side}", (0.014, 0.014, 0.014), col, eye, segs=12, rings=8,
                              loc=(0.035, side * 0.05, 0.02), parent=self.head)
            lib.ellipsoid(f"gus_pupil_{side}", (0.006, 0.004, 0.006), col, pupil, segs=8, rings=6,
                          loc=(0.004, side * 0.012, 0.0), parent=e)
            lib.ellipsoid(f"gus_brow_{side}", (0.022, 0.008, 0.006), col, grey, segs=10, rings=6,
                          loc=(0.035, side * 0.05, 0.04), parent=self.head).rotation_euler = (0, -0.3, 0)
        self.wings = {}
        for side in (-1, 1):
            sh = lib.empty(f"gus_shoulder_{side}", col, loc=(0.08, side * 0.09, 0.06), parent=self.body, size=0.05)
            fold = lib.empty(f"gus_fold_{side}", col, parent=sh, size=0.03)
            loft(f"gus_fold_{side}", [(0.02, side * 0.01, 0), (-0.15, side * 0.03, -0.01), (-0.35, side * 0.02, 0.0)],
                 [0.05, 0.06, 0.02], [0.012, 0.016, 0.006], col, grey, segs=12, parent=fold,
                 lateral=Vector((0, 0, 1)))
            for k in range(4):
                feather(f"gus_foldtip_{side}_{k}", (-0.25 - 0.015 * k, side * 0.03, -0.005 - 0.006 * k),
                        (-0.45 - 0.01 * k, side * 0.035, 0.0), 0.018, col, black, parent=fold)
            spread = lib.empty(f"gus_spread_{side}", col, parent=sh, size=0.03)
            span = 0.62
            loft(f"gus_arm_{side}", [(0, 0, 0), (0.03, side * span * 0.45, 0.02), (0.0, side * span * 0.8, 0.0)],
                 [0.06, 0.05, 0.03], [0.012, 0.01, 0.008], col, grey, segs=12, parent=spread,
                 lateral=Vector((1, 0, 0)))
            for k in range(9):
                u = k / 8
                root = Vector((0.0, side * span * (0.08 + 0.6 * u), 0.01))
                feather(f"gus_sec_{side}_{k}", root, root + Vector((-0.17, side * 0.01, -0.005)), 0.03, col, grey,
                        parent=spread)
            for k in range(6):
                a = math.radians(-5 + 12 * k)
                root = Vector((-0.01, side * span * 0.76, 0.0))
                ln = 0.24 - 0.012 * abs(k - 2)
                feather(f"gus_prim_{side}_{k}", root, root + Vector((-math.sin(a) * ln, side * math.cos(a) * ln, -0.01)),
                        0.024, col, black, parent=spread)
            self.wings[side] = dict(shoulder=sh, fold=fold, spread=spread)
        for side in (-1, 1):
            lib.tube(f"gus_leg_{side}", [(0.0, side * 0.04, -0.08), (0.01, side * 0.045, -0.2)], [0.008, 0.007], col,
                     leg, segs=8, parent=self.body)
            lib.ellipsoid(f"gus_foot_{side}", (0.04, 0.025, 0.006), col, leg, segs=10, rings=6,
                          loc=(0.03, side * 0.045, -0.205), parent=self.body)
