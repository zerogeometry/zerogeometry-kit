"""Deeper checks: idempotent follow, multi-camera follow, master untouched, render-all, real song, wedge sheet.
blender -b --factory-startup -P tests/test_more.py -- [path/to/song.mp3]
"""
import os, sys, math, time, tempfile, glob, subprocess
import bpy, mathutils
from bpy_extras.object_utils import world_to_camera_view

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import social_video_kit as svk
svk.register()
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.join(tempfile.gettempdir(), "svk_more")
os.makedirs(OUT, exist_ok=True)
res = []
def check(name, ok, detail=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))

def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 48
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    bpy.ops.mesh.primitive_cylinder_add(radius=0.33, depth=1.2, location=(0, -2.0, 0.6))
    can = bpy.context.object; can.name = "Product"
    can.keyframe_insert("location", frame=1); can.location.y = 2.0; can.keyframe_insert("location", frame=48)
    cams = []
    for i, (loc, rot) in enumerate((((9, 0, 1), (math.radians(86), 0, math.radians(90))),
                                    ((7, 3, 1.5), (math.radians(84), 0, math.radians(113))))):
        c = bpy.data.objects.new(f"Cam{i}", bpy.data.cameras.new(f"Cam{i}"))
        sc.collection.objects.link(c); c.location = loc; c.rotation_euler = rot; c.data.lens = 40
        cams.append(c)
    cams[0].data.keyframe_insert("lens", frame=1)
    cams[0].data.lens = 55; cams[0].data.keyframe_insert("lens", frame=48)   # animated zoom
    sc.camera = cams[0]
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
    return sc, can, cams

def inside(sc, obj, frames, pad=0.0):
    for f in frames:
        sc.frame_set(f)
        for c in obj.bound_box:
            p = world_to_camera_view(sc, sc.camera, obj.matrix_world @ mathutils.Vector(c))
            if not (-pad <= p.x <= 1 + pad and -pad <= p.y <= 1 + pad):
                return False, f
    return True, None

# ---------- 1. master untouched, animated lens scaled in the copy
sc, can, cams = scene()
master_lens = [cams[0].data.animation_data.action and None]
before = (cams[0].data.lens, )
bpy.ops.svk.reframe(aspect="9x16", copy_scene=True, zoom=1.3)
v = bpy.context.scene
m_cam = bpy.data.scenes["Scene"].camera
v_cam = v.camera
sc_m = bpy.data.scenes["Scene"]
sc_m.frame_set(48); m48 = m_cam.data.lens
v.frame_set(48); v48 = v_cam.data.lens
check("master camera untouched", abs(m48 - 55) < 1e-4, f"master lens@48 {m48:.2f}")
check("copy lens scaled incl. keyframes", abs(v48 - 55 * 1.3) < 1e-3 and m_cam.data != v_cam.data, f"copy lens@48 {v48:.2f}")
check("copy remembers master", v.get("svk_source") == "Scene")

# ---------- 2. follow keeps the product inside, re-run is idempotent
v.svk_subject = next(o for o in v.objects if o.name.startswith("Product"))
ok0, f0 = inside(v, v.svk_subject, range(1, 49))
check("without follow the product leaves the 9:16 frame", not ok0, f"leaves at frame {f0}")
bpy.ops.svk.reframe_follow(fit=True, smoothing=5, use_safe_zone=False)
ok1, f1 = inside(v, v.svk_subject, range(1, 49), pad=0.01)
check("follow keeps it inside", ok1, f"fails at {f1}" if not ok1 else "")
v.frame_set(30); l1 = v.camera.data.lens; s1 = v.camera.data.shift_x
bpy.ops.svk.reframe_follow(fit=True, smoothing=5, use_safe_zone=False)
v.frame_set(30); l2 = v.camera.data.lens; s2 = v.camera.data.shift_x
check("re-running follow does not compound", abs(l1 - l2) < 1e-4 and abs(s1 - s2) < 1e-5, f"lens {l1:.3f}->{l2:.3f}")
bpy.ops.svk.reframe_follow_clear()
v.frame_set(48)
check("clear follow restores animated lens", abs(v.camera.data.lens - 55 * 1.3) < 1e-3 and abs(v.camera.data.shift_x) < 1e-6,
      f"{v.camera.data.lens:.2f}")

