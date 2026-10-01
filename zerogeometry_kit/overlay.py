"""ZeroGeometry viewport overlay (camera view only): real asymmetric social safe zones, a format badge
and a beat pulse -- drawn in the ZeroGeometry palette with the brand fonts."""
import os
import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils

LIME = (0.8, 1.0, 0.0)            # #CCFF00
INK = (0.04, 0.04, 0.04)          # #0A0A0A
ASSETS = os.path.join(os.path.dirname(__file__), "assets")

# fraction of the frame covered by platform UI, measured on 1080x1920 screenshots
# (left, right, top, bottom) + the right-hand button column's vertical extent (from, to) as frame fractions
PLATFORMS = {
    "TIKTOK": dict(label="TikTok", l=0.04, r=0.04, t=0.07, b=0.21, col=(0.86, 1.0, 0.34, 0.80)),
    "REELS":  dict(label="Reels",  l=0.04, r=0.04, t=0.07, b=0.20, col=(0.86, 1.0, 0.36, 0.78)),
    "SHORTS": dict(label="Shorts", l=0.04, r=0.04, t=0.06, b=0.17, col=(0.86, 1.0, 0.34, 0.72)),
    "NONE":   dict(label="", l=0, r=0, t=0, b=0, col=(1, 1, 0, 0)),
}
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


def draw():
    context = bpy.context
    sc = context.scene
    if not getattr(sc, "zgk_overlay", False):
        return
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
    p = PLATFORMS.get(sc.zgk_platform, PLATFORMS["NONE"])
    if sc.zgk_platform != "NONE":
        tint = (*LIME, 0.07)
        # covered bands
        _rect(shader, x0, y1 - h * p["t"], x1, y1, tint)                       # top bar
        _rect(shader, x0, y0, x1, y0 + h * p["b"], tint)                       # caption + nav
        _rect(shader, x1 - w * 0.17, y0 + h * p["b"], x1, y0 + h * 0.62, tint)  # like / comment / share column
        # inner safe box
        sx0, sx1 = x0 + w * p["l"], x1 - w * 0.17
        sy0, sy1 = y0 + h * p["b"], y1 - h * p["t"]
        _outline(shader, sx0, sy0, sx1, sy1, (*LIME, 0.95), 2.0)
        if f.get("mono") is not None:
            _text(f["mono"], f"{p['label'].upper()} SAFE", sx0 + 6 * u, sy1 - 16 * u, int(11 * u), (*LIME, 0.95))
    # frame outline + badge
    _outline(shader, x0, y0, x1, y1, (*LIME, 0.55), 1.0)
    r = sc.render
    ratio = r.resolution_x / max(1, r.resolution_y)
    named = {round(9 / 16, 3): "9:16", round(4 / 5, 3): "4:5", 1.0: "1:1", round(16 / 9, 3): "16:9"}
    fmt = named.get(round(ratio, 3), f"{r.resolution_x}x{r.resolution_y}")
    fs = int(12 * u)
    bx, by = x0 + 8 * u, y0 + 8 * u                           # inside the frame, bottom-left
    blf.size(f.get("light", 0), fs)
    zw = blf.dimensions(f.get("light", 0), "ZERO ")[0]
    blf.size(f.get("bold", 0), fs)
    gw = blf.dimensions(f.get("bold", 0), "GEOMETRY")[0]
    blf.size(f.get("mono", 0), fs)
    fw = blf.dimensions(f.get("mono", 0), fmt)[0]
    bw, bh = 10 * u + zw + gw + 12 * u + fw + 10 * u, 22 * u
    _rect(shader, bx, by, bx + bw, by + bh, (*INK, 0.92))
    _rect(shader, bx, by, bx + 4 * u, by + bh, (*LIME, 1.0))
    _text(f.get("light", 0), "ZERO", bx + 10 * u, by + 6 * u, fs, (1, 1, 1, 0.9))
    _text(f.get("bold", 0), "GEOMETRY", bx + 10 * u + zw, by + 6 * u, fs, (1, 1, 1, 1))
    _text(f.get("mono", 0), fmt, bx + 10 * u + zw + gw + 12 * u, by + 6 * u, fs, (*LIME, 1.0))
    # beat pulse: the zerogeometry.com lime dot, bright on the beat, fading over 6 frames
    from .beat import beat_frames
    beats = beat_frames(sc)
    if beats:
        cur = sc.frame_current
        past = [b for b in beats if b <= cur]
        if past:
            age = cur - past[-1]
            a = max(0.0, 1.0 - age / 6.0)
            rad = (7 + 7 * a) * u
            cx, cy = x1 - 19 * u, y0 + 19 * u                 # bottom-right, opposite the badge
            import math
            pts = [(cx + rad * math.cos(t / 16 * math.tau), cy + rad * math.sin(t / 16 * math.tau)) for t in range(16)]
            batch = batch_for_shader(shader, "TRI_FAN", {"pos": [(cx, cy)] + pts + [pts[0]]})
            shader.uniform_float("color", (*LIME, 0.25 + 0.75 * a))
            batch.draw(shader)
    gpu.state.blend_set("NONE")


class ZGK_OT_overlay_toggle(bpy.types.Operator):
    """Toggle the ZeroGeometry camera overlay (safe zones, format badge, beat pulse)"""
    bl_idname = "zgk.overlay_toggle"
    bl_label = "ZG Overlay"

    def execute(self, context):
        context.scene.zgk_overlay = not context.scene.zgk_overlay
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


classes = (ZGK_OT_overlay_toggle,)
