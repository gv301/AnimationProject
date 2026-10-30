"""Build the 3D half of ATTEMPT 4,818 as a .blend (Blender 4.4+ / 5.x).

  blender -b -P blender/build.py -- [--out blender/attempt_4818_3d.blend] [--frames 3481-8255]

Everything is procedural and driven by blender/anim.json (python blender/export_anim.py),
so the 3D picture lands on the same frames as the 2D film's soundtrack.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

from a4818 import lib, sets, world  # noqa: E402
from a4818 import materials as M  # noqa: E402
from a4818.bike import Bike, SADDLE, K  # noqa: E402
from a4818.gull import Gull  # noqa: E402
from a4818.percy import Percy, HEAD  # noqa: E402

FPS = 30
SUN_DAY = 30.0         # sky azimuths: day light from the camera side, sunsets over the sea ahead
SUN_SET = 120.0


class Film3D:
    def __init__(self, anim, frames=None):
        self.a = anim
        rows = anim["frames"]
        if frames:
            rows = [r for r in rows if frames[0] <= r["f"] <= frames[1]]
        self.rows = rows
        self.frames = [r["f"] for r in rows]
        self.scenes = anim["scenes"]
        self.course = next((r["course"] for r in anim["frames"] if "course" in r), None)

    def cue(self, scene, name):
        s = self.scenes[scene]
        return s["start"] + s["cues"][name]

    def f(self, scene, name, dt=0.0):
        return int(round((self.cue(scene, name) + dt) * FPS))

    def scene_range(self, scene):
        s = self.scenes[scene]
        return s["frame_start"], s["frame_end"]


def blink(t, seed=0):
    """0..1 lid closure: a quick blink every few seconds (deterministic)."""
    period = 3.6
    k = math.floor((t + seed * 0.37) / period)
    start = k * period + 2.4 * lib.rand("blink", seed, k) - seed * 0.37
    u = (t - start) / 0.17
    return math.sin(math.pi * u) if 0 <= u <= 1 else 0.0


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "attempt_4818_3d.blend"))
    ap.add_argument("--frames", help="only build this range, e.g. 4000-4100 (for tests)")
    ap.add_argument("--anim", default=str(HERE / "anim.json"))
    args, _ = ap.parse_known_args(argv)
    rng = tuple(int(v) for v in args.frames.split("-")) if args.frames else None
    film = Film3D(json.loads(Path(args.anim).read_text()), rng)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = film.frames[0], film.frames[-1]
    scene.render.fps = FPS
    build(scene, film)
    bpy.ops.wm.save_as_mainfile(filepath=args.out, compress=True)
    print("saved", args.out, "frames", scene.frame_start, scene.frame_end)


# ============================================================================= build

def build(scene, film):
    chars = lib.collection("characters")
    env = lib.collection("environment")
    props = lib.collection("props")
    sweep_bike = lib.empty("sweep_bike", chars, loc=(0, 0, 60))
    sweep_percy = lib.empty("sweep_percy", chars, loc=(0, 0, 60))
    bike = Bike(chars, sweep_bike, M.outline("outline_bike", sweep_bike))
    percy = Percy(chars, sweep_percy, M.outline("outline_percy", sweep_percy))
    percy.root.parent = bike.root
    percy.root.location = SADDLE
    percy.hook_neck()
    gus = Gull(chars)
    mats = sets.Mats()
    sets.coast(env, mats)
    sets.town(env, mats)
    hill = sets.hill(env, mats, film.course)
    sets.beach(env, mats)
    sets.clouds(env)
    sets.bay(env, mats)
    flat = lambda x: 0.0
    sets.flowers(env, mats, [(sets.COAST_X - 40, sets.COAST_X + 90, 2.2, 6.0, flat),
                             (sets.COAST_X - 40, sets.COAST_X + 90, -2.2, -9.0, flat),
                             (sets.HILL_X - 30, sets.HILL_X + 60, -2.4, -14.0, hill.z)], count=500)
    sets.bushes(env, mats, [sets.HILL_X - 30 + 6.5 * k for k in range(22)], hill.z, (-16.0, -4.0), "hillbush")
    sets.bushes(env, mats, [sets.COAST_X - 30 + 7.0 * k for k in range(18)], flat, (-16.0, -6.0), "coastbush")
    sea, ocean = world.ocean(env, size=OCEAN_SIZE, resolution=13, loc=(0, 0, -0.25), repeat=OCEAN_REPEAT)
    world.far_sea(env, sea, inner=(-OCEAN_SIZE / 2 + 2, OCEAN_SIZE * OCEAN_REPEAT - OCEAN_SIZE / 2 - 2))
    haze_obj, haze_vol = world.haze(env, centre=(600, 0, 0), size=(1800.0, 900.0, 140.0))
    sky, _, sun = world.sky(scene, 9.0, SUN_DAY)
    world.setup_render(scene)
    world.compositor(scene, 0.55)
    spark = make_spark(props)
    fish = make_fish(props)
    duck = make_duck(props)
    umbrella = make_umbrella(props)
    leaves = make_leaves(props, percy)

    poses = bike_poses(film, hill)
    rig_lights(film, poses, chars)
    fx(film, poses, props)
    animate_bike(film, bike, poses)
    animate_percy(film, percy, bike, poses)
    animate_gus(film, gus, poses)
    animate_spark(film, spark, poses)
    animate_props(film, poses, fish, duck, umbrella, leaves, percy)
    animate_world(film, sea, sky, sun)
    animate_haze(film, haze_vol)
    animate_transformation(film, sweep_bike, sweep_percy, bike, percy)
    cameras(film, scene, poses, hill, percy)


# ============================================================================= motion

def bike_poses(film, hill):
    """World location and rotation of the bike (rear contact point) for every frame."""
    out = {}
    s7 = film.scenes["s07_learning"]["cues"]
    crash = film.cue("s07_learning", "crash")
    push = film.cue("s07_learning", "push")
    emerge = film.cue("s07_learning", "emerge")
    go = film.cue("s07_learning", "go")
    x_crash = None
    deck = hill.top - K * film.course["drop"] if film.course else 3.0
    x_end = sets.HILL_X + K * film.course["x_end"] if film.course else sets.HILL_X + 130
    land = film.cue("s11_beach", "land")
    touch = land + 1.7
    for r in film.a["frames"]:
        sc, T = r["scene"], r["f"] / FPS
        x, y = r["x"], r["y"]
        loc, rot = Vector((0, 0, 0)), Euler((0, 0, 0))
        if sc == "s06_transform":
            loc = Vector((sets.COAST_X, 0, 0))
        elif sc == "s07_learning":
            loc = Vector((sets.COAST_X + K * x, 0, 0))
            if push <= T < crash:
                u = (T - push) / (crash - push)
                loc.y = 1.5 * u ** 2.2
                rot = Euler((0.18 * math.sin(T * 9) * u, 0, 0.22 * u ** 2))
            elif crash <= T < go - 0.6:
                x_crash = x_crash or loc.x
                k = min(1.0, (T - crash) / 0.35)
                rise = lib.smoothstep(emerge - 0.2, emerge + 0.6, T)
                loc = Vector((x_crash + 0.3 * k, 1.5 + 0.6 * k, -0.15 * k * (1 - rise)))
                rot = Euler((1.15 * k * (1 - rise), 0.25 * k * (1 - rise), 0.22 + 0.2 * k * (1 - rise)))
            elif T >= go - 0.6:
                back = lib.smoothstep(go - 0.6, go + 0.4, T)
                base = Vector((x_crash or loc.x, 2.1, 0))
                loc = base.lerp(Vector((sets.COAST_X + K * x, 0.0, 0)), back)
                rot = Euler((0, 0, 0.22 * (1 - back)))
        elif sc == "s08_ride":
            loc = Vector((sets.TOWN_X + K * x, 0, 0))
        elif sc == "s09_hill":
            loc = Vector((sets.HILL_X + K * x, 0, hill.ground(x)))
            rot = Euler((0, r["slope"], 0))
        elif sc == "s10_flight":
            loc = Vector((x_end + K * x, 0, deck - K * y))
            rot = Euler((0, -0.08 * lib.smoothstep(film.cue("s10_flight", "wings"), film.cue("s10_flight", "soar"), T), 0))
        elif sc == "s11_beach":
            loc = Vector((sets.BEACH_X + K * x, 0, 0.12))
            if T < touch:
                u = (touch - T) / 1.7
                loc.z += 2.2 * u ** 1.6
                rot = Euler((0, -0.12 * u, 0))
        out[r["f"]] = (loc, rot)
    del s7
    return out


def percy_world(poses, f, offset=(0, 0, 0)):
    loc, rot = poses[f]
    return loc + rot.to_matrix() @ (SADDLE + Vector(offset))


def animate_bike(film, bike, poses):
    fr = film.frames
    lib.bake(bike.root, "location", fr, [poses[f][0] for f in fr])
    lib.bake(bike.root, "rotation_euler", fr, [poses[f][1] for f in fr])
    bike.animate(fr, [r["wheel"] for r in film.rows], [r["crank"] for r in film.rows])


def wing_state(film, r):
    """Which wing pose Percy holds in this frame: fold, grip, spread (flight) or admire."""
    sc, T = r["scene"], r["f"] / FPS
    if sc == "s06_transform":
        if film.cue(sc, "L22") - 0.2 <= T < film.cue(sc, "L23"):
            return "admire"
        if film.cue(sc, "L25") - 0.1 <= T < film.cue(sc, "L25.end") + 0.4:
            return "spread"
        return "fold"
    if sc == "s07_learning":
        crash, emerge, go = (film.cue(sc, c) for c in ("crash", "emerge", "go"))
        if crash <= T < emerge + 0.4:
            return "spread"
        if emerge + 0.4 <= T < go - 0.6:
            return "fold"
        if film.cue(sc, "L34") + 2.2 <= T < film.cue(sc, "L35.end"):
            return "spread"
        return "grip"
    if sc == "s10_flight":
        return "spread" if T >= film.cue(sc, "wings") else "grip"
    if sc == "s11_beach":
        land = film.cue(sc, "land")
        if T < land + 1.4:
            return "spread"
        if film.cue(sc, "L53") - 0.3 <= T < film.cue(sc, "rideoff") - 0.2:
            return "fold"
        return "grip"
    return "grip"


def animate_percy(film, percy, bike, poses):
    fr = film.frames
    body_loc, body_rot, head_rot, jaw, lids, pouch = [], [], [], [], [], []
    wings = {side: {k: [] for k in ("fold", "grip", "spread", "sh")} for side in (-1, 1)}
    pedals = {-1: [], 1: []}
    flap_phase = 0.0
    for r in film.rows:
        sc, T, t = r["scene"], r["f"] / FPS, r["t"]
        v = r["v"]
        pedal = 1.0 if v > 30 else 0.0
        bob = 0.006 * math.sin(2 * r["crank"]) * pedal
        lean = 0.03 + 0.14 * min(1.0, v / 2500)
        if sc == "s10_flight":
            lean = 0.08
        body_loc.append((0, 0, bob))
        body_rot.append((0.02 * math.sin(r["crank"]) * pedal, lean, 0))
        # where he looks: at the Model when she speaks, otherwise down the road
        yaw, pitch = 0.0, 0.05
        if r["jaw"]["MODEL"] > 0.02 or (sc in ("s06_transform", "s11_beach") and t > 2):
            yaw, pitch = -0.35, -0.12
        if sc == "s06_transform" and film.cue(sc, "L22") - 0.3 <= T < film.cue(sc, "L23"):
            yaw, pitch = -0.6, 0.55
        if sc == "s06_transform" and film.cue(sc, "L23") <= T < film.cue(sc, "L24"):
            yaw, pitch = 0.2, 0.7
        if sc == "s09_hill" and T >= film.cue(sc, "tip"):
            pitch = -0.05
        head_rot.append((0, pitch, yaw))
        jaw.append(0.34 * min(1.0, r["jaw"]["PERCY"] * 1.15))
        lids.append(max(blink(T, 1), 0.0))
        pouch.append(1.0 if sc == "s08_ride" and T >= film.cue(sc, "catch") else 0.0)
        state = wing_state(film, r)
        if state == "spread" and sc in ("s10_flight", "s11_beach", "s07_learning"):
            flap_phase += 2 * math.pi * (2.0 if sc != "s10_flight" else 1.4) / FPS * (
                0.05 if sc == "s10_flight" and T < film.cue(sc, "wings") else 1.0)
        for side in (-1, 1):
            w = wings[side]
            w["fold"].append(1.0 if state == "fold" else 0.0)
            w["grip"].append(1.0 if state == "grip" else 0.0)
            spread = state in ("spread", "admire") and (state != "admire" or side == -1)
            w["spread"].append(1.0 if spread else 0.0)
            if state == "spread":
                roll = side * (0.15 + 0.55 * math.sin(flap_phase)) if sc != "s06_transform" else side * -0.5
                w["sh"].append((roll, -0.1, 0.0))
            elif state == "admire" and side == -1:
                w["sh"].append((side * -0.9, 0.0, 0.9))
            else:
                w["sh"].append((0.0, 0.0, 0.0))
        for side in (-1, 1):
            pedals[side].append(bike.pedal_world(r["crank"], side) - SADDLE)
    lib.bake(percy.body_pivot, "location", fr, body_loc)
    lib.bake(percy.body_pivot, "rotation_euler", fr, body_rot)
    lib.bake(percy.head, "rotation_euler", fr, head_rot)
    lib.bake(percy.jaw, "rotation_euler", fr, [(0, j, 0) for j in jaw])
    for lid, side in percy.lids:
        lib.bake(lid, "rotation_euler", fr, [(percy.lid_angles(c)[side], 0, 0) for c in lids])
    keys = percy.pouch.data.shape_keys
    if keys:
        lib.bake(keys, 'key_blocks["full"].value', fr, pouch)
    for side in (-1, 1):
        w, objs = wings[side], percy.wings[side]
        for k in ("fold", "grip", "spread"):
            lib.bake(objs[k], "scale", fr, [(s, s, s) for s in w[k]])
        lib.bake(objs["shoulder"], "rotation_euler", fr, w["sh"])
    legs = percy.solve_legs(pedals)
    for side in (-1, 1):
        rows = legs[side]
        L = percy.legs[side]
        lib.bake(L["thigh"], "location", fr, [row[0] for row in rows])
        lib.bake(L["thigh"], "rotation_euler", fr, [row[1] for row in rows])
        lib.bake(L["shin"], "location", fr, [row[2] for row in rows])
        lib.bake(L["shin"], "rotation_euler", fr, [row[3] for row in rows])
        lib.bake(L["foot"], "location", fr, [row[4] + Vector((0, 0, -0.02)) for row in rows])


def animate_gus(film, gus, poses):
    fr = film.frames
    locs, rots, jaws, folds, spreads, shoulders = [], [], [], [], [], []
    post7 = Vector((sets.COAST_X + 4.0, 5.6, 1.52))
    post11 = Vector((sets.BEACH_X - 1.56, 3.2, 1.42))
    for r in film.rows:
        sc, T, t = r["scene"], r["f"] / FPS, r["t"]
        p = percy_world(poses, r["f"])
        flying = True
        face = 0.0
        if sc == "s07_learning":
            loc, flying = post7.copy(), False
            face = math.atan2(p.y - loc.y, p.x - loc.x)
            loc.z += 0.03 * abs(math.sin(T * 14)) * min(1.0, r["jaw"]["GUS"] * 3)
        elif sc == "s08_ride":
            loc = p + Vector((-1.2 + 0.4 * math.sin(T * 0.8), 2.4, 2.0 + 0.25 * math.sin(T * 2.1)))
        elif sc == "s09_hill" and T >= film.cue(sc, "pier") - 0.8:
            arrive = lib.smoothstep(film.cue(sc, "pier") - 0.8, film.cue(sc, "pier") + 0.5, T)
            loc = p + Vector((lib.lerp(-6.0, 2.2, arrive), 2.0, 2.4 + 0.2 * math.sin(T * 5)))
            face = math.pi * 0.0
        elif sc == "s10_flight" and T >= film.cue(sc, "soar") - 1.0:
            loc = p + Vector((-2.4, 3.2, 1.2 + 0.3 * math.sin(T * 1.7)))
        elif sc == "s11_beach":
            loc, flying = post11.copy(), False
            face = math.pi
        else:
            loc = Vector((0, 0, -50))    # off stage
        locs.append(loc)
        rots.append((0, 0, face))
        jaws.append(0.45 * min(1.0, r["jaw"]["GUS"] * 1.2))
        folds.append(0.0 if flying else 1.0)
        spreads.append(1.0 if flying else 0.0)
        flap = math.sin(T * 2 * math.pi * 2.6)
        shoulders.append((0.15 + 0.55 * flap) if flying else 0.0)
    lib.bake(gus.root, "location", fr, locs)
    lib.bake(gus.root, "rotation_euler", fr, rots)
    lib.bake(gus.jaw, "rotation_euler", fr, [(0, j, 0) for j in jaws])
    for side in (-1, 1):
        w = gus.wings[side]
        lib.bake(w["fold"], "scale", fr, [(s, s, s) for s in folds])
        lib.bake(w["spread"], "scale", fr, [(s, s, s) for s in spreads])
        lib.bake(w["shoulder"], "rotation_euler", fr, [(side * a, 0, 0) for a in shoulders])


# ============================================================================= the Model

def make_spark(col):
    root = lib.empty("spark", col, size=0.1)
    core = M.surface("spark_core", "#ffffff", emission="#bff4ff", strength=30.0)
    glow = M.surface("spark_rays", "#9fe6ff", emission="#7fdcff", strength=16.0)
    lib.ellipsoid("spark_core", (0.022, 0.022, 0.022), col, core, segs=12, rings=8, parent=root)
    for k in range(4):
        a = math.pi / 2 * k
        tip = Vector((math.cos(a) * 0.1, 0, math.sin(a) * 0.1))
        lib.tube(f"spark_ray_{k}", [(0, 0, 0), tip * 0.5, tip], [0.012, 0.004, 0.0005], col, glow, segs=8, parent=root)
    light = bpy.data.lights.new("spark_light", "POINT")
    light.color = (0.55, 0.88, 1.0)
    light.energy = 6.0
    light.shadow_soft_size = 0.05
    lo = bpy.data.objects.new("spark_light", light)
    lo.parent = root
    col.objects.link(lo)
    return root


def animate_spark(film, spark, poses):
    fr = film.frames
    locs, scales, rots = [], [], []
    for r in film.rows:
        sc, T = r["scene"], r["f"] / FPS
        p = percy_world(poses, r["f"])
        off = Vector((0.85 + 0.08 * math.sin(T * 0.9), -0.55, 1.2 + 0.06 * math.sin(T * 1.3)))
        if sc == "s06_transform" and T < film.cue(sc, "percy") + 1.8:
            # the Model *is* the renderer: it rides the sweep line up the bike, then up Percy
            b0, p0 = film.cue(sc, "bike"), film.cue(sc, "percy")
            if b0 <= T < b0 + 1.4:
                off = Vector((0.45, -0.6, -0.4 + 1.0 * (T - b0) / 1.4))
            elif p0 <= T < p0 + 1.8:
                off = Vector((0.3, -0.6, -0.1 + 1.25 * (T - p0) / 1.5))
        if sc == "s10_flight" and T < film.cue(sc, "wings"):
            off = Vector((0.55, -0.45, 1.15))
        e = 0.8 + 0.45 * r["jaw"]["MODEL"]
        locs.append(p + off)
        scales.append((e, e, e))
        rots.append((0, T * 0.6, 0))
    lib.bake(spark, "location", fr, locs)
    lib.bake(spark, "scale", fr, scales)
    lib.bake(spark, "rotation_euler", fr, rots)


# ============================================================================= props

def make_fish(col):
    silver = M.surface("fish", "#b8c4cc", rough=0.25, metal=0.6, coat=0.6)
    root = lib.empty("fish", col, loc=(0, 0, -50), size=0.05)
    lib.ellipsoid("fish_body", (0.12, 0.025, 0.04), col, silver, segs=14, rings=8, parent=root)
    lib.mesh_object("fish_tail", [(-0.11, 0, 0), (-0.18, 0, 0.04), (-0.18, 0, -0.04)], [(0, 1, 2)], col, silver,
                    smooth=False, parent=root)
    return root


def make_duck(col):
    yellow = M.surface("duck", "#ffd23a", rough=0.3, coat=0.6)
    orange = M.surface("duck_bill", "#f58a1f", rough=0.3, coat=0.6)
    root = lib.empty("duck", col, size=0.05)
    lib.ellipsoid("duck_body", (0.07, 0.05, 0.045), col, yellow, segs=16, rings=10, parent=root)
    lib.ellipsoid("duck_head", (0.035, 0.035, 0.035), col, yellow, segs=14, rings=8, loc=(0.045, 0, 0.055), parent=root)
    lib.ellipsoid("duck_bill", (0.025, 0.018, 0.008), col, orange, segs=10, rings=6, loc=(0.08, 0, 0.05), parent=root)
    return root


def make_umbrella(col):
    cloth = M.surface("umbrella", "#e8434f", rough=0.55, sss=0.2)
    root = lib.empty("umbrella", col, size=0.1)
    canopy = lib.empty("umbrella_canopy", col, parent=root, size=0.05)
    verts, faces = [(0, 0, 0.0)], []
    for k in range(16):
        a = math.tau * k / 16
        verts.append((math.cos(a) * 0.55, math.sin(a) * 0.55, -0.22))
    for k in range(16):
        faces.append((0, 1 + k, 1 + (k + 1) % 16))
    lib.mesh_object("umbrella_cloth", verts, faces, col, cloth, smooth=False, parent=canopy)
    lib.cylinder("umbrella_shaft", (0, 0, 0.02), (0, 0, -0.75), 0.008, col, M.surface("umbrella_shaft", "#333333"),
                 parent=root)
    return root


def make_leaves(col, percy):
    leaf = M.surface("leaf", "#5aa337", rough=0.6, sss=0.3)
    out = []
    for k in range(5):
        o = lib.ellipsoid(f"head_leaf_{k}", (0.03, 0.012, 0.004), col, leaf, segs=8, rings=4,
                          loc=(-0.02 + 0.03 * k, (k - 2) * 0.02, 0.11), parent=percy.head)
        o.rotation_euler = (0.3 * k, 0.5, 0.7 * k)
        out.append(o)
    return out


def animate_props(film, poses, fish, duck, umbrella, leaves, percy):
    fr = film.frames
    s8, s9, s7 = "s08_ride", "s09_hill", "s07_learning"
    # the fish leaps from the harbour and lands in the pouch
    f_locs, f_rots, d_s, d_locs, u_s, u_locs, u_rot, l_s = [], [], [], [], [], [], [], []
    for r in film.rows:
        sc, T = r["scene"], r["f"] / FPS
        p = percy_world(poses, r["f"])
        loc = Vector((0, 0, -50))
        rot = (0, 0, 0)
        if sc == s8:
            a, b = film.cue(sc, "fish"), film.cue(sc, "catch")
            if a <= T <= b:
                u = (T - a) / (b - a)
                bill = percy_world(poses, r["f"], (0.62, 0.0, 0.95))
                start = Vector((bill.x - 1.2, 6.0, -0.3))
                loc = start.lerp(bill, u) + Vector((0, 0, 2.4 * math.sin(math.pi * u)))
                rot = (0, -2.5 * u + 1.0, 0)
        f_locs.append(loc)
        f_rots.append(rot)
        on = sc == s9 and film.cue(sc, "duck") <= T < film.cue(sc, "umbrella") + 0.4
        pop = lib.smoothstep(film.cue(s9, "duck"), film.cue(s9, "duck") + 0.25, T) if on else 0.0
        d_s.append((pop, pop, pop))
        d_locs.append(percy_world(poses, r["f"], (0.36, 0.0, 0.26)) if on else Vector((0, 0, -50)))
        uon = sc == s9 and film.cue(sc, "umbrella") <= T < film.cue(sc, "pier")
        if uon:
            k = T - film.cue(s9, "umbrella")
            open_ = lib.smoothstep(0.0, 0.35, k)
            flip = lib.smoothstep(0.8, 1.0, k)
            away = max(0.0, k - 1.0)
            u_s.append((open_, open_, open_ * (1 - 2 * flip)))
            u_locs.append(percy_world(poses, r["f"], (0.1 - 3.0 * away, 0.0, 1.45 + 1.5 * away)))
            u_rot.append((0.3 * away, -0.5 * away, 0))
        else:
            u_s.append((0, 0, 0))
            u_locs.append(Vector((0, 0, -50)))
            u_rot.append((0, 0, 0))
        lon = sc == s7 and film.cue(s7, "crash") + 0.3 <= T < film.cue(s7, "go") + 2.5
        l_s.append((1, 1, 1) if lon else (0, 0, 0))
    lib.bake(fish, "location", fr, f_locs)
    lib.bake(fish, "rotation_euler", fr, f_rots)
    lib.bake(duck, "location", fr, d_locs)
    lib.bake(duck, "scale", fr, d_s)
    canopy = bpy.data.objects["umbrella_canopy"]
    lib.bake(umbrella, "location", fr, u_locs)
    lib.bake(umbrella, "rotation_euler", fr, u_rot)
    lib.bake(canopy, "scale", fr, u_s)
    for o in leaves:
        lib.bake(o, "scale", fr, l_s)


# ============================================================================= lights and effects

def rig_lights(film, poses, col):
    """A soft fill from the camera side and a rim from behind, travelling with Percy,
    so he always separates from the background (cool by day, warm at sunset)."""
    fill = bpy.data.lights.new("fill", "AREA")
    fill.size = 2.5
    rim = bpy.data.lights.new("rim", "AREA")
    rim.size = 1.2
    lights = []
    for light, off in ((fill, (1.2, -3.0, 1.6)), (rim, (-1.0, 2.2, 2.0))):
        o = bpy.data.objects.new(light.name, light)
        col.objects.link(o)
        lights.append((o, Vector(off)))
    fr = film.frames
    for o, off in lights:
        locs, rots = [], []
        for f in fr:
            p = percy_world(poses, f, (0.3, 0, 0.8))
            locs.append(p + off)
            rots.append((-off).to_track_quat("-Z", "Y").to_euler())
        lib.bake(o, "location", fr, locs)
        lib.bake(o, "rotation_euler", fr, rots)
    for sc in SKY:
        a, b = film.scene_range(sc)
        if b < fr[0] or a > fr[-1]:
            continue
        sunset = sc in ("s09_hill", "s10_flight", "s11_beach")
        for f in (max(a, fr[0]), min(b, fr[-1])):
            fill.energy = 120.0 if sunset else 60.0
            fill.color = (1.0, 0.78, 0.6) if sunset else (0.85, 0.9, 1.0)
            rim.energy = 260.0 if sunset else 160.0
            rim.color = (1.0, 0.62, 0.35) if sunset else (0.9, 0.95, 1.0)
            for light in (fill, rim):
                light.keyframe_insert("energy", frame=f)
                light.keyframe_insert("color", frame=f)


def burst(name, col, mat, film, frame0, origin, n, speed, up, life, size, spread=1.0, gravity=9.8, seed=0):
    """A spray of little pieces (leaves, sand, droplets) thrown from a point, falling and fading."""
    fr = [f for f in film.frames]
    src = lib.ellipsoid(name + "_src", (size, size * 0.7, size * 0.35), col, mat, segs=8, rings=5)
    src.hide_render = src.hide_viewport = True
    for i in range(n):
        o = bpy.data.objects.new(f"{name}_{i}", src.data)
        col.objects.link(o)
        a = math.tau * lib.rand(name, i, seed)
        v = Vector((math.cos(a) * spread * speed * (0.4 + lib.rand(name, i, "v")),
                    math.sin(a) * spread * speed * (0.4 + lib.rand(name, i, "w")),
                    up * (0.5 + lib.rand(name, i, "u"))))
        locs, scales, rots = [], [], []
        for f in fr:
            t = (f - frame0) / FPS
            if 0 <= t <= life:
                p = Vector(origin) + v * t + Vector((0, 0, -0.5 * gravity * t * t))
                p.z = max(p.z, Vector(origin).z - 0.4)
                s = 1.0 - (t / life) ** 3
            else:
                p, s = Vector((0, 0, -50)), 0.0
            locs.append(p)
            scales.append((s, s, s))
            rots.append((t * 7 * lib.rand(name, i, "r"), t * 5, 0))
        lib.bake(o, "location", fr, locs)
        lib.bake(o, "scale", fr, scales)
        lib.bake(o, "rotation_euler", fr, rots)


def fx(film, poses, col):
    leaf = M.surface("fx_leaf", "#5aa337", rough=0.6, sss=0.3)
    sand = M.surface("fx_sand", "#e2c48f", rough=0.9)
    drop = M.surface("fx_drop", "#e8f6ff", rough=0.05, spec=0.9, coat=1.0)
    s7, s8, s11 = "s07_learning", "s08_ride", "s11_beach"
    crash = film.f(s7, "crash")
    burst("fx_leaves", col, leaf, film, crash, percy_world(poses, crash, (0.4, 0.3, 0.6)), 34, 2.4, 3.2, 1.6, 0.035)
    emerge = film.f(s7, "emerge")
    burst("fx_leaves2", col, leaf, film, emerge, percy_world(poses, emerge, (0.3, 0.0, 1.0)), 18, 1.6, 2.6, 1.4, 0.03,
          seed=1)
    fish = film.f(s8, "fish")
    bill = percy_world(poses, fish, (0.62, 0.0, 0.95))
    burst("fx_splash", col, drop, film, fish, (bill.x - 1.2, 6.0, -0.2), 40, 1.2, 4.2, 1.1, 0.02)
    touch = int(round((film.cue(s11, "land") + 1.7) * FPS))
    burst("fx_sand", col, sand, film, touch, percy_world(poses, touch, (-0.3, 0.0, -0.4)), 60, 1.8, 2.4, 1.2, 0.018,
          seed=2)


# ============================================================================= world over time

SKY = {   # scene: (sun elevation at start, at end, azimuth)
    "s06_transform": (8.0, 9.5, SUN_DAY),
    "s07_learning": (22.0, 24.0, SUN_DAY),
    "s08_ride": (30.0, 30.0, SUN_DAY),
    "s09_hill": (9.0, 3.5, SUN_SET),
    "s10_flight": (3.2, 2.6, SUN_SET),
    "s11_beach": (2.4, 0.8, SUN_SET),
}
OCEAN_SIZE, OCEAN_REPEAT = 80, 5
# where each scene's simulated sea is centred (the tile spans OCEAN_SIZE * OCEAN_REPEAT metres)
OCEAN = {"s06_transform": (10, 208), "s07_learning": (10, 208), "s08_ride": (210, 203), "s09_hill": (560, 100),
         "s10_flight": (600, 120), "s11_beach": (1150, 205)}


def animate_world(film, sea, sky, sun):
    fr = film.frames
    ocean_t, ocean_loc = [], []
    for r in film.rows:
        sc = r["scene"]
        ocean_t.append(r["tw"] + 7.0)
        cx, cy = OCEAN[sc]
        shift = OCEAN_SIZE * OCEAN_REPEAT / 2 - OCEAN_SIZE / 2
        ocean_loc.append((cx - shift, cy - shift, -0.25))
    lib.bake(sea, 'modifiers["Ocean"].time', fr, ocean_t)
    lib.bake(sea, "location", fr, ocean_loc, interp="CONSTANT")
    owner_e, path_e = world.sky_socket_or_prop(sky, "sun_elevation")
    owner_r, path_r = world.sky_socket_or_prop(sky, "sun_rotation")
    for sc, (e0, e1, az) in SKY.items():
        a, b = film.scene_range(sc)
        a, b = max(a, fr[0]), min(b, fr[-1])
        if a > b:
            continue
        for f, e in ((a, e0), (b, e1)):
            if owner_e is not None:
                setattr(owner_e, path_e, math.radians(e))
                owner_e.keyframe_insert(path_e, frame=f)
                setattr(owner_r, path_r, math.radians(az))
                owner_r.keyframe_insert(path_r, frame=f)
            world.aim_sun(sun, e, az)
            sun.keyframe_insert("rotation_euler", frame=f)
            sun.data.keyframe_insert("energy", frame=f)
            sun.data.keyframe_insert("color", frame=f)


HAZE = {"s06_transform": 0.0003, "s07_learning": 0.00012, "s08_ride": 0.00012, "s09_hill": 0.00038,
        "s10_flight": 0.00034, "s11_beach": 0.0004}


def animate_haze(film, vol):
    """Clear air by day; thicker golden air at sunset, so the low sun throws shafts past Percy."""
    sock = vol.inputs["Density"]
    for sc, d in HAZE.items():
        a, b = film.scene_range(sc)
        for f in (max(a, film.frames[0]), min(b, film.frames[-1])):
            if f < film.frames[0] or f > film.frames[-1]:
                continue
            sock.default_value = d
            sock.keyframe_insert("default_value", frame=f)


def animate_transformation(film, sweep_bike, sweep_percy, bike, percy):
    """Flat drawing until the Model renders the bike (cue 'bike'), then Percy (cue 'percy')."""
    sc = "s06_transform"
    first = film.frames[0]
    b0, p0 = film.f(sc, "bike"), film.f(sc, "percy")
    for obj, f0, z0, z1, dur in ((sweep_bike, b0, -0.1, 1.1, 1.4), (sweep_percy, p0, 0.0, 1.9, 1.5)):
        for f, z in ((first, z0), (f0, z0), (f0 + int(dur * FPS), z1), (f0 + int(dur * FPS) + 1, 60.0)):
            obj.location = (0, 0, z)
            obj.keyframe_insert("location", index=2, frame=f)
    done = p0 + int(2.0 * FPS)
    for o in list(bike.parts) + list(percy.meshes):
        mod = o.modifiers.get("Outline") if o.type == "MESH" else None
        if mod is None:
            continue
        for f, on in ((first, True), (done, False)):
            mod.show_render = on
            mod.show_viewport = on
            o.keyframe_insert(f'modifiers["Outline"].show_render', frame=f)
            o.keyframe_insert(f'modifiers["Outline"].show_viewport', frame=f)


# ============================================================================= cameras

class Shot:
    def __init__(self, name, a, b, place, lens=40.0, fstop=4.0):
        self.name, self.a, self.b, self.place, self.lens, self.fstop = name, a, b, place, lens, fstop


def cameras(film, scene, poses, hill, percy):
    col = lib.collection("cameras")
    F = film.f

    def P(f, off=(0, 0, 0)):
        return percy_world(poses, f, off)

    def track(off, look=(0.35, 0, 0.75), orbit=None):
        def place(f, u):
            o = Vector(off)
            if orbit:
                a0, a1, rad = orbit
                a = lib.lerp(a0, a1, u)
                o = Vector((math.cos(a) * rad, math.sin(a) * rad, off[2]))
            return P(f) + o, P(f, look)
        return place

    def fixed(pos, look_off=(0.35, 0, 0.75)):
        return lambda f, u: (Vector(pos), P(f, look_off))

    s6, s7, s8, s9, s10, s11 = ("s06_transform", "s07_learning", "s08_ride", "s09_hill", "s10_flight", "s11_beach")
    x_hedge = poses[F(s7, "crash")][0]
    shots = [
        Shot("s06_reveal", F(s6, "peel"), F(s6, "percy", 2.6), track((0.55, -3.9, 0.92), (0.5, 0, 0.62)), 50, 5.6),
        Shot("s06_feathers", F(s6, "percy", 2.6), F(s6, "L24"),
             track((0, 0, 0.95), (0.25, 0, 0.8), orbit=(-1.75, -0.7, 2.6)), 40, 2.8),
        Shot("s06_twoshot", F(s6, "L24"), F(s6, "L26"), track((2.3, -2.2, 1.25), (0.2, 0, 0.85)), 45, 2.8),
        Shot("s06_ride_it", F(s6, "L26"), F(s6, "title"), track((1.3, -2.4, 0.9), (0.3, 0, 0.8)), 50, 2.8),
        Shot("s06_title", F(s6, "title"), film.scene_range(s6)[1], track((-5.0, -11.0, 3.2), (2.0, 0, 0.6)), 24, 8),
        Shot("s07_wobble", film.scene_range(s7)[0], F(s7, "crash", -0.25), track((1.0, -4.6, 1.0), (0.4, 0, 0.6)), 40, 4),
        Shot("s07_crash", F(s7, "crash", -0.25), F(s7, "L30"),
             fixed(x_hedge + Vector((2.6, -3.0, 0.7)), (0.3, 0, 0.3)), 35, 4),
        Shot("s07_gus", F(s7, "L30"), F(s7, "emerge", -0.2),
             lambda f, u: (Vector((sets.COAST_X + 5.3, 4.0, 1.85)), Vector((sets.COAST_X + 4.0, 5.6, 1.65))), 55, 2.8),
        Shot("s07_emerge", F(s7, "emerge", -0.2), F(s7, "go", 1.0),
             fixed(x_hedge + Vector((1.2, -3.2, 1.3)), (0.3, 0, 0.8)), 40, 4),
        Shot("s07_doing_it", F(s7, "go", 1.0), film.scene_range(s7)[1], track((2.7, -2.3, 0.45), (0.3, 0, 0.9)), 28, 4),
        Shot("s08_town", film.scene_range(s8)[0], F(s8, "fish", -0.6), track((0.2, -5.6, 1.3), (0.4, 0, 0.9)), 35, 5.6),
        Shot("s08_fish", F(s8, "fish", -0.6), F(s8, "catch", 0.9), track((1.6, -3.4, 1.0), (0.6, 1.0, 1.1)), 30, 5.6),
        Shot("s08_my_fish", F(s8, "catch", 0.9), film.scene_range(s8)[1], track((1.5, -2.3, 1.5), (0.5, 0, 1.2)), 40, 2.8),
        Shot("s09_climb", film.scene_range(s9)[0], F(s9, "crest", 0.6), track((-3.2, -2.6, 0.9), (2.0, 0, 0.9)), 32, 5.6),
        Shot("s09_crest", F(s9, "crest", 0.6), F(s9, "tip"), track((-2.6, 1.6, 1.9), (12.0, 4.5, -3.2)), 28, 8),
        Shot("s09_descent", F(s9, "tip"), F(s9, "duck"), track((3.6, -1.6, 0.6), (0.3, 0, 0.85)), 28, 4),
        Shot("s09_duck", F(s9, "duck"), F(s9, "umbrella"), track((1.7, -1.5, 1.05), (0.45, 0, 0.75)), 35, 2.8),
        Shot("s09_umbrella", F(s9, "umbrella"), F(s9, "pier"), track((0.3, -6.4, 1.8), (0.4, 0, 1.0)), 35, 5.6),
        Shot("s09_pier", F(s9, "pier"), film.scene_range(s9)[1], track((5.5, -1.3, 0.5), (0.3, 0, 0.9)), 24, 5.6),
        Shot("s10_slowmo", film.scene_range(s10)[0], F(s10, "wings"),
             track((0, 0, 0.25), (0.35, 0, 0.85), orbit=(-1.9, -1.2, 3.6)), 50, 2.8),
        # backlit: the camera looks along the sun's direction, so he spreads his wings against it
        Shot("s10_hero", F(s10, "wings"), F(s10, "soar"), track((-2.7, -1.7, 0.35), (0.3, 0, 0.95)), 30, 4),
        Shot("s10_soar", F(s10, "soar"), film.scene_range(s10)[1], track((-7.5, -6.5, 2.4), (1.0, 0, 0.8)), 35, 8),
        Shot("s11_landing", film.scene_range(s11)[0], F(s11, "land", 3.2),
             lambda f, u: (Vector((sets.BEACH_X + 6.0, -4.8, 0.55)), P(f, (0.3, 0, 0.6))), 32, 5.6),
        Shot("s11_talk", F(s11, "land", 3.2), F(s11, "rideoff"), track((2.6, -2.2, 1.0), (0.25, 0, 0.9)), 45, 2.8),
        Shot("s11_rideoff", F(s11, "rideoff"), film.scene_range(s11)[1],
             lambda f, u: (Vector((sets.BEACH_X + 1.0, -1.7, 1.35)), P(f, (0.3, 0, 0.7))), 35, 5.6),
    ]
    lo, hi = film.frames[0], film.frames[-1]
    for s in shots:
        a, b = max(s.a, lo), min(s.b, hi)
        if a > b:
            continue
        cam = bpy.data.objects.new("cam_" + s.name, bpy.data.cameras.new("cam_" + s.name))
        col.objects.link(cam)
        cam.data.lens = s.lens
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = s.fstop
        cam.data.clip_end = 6000
        frames = list(range(a, b + 1))
        locs, rots, focus = [], [], []
        for f in frames:
            u = (f - s.a) / max(1, s.b - s.a)
            pos, target = s.place(f, u)
            locs.append(pos)
            d = target - pos
            rots.append(d.to_track_quat("-Z", "Y").to_euler())
            focus.append((P(f, (0.4, 0, 0.9)) - pos).length)
        # unwrap the euler angles so interpolation never spins the long way round
        for i in range(1, len(rots)):
            for c in range(3):
                while rots[i][c] - rots[i - 1][c] > math.pi:
                    rots[i][c] -= 2 * math.pi
                while rots[i][c] - rots[i - 1][c] < -math.pi:
                    rots[i][c] += 2 * math.pi
        lib.bake(cam, "location", frames, locs)
        lib.bake(cam, "rotation_euler", frames, rots)
        lib.bake(cam.data, "dof.focus_distance", frames, focus)
        m = scene.timeline_markers.new(s.name, frame=a)
        m.camera = cam
        if scene.camera is None:
            scene.camera = cam


if __name__ == "__main__":
    main()