# ---------- 3. safe-area target: product centred inside each platform's safe box (and the combined one)
def inside_box(platform):
    bx0, bx1, by0, by1 = svk.overlay.safe_box(platform)
    for f in (1, 24, 48):
        v.frame_set(f)
        pts = [world_to_camera_view(v, v.camera, v.svk_subject.matrix_world @ mathutils.Vector(c))
               for c in v.svk_subject.bound_box]
        if min(q.x for q in pts) < bx0 - 0.01 or max(q.x for q in pts) > bx1 + 0.01 or \
           min(q.y for q in pts) < by0 - 0.01 or max(q.y for q in pts) > by1 + 0.01:
            return False
    return True
for plat in ("ALL", "TIKTOK", "REELS", "SHORTS"):
    bpy.ops.svk.safe_zones(platform=plat)
    bpy.ops.svk.reframe_follow(fit=True, smoothing=1, use_safe_zone=True)
    check(f"follow keeps product inside the {plat} safe area", inside_box(plat))
a = svk.overlay.PLATFORMS
check("All-platforms area is inside every platform's area",
      all(svk.overlay.safe_box("ALL")[0] >= svk.overlay.safe_box(k)[0] and
          svk.overlay.safe_box("ALL")[1] <= svk.overlay.safe_box(k)[1] and
          svk.overlay.safe_box("ALL")[2] >= svk.overlay.safe_box(k)[2] and
          svk.overlay.safe_box("ALL")[3] <= svk.overlay.safe_box(k)[3] for k in ("TIKTOK", "REELS", "SHORTS")))
bpy.ops.svk.safe_zones(platform="ALL")
bx0, bx1, by0, by1 = svk.overlay.safe_box("ALL")

# ---------- 3b. fill: a small subject is punched in to fill the safe box width
bpy.ops.svk.reframe_follow(fit=True, fill=True, smoothing=1, use_safe_zone=True, margin=0.08)
v.frame_set(24)
pts = [world_to_camera_view(v, v.camera, v.svk_subject.matrix_world @ mathutils.Vector(c)) for c in v.svk_subject.bound_box]
span_x = max(q.x for q in pts) - min(q.x for q in pts)
span_y = max(q.y for q in pts) - min(q.y for q in pts)
target_x = (bx1 - bx0) * 0.84
target_y = (by1 - by0) * 0.84
check("fill frame punches in to the safe box", abs(span_x - target_x) < 0.03 or abs(span_y - target_y) < 0.03,
      f"span {span_x:.2f}x{span_y:.2f}, target {target_x:.2f}x{target_y:.2f}")

# ---------- 4. multi-camera (beat cuts): both cameras follow
bpy.ops.svk.reframe_follow_clear()
bpy.ops.svk.beat_grid(bpm=120)
for o in v.objects: o.select_set(False)
for o in v.objects:
    if o.type == "CAMERA": o.select_set(True)
bpy.ops.svk.beat_cuts(every=2)
bpy.ops.svk.reframe_follow(fit=True, smoothing=1, use_safe_zone=False)
ok4, f4 = inside(v, v.svk_subject, range(1, 49), pad=0.01)
keyed = {c.name for c in v.objects if c.type == "CAMERA" and c.data.animation_data and
         any(fc.data_path == "shift_x" for fc in svk.beat._fcurves(c.data))}
check("multi-camera follow (beat cuts)", ok4 and len(keyed) == 2, f"keyed {sorted(keyed)}; fail frame {f4}")

# ---------- 5. all formats + render all formats (tiny, fast)
bpy.context.window_manager  # noqa
bpy.context.window.scene = sc_m if bpy.context.window else None
for s in list(bpy.data.scenes):
    if s.name != "Scene": bpy.data.scenes.remove(s)
