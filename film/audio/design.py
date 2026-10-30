"""Sound design, scene by scene. Physical sounds are computed from the same motion the
animation uses: freewheel clicks per pawl crossing, plank thumps per seam, chain whir
from cadence, wind from speed, wing whooshes on each downstroke."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import sfx
from . import synth as S
from .synth import SR
from .. import bicycle as bk


@dataclass
class E:
    t: float                  # global seconds
    audio: np.ndarray         # mono or (n, 2)
    gain: float = 1.0
    pan: float = 0.0
    send: float = 0.15


def _ctx(film, name):
    from ..film import Ctx
    st = next(s for s in film.timeline.scenes if s.name == name)
    return st, Ctx(film, st, 0.0, st.start, film.fps)


def _freewheel(motion, t0, t1, geo=bk.PERCY, pawls=24):
    """Click times where the hub's pawls pass a ratchet tooth (wheel turning faster
    than the cranks drive it)."""
    m = motion
    mask = (m.t >= t0) & (m.t <= t1)
    ts = m.t[mask]
    rel = m.wheel[mask] - m.crank[mask] * geo.ratio
    step = 2 * math.pi / pawls
    idx = np.floor(rel / step)
    hits = np.nonzero(np.diff(idx) > 0)[0]
    omega = np.gradient(m.wheel[mask], m.dt)
    return ts[hits + 1], np.clip(0.25 + omega[hits + 1] / 40, 0.25, 1.0)


def _cadence(motion, t0, t1):
    m = motion
    mask = (m.t >= t0) & (m.t <= t1)
    rev = np.gradient(m.crank[mask], m.dt) / (2 * math.pi)
    return m.t[mask], np.clip(rev, 0, None), m.v[mask]


def _curve(times, values, t0, length):
    """Resample a control curve onto audio samples starting at t0."""
    n = int(length * SR)
    ts = t0 + np.arange(n) / SR
    return np.interp(ts, times, values).astype(np.float32)


def ambience(film):
    """Continuous beds: room tone on the page, sea and gulls outside."""
    events = []
    tl = film.timeline
    scenes = {s.name: s for s in tl.scenes}
    outside = ["s06_transform", "s07_learning", "s08_ride", "s09_hill", "s10_flight", "s11_beach"]
    start = scenes["s06_transform"].start + scenes["s06_transform"].cues["peel"] + 1.0
    end = scenes["s11_beach"].start + scenes["s11_beach"].cues["lineart"] + 1.2
    dur = end - start
    bed = sfx.waves(dur, seed=1, level=1.0)
    bed *= np.minimum(1, np.arange(len(bed)) / (2.0 * SR))
    bed[-int(1.2 * SR):] *= np.linspace(1, 0, int(1.2 * SR))
    events.append(E(start, S.pan(bed, -0.3) + S.pan(sfx.waves(dur, seed=2), 0.3), 0.55, 0.0, 0.0))
    rng = S.rng("gulls")
    t = start + 2.0
    while t < end - 2:
        events.append(E(t, sfx.gull_call(int(rng.integers(0, 4))), 0.35, float(rng.uniform(-0.8, 0.8)), 0.4))
        if rng.random() < 0.5:
            events.append(E(t + 0.35, sfx.gull_call(int(rng.integers(0, 4))), 0.25, float(rng.uniform(-0.8, 0.8)), 0.4))
        t += rng.uniform(4.0, 9.0)
    for name in ("s02_attempt1", "s05_talk"):
        st = scenes[name]
        hum = S.lowpass(S.pink(int((st.duration + 0.5) * SR), ("room", name)), 300) * 0.05
        events.append(E(st.start, hum, 1.0, 0.0, 0.0))
    del outside
    return events


def scene_events(film):
    ev = []
    ev += ambience(film)

    # 1. Prompt: keys, enter, a swoosh up, data trickling, the zoom
    st, ctx = _ctx(film, "s01_prompt")
    from ..scenes import s01_prompt as s1
    for i, k in enumerate(s1.typing_times(st.cues["type"])):
        ev.append(E(st.start + k, sfx.key_click(i), 0.55, -0.1 + 0.02 * (i % 5), 0.05))
    ev.append(E(st.start + st.cues["send"], sfx.enter_key(), 0.7, 0.0, 0.05))
    ev.append(E(st.start + st.cues["send"] + 0.05, sfx.whoosh(0.5, 400, 4000, seed=1, peak=0.4), 0.35, 0.1, 0.2))
    ev.append(E(st.start + st.cues["send"] + 0.4, sfx.shimmer(1.0, seed=1, count=10), 0.25, -0.4, 0.4))
    code = st.cues["code"]
    for k in range(int(2.2 * 14)):
        ev.append(E(st.start + code + k / 14, sfx.tick(5000 + 600 * (k % 4)), 0.18, 0.2, 0.05))
    ev.append(E(st.start + st.cues["zoom"] - 0.2, sfx.whoosh(1.2, 200, 6000, seed=2, peak=0.75), 0.8, 0.0, 0.3))

    # 2. Attempt 1: shapes pop in on a D-major arpeggio; the wheel's slide whistle; clatter; eraser
    st, ctx = _ctx(film, "s02_attempt1")
    from ..scenes import s02_attempt1 as s2
    notes = [62, 66, 69, 74, 78, 81, 86, 78, 81, 86, 90]
    for i, name in enumerate(s2.ORDER):
        t = st.start + st.cues["build"] + i * s2.POP
        ev.append(E(t, sfx.pop(S.midi_hz(notes[i])), 0.32, (s2.ANCHORS[name][0] - 960) / 1400, 0.2))
    roll = st.cues["roll"]
    ev.append(E(st.start + roll + 0.2, sfx.slide_whistle(1400, 300, 2.6), 0.6, 0.6, 0.3))
    ev.append(E(st.start + st.cues["clatter"], sfx.clatter(), 0.6, 0.95, 0.5))
    ev.append(E(st.start + st.cues["erase"], sfx.eraser(0.7), 0.6, 0.0, 0.2))
    ev.append(E(st.start + st.cues["erase"], sfx.whoosh(0.7, 300, 3000, seed=3), 0.4, 0.0, 0.2))

    # 3. Attempt 2: the scanline render, the head-turn squeak, a happy boing
    st, ctx = _ctx(film, "s03_attempt2")
    ev.append(E(st.start + st.cues["draw"], sfx.scan(1.5), 0.5, 0.0, 0.2))
    ev.append(E(st.start + st.cues["turn"] + 0.1, sfx.squeak(2), 0.25, -0.05, 0.1))
    ev.append(E(st.start + st.cues["L08"] + 0.05, sfx.boing(260), 0.4, 0.4, 0.2))

    # 4. Montage: a pop per gag, its own stinger, and the counter spinning
    st, ctx = _ctx(film, "s04_montage")
    stingers = {"g1": sfx.thud(110, 0.25), "g2": sfx.boing(150), "g3": sfx.rustle(0.4, 5, 2.0),
                "g4": sfx.squeak(0), "g5": sfx.scan(0.4), "g6": sfx.splash(), "g7": sfx.crunch()}
    for cue, number, kind in __import__("film.scenes.s04_montage", fromlist=["GAGS"]).GAGS:
        t = st.start + st.cues[cue]
        ev.append(E(t, sfx.pop(500), 0.4, 0.0, 0.1))
        ev.append(E(t + 0.05, stingers[cue], 0.32, 0.0, 0.2))
        for k in range(6):
            ev.append(E(t - 0.15 + k * 0.025, sfx.tick(4200), 0.15, 0.8, 0.0))
    spin = st.cues["spin"]
    tt = 0.0
    while tt < 1.2:
        ev.append(E(st.start + spin + tt, sfx.tick(4500), 0.2, 0.8, 0.0))
        tt += 0.07 * (1 - 0.6 * math.sin(math.pi * tt / 1.2))

    # 5. Attempt 4,817: a flap of exasperation, kicking feet, a rising hum for "hold on"
    st, ctx = _ctx(film, "s05_talk")
    ev.append(E(st.start + st.cues["L14"] - 0.1, sfx.flap(1, 1.4), 0.7, 0.0, 0.2))
    ev.append(E(st.start + st.cues["L14.end"] + 0.2, sfx.flap(2, 1.2), 0.5, 0.0, 0.2))
    for k in range(5):
        ev.append(E(st.start + st.cues["L15"] + 0.2 + k * 0.35, sfx.whoosh(0.18, 300, 1200, seed=10 + k, peak=0.5),
                    0.18, -0.1, 0.1))
    ev.append(E(st.start + st.cues["L21"] + 0.3, sfx.rise(st.duration - st.cues["L21"], 120, 900), 0.5, 0.0, 0.4))

    # 6. Transformation: tear, reveal boom, spokes ping in, chain links, the bell, the ruffle
    st, ctx = _ctx(film, "s06_transform")
    c = st.cues
    ev.append(E(st.start + c["glow"], sfx.shimmer(1.2, seed=2, count=30), 0.35, 0.0, 0.5))
    ev.append(E(st.start + c["peel"], sfx.tear(c["world"] - c["peel"]), 0.7, 0.0, 0.3))
    ev.append(E(st.start + c["peel"], sfx.whoosh(c["world"] - c["peel"] + 0.4, 100, 5000, seed=4, peak=0.8), 0.6, 0.0, 0.4))
    ev.append(E(st.start + c["world"], sfx.thud(45, 1.2), 0.5, 0.0, 0.5))
    c0 = c["bike"]
    for i in range(18):
        appear = c0 + 0.8 + 1.8 * ((i * 7) % 18) / 18
        f = S.midi_hz(74 + [0, 4, 7, 12, 16, 19][i % 6])
        ev.append(E(st.start + appear, sfx.spoke_ping(f), 0.35, -0.3 + 0.6 * (i % 2), 0.4))
    for k in range(30):
        ev.append(E(st.start + c0 + 2.0 + k / 30, sfx.tick(2600 + 200 * (k % 3)), 0.3, -0.1, 0.1))
    ev.append(E(st.start + c0 + 3.4, sfx.bike_bell(), 0.6, 0.1, 0.3))
    ev.append(E(st.start + c["percy"], sfx.shimmer(1.0, seed=5, count=26, lo=3000, hi=8000), 0.4, 0.0, 0.5))
    ev.append(E(st.start + c["percy"] + 0.95, sfx.flap(5, 0.8), 0.6, -0.05, 0.1))
    ev.append(E(st.start + c["percy"] + 1.05, sfx.flap(6, 0.6), 0.5, -0.05, 0.1))
    ev.append(E(st.start + c["L23"] + 0.3, sfx.bike_bell(), 0.45, 0.1, 0.3))

    # 7. Learning: chain and tyres from the motion, the crash, a wheel freewheeling in the hedge
    st, ctx = _ctx(film, "s07_learning")
    from ..scenes import s07_learning as s7
    m = s7._motion(ctx)
    c = st.cues
    ts, cad, v = _cadence(m, 0, c["crash"])
    seg = c["crash"]
    ev.append(E(st.start, sfx.chain_whir(seg, _curve(ts, cad, 0, seg)), 0.5, -0.1, 0.05))
    ev.append(E(st.start, sfx.roll_noise(seg, _curve(ts, v / 900, 0, seg)), 0.5, -0.1, 0.05))
    ev.append(E(st.start + c["crash"] - 0.05, sfx.rustle(1.4, 1, 1.5), 0.9, 0.35, 0.2))
    ev.append(E(st.start + c["crash"], sfx.thud(80, 0.4), 0.45, 0.35, 0.2))
    ev.append(E(st.start + c["crash"] + 0.08, sfx.bike_bell(), 0.25, 0.35, 0.3))
    k = np.arange(0, 6.0, 1 / 240)
    spin = 8 * (1 - np.exp(-k * 0.8)) / 0.8
    clicks = [k[i] for i in range(1, len(k)) if math.floor(spin[i] / (2 * math.pi / 24)) > math.floor(spin[i - 1] / (2 * math.pi / 24))]
    clicks = [x for x in clicks if x < c["emerge"] - c["crash"]]
    ev.append(E(st.start + c["crash"], sfx.clicks(clicks, 6.0, sfx.tick(3200)), 0.35, 0.3, 0.05))
    ev.append(E(st.start + c["emerge"] - 0.05, sfx.rustle(0.6, 2, 2.0), 0.6, 0.2, 0.2))
    go = c["go"]
    ts, cad, v = _cadence(m, go, st.duration)
    seg = st.duration - go
    ev.append(E(st.start + go, sfx.chain_whir(seg, _curve(ts, cad, go, seg)), 0.32, 0.0, 0.05))
    ev.append(E(st.start + go, sfx.roll_noise(seg, _curve(ts, v / 900, go, seg)), 0.3, 0.0, 0.05))

    # 8. Ride: chain, tyres and breeze all the way; bell; the fish
    st, ctx = _ctx(film, "s08_ride")
    from ..scenes import s08_ride as s8
    m = s8._motion(ctx)
    c = st.cues
    ts, cad, v = _cadence(m, 0, st.duration)
    seg = st.duration
    ev.append(E(st.start, sfx.chain_whir(seg, _curve(ts, cad, 0, seg)), 0.32, -0.1, 0.05))
    ev.append(E(st.start, sfx.roll_noise(seg, _curve(ts, v / 900, 0, seg)), 0.3, -0.1, 0.05))
    ev.append(E(st.start, sfx.wind(seg, _curve(ts, v / 2600, 0, seg), seed=8), 0.12, 0.0, 0.0))
    for at in (0.6, 0.85):
        ev.append(E(st.start + c["bell"] + at, sfx.bike_bell(), 0.5, -0.1, 0.25))
    ev.append(E(st.start + c["fish"], sfx.splash(), 0.6, 0.6, 0.3))
    ev.append(E(st.start + c["fish"] + 0.1, sfx.whoosh(1.0, 400, 2500, seed=12, peak=0.5), 0.35, 0.3, 0.2))
    ev.append(E(st.start + c["catch"], sfx.gulp(), 0.5, -0.1, 0.1))
    for k in range(int(st.duration * 2.4)):
        ev.append(E(st.start + 0.2 + k / 2.4, sfx.flap(20 + k, 0.5), 0.12, 0.35, 0.1))

    # 9. Hill: effort, then a freewheel buzzing faster and faster, wind roar, plank thunder
    st, ctx = _ctx(film, "s09_hill")
    from ..scenes import s09_hill as s9
    course = s9.Course(ctx)
    m = course.m
    c = st.cues
    ts, cad, v = _cadence(m, 0, st.duration)
    seg = st.duration
    ev.append(E(st.start, sfx.chain_whir(c["crest"], _curve(ts, cad, 0, c["crest"])), 0.4, -0.1, 0.05))
    clicks_t, gains = _freewheel(m, c["crest"], st.duration)
    ev.append(E(st.start, sfx.clicks(list(clicks_t), seg, sfx.tick(3300), list(gains)), 0.45, -0.05, 0.03))
    wind_curve = _curve(ts, np.clip(v / 2500, 0, 1), 0, seg)
    ev.append(E(st.start, sfx.wind(seg, wind_curve, seed=9), 0.22, 0.0, 0.0))
    road = np.where(ts < 0, 0, 1)
    del road
    ev.append(E(st.start, sfx.roll_noise(seg, _curve(ts, np.clip(v / 2500, 0, 1) * (m.x[: len(ts)] < course.x_pier), 0, seg)),
                0.3, 0.0, 0.03))
    # plank seams under both tyres
    thumps = []
    xs = m.x
    for offset in (0.0, bk.PERCY.wheelbase):
        rel = (xs + offset - course.x_pier) / 46.0
        idx = np.floor(rel)
        crossings = np.nonzero((np.diff(idx) > 0) & (rel[1:] > 0))[0]
        thumps += [m.t[i + 1] for i in crossings if m.t[i + 1] < c["launch"]]
    thumps.sort()
    ev.append(E(st.start, sfx.clicks(thumps, seg, sfx.plank_thump(1)), 0.4, 0.0, 0.1))
    ev.append(E(st.start + c["duck"], sfx.shimmer(0.6, seed=9, count=14), 0.4, 0.2, 0.3))
    t = c["duck"] + 0.9
    while t < c["L44"]:
        phase = (t - c["duck"]) * 14
        if math.sin(phase) > 0.98:
            ev.append(E(st.start + t, sfx.squeak(int(t * 10) % 3), 0.55, 0.2, 0.15))
            t += 0.2
        t += 0.005
    u0 = c["umbrella"]
    ev.append(E(st.start + u0, sfx.shimmer(0.4, seed=10, count=10), 0.4, -0.2, 0.3))
    ev.append(E(st.start + u0 + 0.4, sfx.fwump(), 0.9, -0.2, 0.2))
    ev.append(E(st.start + u0 + 0.8, sfx.fabric_flip(), 0.8, -0.3, 0.2))
    ev.append(E(st.start + u0 + 1.0, sfx.whoosh(0.9, 300, 2500, rise=False, seed=13, peak=0.3), 0.5, -0.6, 0.2))
    for k in range(int((c["launch"] - c["pier"] + 0.8) * 5)):
        ev.append(E(st.start + c["pier"] - 0.8 + k / 5, sfx.flap(40 + k, 0.5), 0.15, 0.4, 0.1))
    ev.append(E(st.start + c["launch"] - 0.1, sfx.whoosh(0.8, 200, 4000, seed=14, peak=0.3), 0.6, 0.0, 0.3))

    # 10. Flight: a low hush in slow motion; the wings open with a roar of air; every downstroke whooshes
    st, ctx = _ctx(film, "s10_flight")
    from ..scenes import s10_flight as s10
    c = st.cues
    ev.append(E(st.start, sfx.drone(c["wings"] + 0.5, 41.2), 0.6, 0.0, 0.4))
    hush = S.lowpass(sfx.wind(c["wings"], np.full(int(c["wings"] * SR), 0.4), seed=15), 500)
    ev.append(E(st.start, hush, 0.6, 0.0, 0.2))
    ev.append(E(st.start + c["wings"] - 0.05, sfx.whoosh(1.0, 80, 2500, seed=16, peak=0.25), 1.0, 0.0, 0.3))
    ev.append(E(st.start + c["wings"], sfx.flap(60, 2.4), 0.9, 0.0, 0.3))
    t = c["wings"] + 0.75
    while t < st.duration:
        phase = (t - c["wings"]) * 2 * math.pi * 1.4 + math.pi / 2
        if math.sin(phase) < -0.995:
            ev.append(E(st.start + t, sfx.flap(int(t * 7), 1.6), 0.45, -0.05, 0.15))
            t += 0.3
        t += 0.004
    # he rushes past the camera: pitch up as he approaches, down as he goes (Doppler)
    dur = c["soar"] - c["wings"]
    n = int(dur * SR)
    u = np.arange(n) / n
    doppler = 1 + 0.35 * np.tanh((0.7 - u) * 6)
    rush = S.bandpass(S.pink(n, "rush"), 200, 3000)
    idx = np.clip(np.cumsum(doppler), 0, n - 1)
    rush = np.interp(idx, np.arange(n), rush) * np.exp(-((u - 0.7) ** 2) / 0.03) * 2.0
    ev.append(E(st.start + c["wings"], S.pan(rush.astype(np.float32), 0.0) * np.stack([1 - 0.4 * u, 0.6 + 0.4 * u], axis=1).astype(np.float32), 0.7, 0.0, 0.2))
    seg = st.duration - c["wings"]
    ev.append(E(st.start + c["wings"], sfx.wind(seg, np.full(int(seg * SR), 0.45), seed=17), 0.16, 0.0, 0.0))
    for k in range(int((st.duration - c["soar"]) * 3)):
        ev.append(E(st.start + c["soar"] + 1.0 + k / 3, sfx.flap(80 + k, 0.5), 0.12, 0.4, 0.1))
    del s10

    # 11. Beach: touchdown in sand, sand braking, the page closing in
    st, ctx = _ctx(film, "s11_beach")
    from ..scenes import s11_beach as s11
    c = st.cues
    touch = c["land"] + s11.TOUCH
    ev.append(E(st.start + c["land"], sfx.flap(90, 1.8), 0.4, -0.3, 0.2))
    ev.append(E(st.start + touch, sfx.thud(60, 0.4), 0.45, 0.0, 0.2))
    ev.append(E(st.start + touch, sfx.rustle(0.5, 11, 1.2), 0.4, 0.0, 0.1))
    n = int(1.6 * SR)
    sand = sfx.roll_noise(1.6, np.linspace(1, 0, n) ** 1.5, surface="sand", seed=3)
    ev.append(E(st.start + touch, sand, 0.9, 0.0, 0.1))
    m = s11._ride(ctx)
    ts, cad, v = _cadence(m, c["rideoff"], st.duration)
    seg = st.duration - c["rideoff"]
    ev.append(E(st.start + c["rideoff"], sfx.chain_whir(seg, _curve(ts, cad, c["rideoff"], seg)), 0.3, 0.3, 0.1))
    ev.append(E(st.start + c["lineart"], sfx.shimmer(1.6, seed=12, count=30), 0.45, 0.0, 0.5))
    ev.append(E(st.start + c["lineart"], sfx.whoosh(1.6, 200, 5000, rise=False, seed=18, peak=0.5), 0.5, 0.0, 0.4))

    # 12. Post-credits: the wheel rolls in, settles like Euler's disk, stops dead
    st, ctx = _ctx(film, "s12_credits")
    c = st.cues
    roll = c["wobble"] - c["post"]
    n = int(roll * SR)
    rumble = S.lowpass(S.brown(n, "wheelroll"), 300) * np.linspace(0.6, 1.0, n) * 0.8
    ev.append(E(st.start + c["post"], S.pan(rumble, 0.0) * np.stack([np.linspace(1.3, 0.7, n), np.linspace(0.3, 0.7, n)], axis=1).astype(np.float32), 1.0, 0.0, 0.1))
    ev.append(E(st.start + c["wobble"], sfx.euler_disk(2.0), 0.7, 0.0, 0.15))
    return ev


DIALOGUE_PAN = {
    "s01_prompt": {"MODEL": 0.0},
    "s07_learning": {"PERCY": 0.0, "GUS": -0.45, "MODEL": 0.25},
    "s08_ride": {"PERCY": -0.2, "GUS": 0.35, "MODEL": 0.25},
    "s09_hill": {"PERCY": -0.1, "GUS": 0.35, "MODEL": 0.3},
    "s10_flight": {"PERCY": 0.0, "GUS": 0.35, "MODEL": 0.25},
    "s11_beach": {"PERCY": -0.15, "GUS": -0.45, "MODEL": 0.25},
}
DEFAULT_PAN = {"PERCY": -0.08, "MODEL": 0.3, "GUS": 0.3}


def dialogue_pan(scene, who):
    return DIALOGUE_PAN.get(scene, {}).get(who, DEFAULT_PAN[who])
