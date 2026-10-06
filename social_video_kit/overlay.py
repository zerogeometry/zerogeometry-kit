"""Camera Guides (camera view only, never rendered): platform safe areas for vertical video, a format badge
and a beat pulse."""
import os
import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils

LIME = (0.8, 1.0, 0.0)            # #CCFF00
INK = (0.04, 0.04, 0.04)          # #0A0A0A
ASSETS = os.path.join(os.path.dirname(__file__), "assets")

# Fraction of a 9:16 frame covered by each app's interface (approximate, from 1080x1920 screenshots):
# l/t/b = left/top/bottom margins, side = width of the right-hand button column, side_top = how far up
# (from the bottom) that column reaches.
_APPS = {
    "TIKTOK": dict(label="TikTok", l=0.04, t=0.07, b=0.21, side=0.17, side_top=0.62),
    "REELS":  dict(label="Instagram Reels", l=0.04, t=0.07, b=0.20, side=0.16, side_top=0.60),
    "SHORTS": dict(label="YouTube Shorts", l=0.04, t=0.06, b=0.17, side=0.15, side_top=0.58),
}
PLATFORMS = dict(_APPS)
# "All platforms": the strictest edge of every app, so one frame works everywhere
PLATFORMS["ALL"] = dict(label="All platforms", **{k: max(a[k] for a in _APPS.values())
                                                for k in ("l", "t", "b", "side", "side_top")})
PLATFORMS["NONE"] = dict(label="", l=0.0, t=0.0, b=0.0, side=0.0, side_top=0.0)


def safe_box(platform):
    """Safe area as frame fractions (x0, x1, y0, y1), y measured from the bottom."""
    p = PLATFORMS.get(platform, PLATFORMS["NONE"])
    return p["l"], 1.0 - p["side"], p["b"], 1.0 - p["t"]
_fonts = {}
_handle = None


def fonts():
    if not _fonts:
        for key, fn in (("mono", "IBMPlexMono-Regular.ttf"), ("light", "Poppins-Light.ttf"), ("bold", "Poppins-SemiBold.ttf")):
            p = os.path.join(ASSETS, fn)
            fid = blf.load(p) if os.path.exists(p) else 0
            _fonts[key] = fid if fid != -1 else 0
    return _fonts


def unload_fonts():
    for fn in ("IBMPlexMono-Regular.ttf", "Poppins-Light.ttf", "Poppins-SemiBold.ttf"):
        try:
            blf.unload(os.path.join(ASSETS, fn))
        except Exception:
            pass
    _fonts.clear()


def camera_frame_px(context):
    """Corners of the camera frame in region pixels (bottom-left, bottom-right, top-right, top-left)."""
    sc, rv3d, region = context.scene, context.region_data, context.region
    cam = sc.camera
    if not cam or rv3d is None or rv3d.view_perspective != "CAMERA":
        return None
    frame = [cam.matrix_world @ v for v in cam.data.view_frame(scene=sc)]   # tr, br, bl, tl
    pts = [view3d_utils.location_3d_to_region_2d(region, rv3d, p) for p in frame]
    if any(p is None for p in pts):
        return None
    tr, br, bl, tl = pts
    return bl, br, tr, tl


def _rect(shader, x0, y0, x1, y1, color):
    batch = batch_for_shader(shader, "TRIS", {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]},
                             indices=[(0, 1, 2), (0, 2, 3)])
    shader.uniform_float("color", color)
    batch.draw(shader)


def _outline(shader, x0, y0, x1, y1, color, width=1.5):
    gpu.state.line_width_set(width)
    batch = batch_for_shader(shader, "LINE_LOOP", {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]})
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.line_width_set(1.0)


def _text(font, txt, x, y, size, color):
    blf.size(font, size)
    blf.color(font, *color)
    blf.position(font, x, y, 0)
    blf.draw(font, txt)


_beat_cache = {}


def _beats(sc):
    """Beat frames, cached until the markers change (the overlay redraws constantly)."""
    key = (sc.name, len(sc.timeline_markers))
    hit = _beat_cache.get(key)
    if hit is None:
        from .beat import beat_frames
        hit = beat_frames(sc)
        _beat_cache.clear()
        _beat_cache[key] = hit
    return hit


def draw():
    sc = bpy.context.scene
    if not getattr(sc, "svk_overlay", False):
        return
    try:
        _draw(bpy.context, sc)
    except Exception as ex:                      # never break the viewport
        print("Social Video Kit overlay:", ex)
    finally:
        gpu.state.blend_set("NONE")