master = bpy.data.scenes["Scene"]
if bpy.context.window: bpy.context.window.scene = master
bpy.ops.svk.reframe_all()
fmts = sorted((s.render.resolution_x, s.render.resolution_y) for s in bpy.data.scenes if s.get("svk_source") == "Scene")
check("all social formats", fmts == [(1080, 1080), (1080, 1350), (1080, 1920)], str(fmts))
for s in bpy.data.scenes:
    s.render.engine = "BLENDER_WORKBENCH"; s.render.resolution_percentage = 10; s.frame_end = 6
if bpy.context.window: bpy.context.window.scene = master
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "fmt_test.blend"))
RDIR = os.path.join(OUT, "Social Video Exports", "Renders")
for f in glob.glob(os.path.join(RDIR, "*")): os.remove(f)
before = {s.name: (s.render.image_settings.file_format, s.render.filepath, s.render.resolution_x) for s in bpy.data.scenes}
bpy.ops.svk.render_formats()
after = {s.name: (s.render.image_settings.file_format, s.render.filepath, s.render.resolution_x) for s in bpy.data.scenes}
check("render all formats restores your render settings", before == after)
mp4s = sorted(glob.glob(os.path.join(RDIR, "*.mp4")))
sizes = []
for m in mp4s:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", m],
                       capture_output=True, text=True).stdout.strip().splitlines()
    sizes.append(r[0] if r else "?")
names = sorted(os.path.basename(m) for m in mp4s)
check("render all formats -> 4 cleanly named mp4s",
      names == ["Scene_16x9.mp4", "Scene_1x1.mp4", "Scene_4x5.mp4", "Scene_9x16.mp4"], " | ".join(f"{os.path.basename(m)}={s}" for m, s in zip(mp4s, sizes)))

# ---------- 6. real song
if args and os.path.exists(args[0]):
    t0 = time.time()
    bpm, beats = svk.beat.estimate_beats(args[0])
    dt = time.time() - t0
    import numpy as np
    gaps = np.diff(beats)
    check("real song analyses fast", dt < 20, f"{dt:.1f}s for {beats[-1]:.0f}s of audio")
    check("real song tempo plausible + steady grid", 60 <= bpm <= 200 and gaps.std() < 0.03,
          f"{bpm:.1f} BPM, {len(beats)} beats")

# ---------- 7. wedge brand sheet
bpy.ops.svk.wedge(data_path='bpy.data.objects["Product"].location[2]', start=0, end=1, count=4, percent=10, columns=2)
sheet = bpy.context.scene.svk_last_sheet
check("wedge sheet lands in the export folder", sheet.startswith(os.path.join(OUT, "Social Video Exports", "Wedges")), sheet)
img = bpy.data.images.load(sheet)
import numpy as np
px = np.array(img.pixels[:]).reshape(img.size[1], img.size[0], 4)
lime_rows = [y for y in range(img.size[1]) if abs(px[y, img.size[0] // 2, 0] - 0.8) < 0.05 and px[y, img.size[0] // 2, 1] > 0.95]
check("wedge sheet has its header rule", len(lime_rows) >= 2, f"{img.size[0]}x{img.size[1]}")

# ---------- 8. wedge an ANIMATED property: keys must not override the wedge values
bpy.ops.svk.wedge(data_path='bpy.data.objects["Product"].location[1]', start=-1.5, end=1.5, count=3,
                  percent=10, columns=3)
wdir = os.path.dirname(bpy.context.scene.svk_last_sheet)
a = bpy.data.images.load(os.path.join(wdir, "wedge_00.png"))
b = bpy.data.images.load(os.path.join(wdir, "wedge_02.png"))
diff = float(np.abs(np.array(a.pixels[:]) - np.array(b.pixels[:])).mean())
prod = bpy.data.objects["Product"]
still_animated = all(not fc.mute for fc in svk.beat._fcurves(prod))
check("wedge works on animated property + restores keys", diff > 1e-3 and still_animated, f"tile diff {diff:.4f}")

svk.unregister()
print(f"RESULT {sum(res)}/{len(res)} passed")
