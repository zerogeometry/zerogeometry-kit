"""Headless smoke test for ZeroGeometry Kit.
blender -b --factory-startup -P tests/test_headless.py
"""
import os, sys, math, wave, struct, tempfile
import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import zerogeometry_kit as zgk
zgk.register()
OUT = os.path.join(tempfile.gettempdir(), "zgk_test")
os.makedirs(OUT, exist_ok=True)
results = []
def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))

# ---------- scene: cube slides to the right, camera static ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 48
sc.render.fps = 24
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.zgk_output_dir = OUT + os.sep          # keep test output out of the user's Videos folder
bpy.ops.mesh.primitive_cube_add(size=0.5, location=(0, -1.5, 0))
cube = bpy.context.object
cube.keyframe_insert("location", frame=1)
cube.location.y = 1.5
cube.keyframe_insert("location", frame=48)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
sc.collection.objects.link(cam)
cam.location = (8, 0, 0)
cam.rotation_euler = (math.pi / 2, 0, math.pi / 2)
cam.data.lens = 35
sc.camera = cam
light = bpy.data.objects.new("L", bpy.data.lights.new("L", "SUN"))
sc.collection.objects.link(light)

# ---------- beat sync: synthetic 120 BPM click track ----------
wav = os.path.join(OUT, "click120.wav")
rate = 22050
with wave.open(wav, "w") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    n = rate * 8
    frames = bytearray()
    for i in range(n):
        t = i / rate
        ph = t % 0.5                                   # a click every 0.5 s = 120 BPM
        v = math.sin(2 * math.pi * 1800 * t) * math.exp(-ph * 60) if ph < 0.05 else 0.0
        frames += struct.pack("<h", int(v * 30000))
    w.writeframes(bytes(frames))
bpy.ops.zgk.beat_detect(filepath=wav, add_sound=True)
beats = zgk.beat.beat_frames(sc)
check("beat detect finds ~120 BPM", abs(sc.zgk_bpm - 120) < 3, f"{sc.zgk_bpm:.1f} BPM, {len(beats)} beats")
gaps = [b - a for a, b in zip(beats, beats[1:])]
check("beat spacing ~12 frames", gaps and all(11 <= g <= 13 for g in gaps), f"gaps {sorted(set(gaps))}")
bpy.ops.zgk.beat_grid(bpm=120)
check("beat grid", len(zgk.beat.beat_frames(sc)) == 4, f"{len(zgk.beat.beat_frames(sc))} markers in 48 frames")
for o in bpy.context.selected_objects: o.select_set(False)
cube.select_set(True)
bpy.context.view_layer.objects.active = cube
bpy.ops.zgk.beat_key(mode="HOP", amount=0.3, decay=6)
zs = [c.evaluate(4) for c in zgk.beat._fcurves(cube) if c.data_path == "location" and c.array_index == 2]
check("beat hop keys", zs and zs[0] > 0.05, f"z at frame 4 = {zs[0] if zs else None}")
cam2 = cam.copy(); cam2.data = cam.data.copy(); sc.collection.objects.link(cam2)
cam.select_set(True); cam2.select_set(True); cube.select_set(False)
bpy.ops.zgk.beat_cuts(every=1)
bound = [m for m in sc.timeline_markers if m.camera]
check("camera cuts on beats", len(bound) == 4 and {m.camera for m in bound} == {cam, cam2})
for m in list(sc.timeline_markers):
    if m.camera: sc.timeline_markers.remove(m)
bpy.data.objects.remove(cam2)

# ---------- loop doctor ----------
cube.select_set(True)
bpy.ops.zgk.loop_check()
bad = zgk.loop.loop_report(bpy.context, selected_only=True)
check("loop check flags the slide", len(bad) >= 1, f"{len(bad)} curve(s)")
bpy.ops.zgk.loop_fix(method="CLOSE")
bad2 = zgk.loop.loop_report(bpy.context, selected_only=True)
check("loop fix closes it", len(bad2) == 0, f"{len(bad2)} left")

# full-turn spin must count as a closed loop
spin = bpy.data.objects.new("Spinner", None); sc.collection.objects.link(spin)
spin.rotation_euler.z = 0; spin.keyframe_insert("rotation_euler", index=2, frame=1)
spin.rotation_euler.z = 6.283185307; spin.keyframe_insert("rotation_euler", index=2, frame=49)
for o in sc.objects: o.select_set(False)
spin.select_set(True)
check("loop check accepts a full 360 spin", len(zgk.loop.loop_report(bpy.context, selected_only=True)) == 0)
bpy.data.objects.remove(spin)
cube.select_set(True)

# ---------- vertical reframe + auto-follow ----------
bpy.ops.zgk.reframe(aspect="9x16", copy_scene=True)
v = bpy.context.scene
check("reframe makes 9:16 copy", v is not sc and (v.render.resolution_x, v.render.resolution_y) == (1080, 1920), v.name)
v.zgk_subject = v.objects[cube.name] if cube.name in v.objects else cube
bpy.ops.zgk.reframe_follow(follow_x=True, fit=True, smoothing=1)
from bpy_extras.object_utils import world_to_camera_view
inside = True
for f in (1, 12, 24, 36, 48):
    v.frame_set(f)
    subj = v.zgk_subject
    for c in subj.bound_box:
        p = world_to_camera_view(v, v.camera, subj.matrix_world @ __import__("mathutils").Vector(c))
        if not (0 <= p.x <= 1 and 0 <= p.y <= 1):
            inside = False
check("auto-follow keeps subject inside the 9:16 frame", inside)
bpy.ops.zgk.safe_zones(platform="TIKTOK")
check("safe zones set", v.zgk_overlay and v.zgk_platform == "TIKTOK")
v.render.engine = "BLENDER_WORKBENCH"
v.render.resolution_percentage = 20
v.frame_set(48)
v.render.filepath = os.path.join(OUT, "follow_f48.png")
bpy.ops.render.render(write_still=True, scene=v.name)

# ---------- wedge ----------
bpy.context.window_manager  # noqa
sc_w = v
sc_w.render.filepath = os.path.join(OUT, "x")
bpy.ops.zgk.wedge(data_path=f'bpy.data.objects["{cube.name}"].location[2]', start=-0.5, end=0.5,
                  count=4, percent=15, columns=2)
sheet = bpy.context.scene.zgk_last_sheet   # unsaved file -> ~/Videos/ZeroGeometry Exports/Wedges/...
check("wedge contact sheet written", os.path.exists(sheet), sheet)

zgk.unregister()
print(f"RESULT {sum(ok for _, ok in results)}/{len(results)} passed")