def _draw(context, sc):
    fr = camera_frame_px(context)
    if fr is None:
        return
    bl, br, tr, tl = fr
    x0, y0, x1, y1 = bl.x, bl.y, tr.x, tr.y
    w, h = x1 - x0, y1 - y0
    if w < 40 or h < 40:
        return
    f = fonts()
    u = context.preferences.system.ui_scale                      # follow HiDPI / Resolution Scale
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    p = PLATFORMS.get(sc.svk_platform, PLATFORMS["NONE"])
    if sc.svk_platform != "NONE":
        tint = (*LIME, 0.07)
        # areas covered by the app interface
        _rect(shader, x0, y1 - h * p["t"], x1, y1, tint)                                 # top bar
        _rect(shader, x0, y0, x1, y0 + h * p["b"], tint)                                 # caption + nav
        _rect(shader, x1 - w * p["side"], y0 + h * p["b"], x1, y0 + h * p["side_top"], tint)  # button column
        fx0, fx1, fy0, fy1 = safe_box(sc.svk_platform)
        sx0, sx1, sy0, sy1 = x0 + w * fx0, x0 + w * fx1, y0 + h * fy0, y0 + h * fy1
        _outline(shader, sx0, sy0, sx1, sy1, (*LIME, 0.95), 2.0)
        _text(f.get("mono", 0), f"SAFE AREA · {p['label'].upper()}", sx0 + 6 * u, sy1 - 16 * u,
              int(11 * u), (*LIME, 0.95))
    # frame outline + badge
    _outline(shader, x0, y0, x1, y1, (*LIME, 0.55), 1.0)
    r = sc.render
    ratio = r.resolution_x / max(1, r.resolution_y)
    named = {round(9 / 16, 3): "9:16", round(4 / 5, 3): "4:5", 1.0: "1:1", round(16 / 9, 3): "16:9"}
    fmt = named.get(round(ratio, 3), f"{r.resolution_x}x{r.resolution_y}")
    fs = int(12 * u)
    bx, by = x0 + 8 * u, y0 + 8 * u                           # format badge, inside the frame, bottom-left
    label = f"{fmt}   {r.resolution_x}×{r.resolution_y}"
    blf.size(f.get("mono", 0), fs)
    fw = blf.dimensions(f.get("mono", 0), label)[0]
    bw, bh = 10 * u + fw + 10 * u, 22 * u
    _rect(shader, bx, by, bx + bw, by + bh, (*INK, 0.92))
    _rect(shader, bx, by, bx + 4 * u, by + bh, (*LIME, 1.0))
    _text(f.get("mono", 0), label, bx + 10 * u, by + 6 * u, fs, (*LIME, 1.0))
    # beat pulse: bright on the beat, fading over 6 frames
    beats = _beats(sc)
    if beats:
        import bisect
        cur = sc.frame_current
        i = bisect.bisect_right(beats, cur)
        if i:
            age = cur - beats[i - 1]
            a = max(0.0, 1.0 - age / 6.0)
            rad = (7 + 7 * a) * u
            cx, cy = x1 - 19 * u, y0 + 19 * u                 # bottom-right, opposite the badge
            import math
            pts = [(cx + rad * math.cos(t / 16 * math.tau), cy + rad * math.sin(t / 16 * math.tau)) for t in range(16)]
            batch = batch_for_shader(shader, "TRI_FAN", {"pos": [(cx, cy)] + pts + [pts[0]]})
            shader.uniform_float("color", (*LIME, 0.25 + 0.75 * a))
            batch.draw(shader)


class SVK_OT_overlay_toggle(bpy.types.Operator):
    """Camera Guides: drawn in camera view only, never rendered. Shows the format badge, the vertical-video
safe area (when a platform is picked) and a dot that pulses on every beat marker"""
    bl_idname = "svk.overlay_toggle"
    bl_label = "Camera Guides"

    def execute(self, context):
        context.scene.svk_overlay = not context.scene.svk_overlay
        for a in context.screen.areas if context.screen else []:
            if a.type == "VIEW_3D":
                a.tag_redraw()
        return {"FINISHED"}


def register_handler():
    global _handle
    if _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(draw, (), "WINDOW", "POST_PIXEL")


def unregister_handler():
    global _handle
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, "WINDOW")
        _handle = None
    unload_fonts()


classes = (SVK_OT_overlay_toggle,)
