"""Vertical Reframe: turn a finished 16:9 scene into a real 9:16 / 4:5 / 1:1 version -- a new camera
framing, not a crop. Keyframed lenses are scaled too, and the work happens on a scene copy so the
original edit is untouched."""
import bpy
from bpy.props import EnumProperty, FloatProperty, BoolProperty, IntProperty
from .beat import _fcurves

ASPECTS = {
    "9x16": (1080, 1920, "Reels / TikTok / Shorts"),
    "4x5": (1080, 1350, "Instagram feed"),
    "1x1": (1080, 1080, "Square"),
    "16x9": (1920, 1080, "Landscape"),
}


def scale_lens(cam_data, k):
    cam_data.lens *= k
    for fc in _fcurves(cam_data):
        if fc.data_path == "lens":
            for kp in fc.keyframe_points:
                kp.co.y *= k
                kp.handle_left.y *= k
                kp.handle_right.y *= k
            fc.update()


def suggested_zoom(src_w, src_h, dst_w, dst_h, subject_width=0.6):
    """How much to punch in so a subject that filled `subject_width` of the old frame width still
    reads well. Horizontal sensor fit keeps the old horizontal field of view at k = 1."""
    old_aspect = src_w / src_h
    new_aspect = dst_w / dst_h
    if new_aspect >= old_aspect:
        return 1.0
    # the new frame is narrower: compromise between keeping width (1.0) and keeping height
    keep_height = old_aspect / new_aspect
    return 1.0 + (keep_height - 1.0) * (1.0 - subject_width) * 0.5


class ZGK_OT_reframe(bpy.types.Operator):
    """Make a reframed copy of this scene for another aspect ratio (social formats)"""
    bl_idname = "zgk.reframe"
    bl_label = "Reframe Scene"
    bl_options = {"REGISTER", "UNDO"}

    aspect: EnumProperty(name="Format", items=[(k, k.replace("x", ":"), v[2]) for k, v in ASPECTS.items()],
                         default="9x16")
    zoom: FloatProperty(name="Lens punch-in", default=0.0, min=0.0, max=4.0,
                        description="Multiply every lens value; 0 = suggest automatically")
    subject_width: FloatProperty(name="Subject width", default=0.6, min=0.05, max=1.0,
                                 description="How much of the original frame width your subject spans")
    copy_scene: BoolProperty(name="Work on a copy", default=True)
    percent: IntProperty(name="Resolution %", default=100, min=10, max=200)

    def execute(self, context):
        src = context.scene
        sw, sh = src.render.resolution_x, src.render.resolution_y
        dw, dh, _ = ASPECTS[self.aspect]
        if self.copy_scene:
            bpy.ops.scene.new(type="FULL_COPY")
            sc = context.scene
            sc.name = f"{src.name}_{self.aspect}"
        else:
            sc = src
        k = self.zoom or suggested_zoom(sw, sh, dw, dh, self.subject_width)
        sc.render.resolution_x, sc.render.resolution_y = dw, dh
        sc.render.resolution_percentage = self.percent
        cams = {sc.camera} if sc.camera else set()
        cams |= {m.camera for m in sc.timeline_markers if m.camera}     # beat-cut cameras too
        done = set()
        for cam in cams:
            if cam.data.name in done:
                continue
            done.add(cam.data.name)
            cam.data.sensor_fit = "HORIZONTAL"
            scale_lens(cam.data, k)
        sc.zgk_reframe_zoom = k
        self.report({"INFO"}, f"{sc.name}: {dw}x{dh}, lens x{k:.2f} on {len(done)} camera(s)")
        return {"FINISHED"}


class ZGK_OT_reframe_nudge(bpy.types.Operator):
    """Punch in / pull out every camera lens in this scene (keyframes included)"""
    bl_idname = "zgk.reframe_nudge"
    bl_label = "Nudge Zoom"
    bl_options = {"REGISTER", "UNDO"}

    factor: FloatProperty(name="Factor", default=1.1, min=0.1, max=10.0)

    def execute(self, context):
        sc = context.scene
        cams = {sc.camera} if sc.camera else set()
        cams |= {m.camera for m in sc.timeline_markers if m.camera}
        for data in {c.data for c in cams}:
            scale_lens(data, self.factor)
        sc.zgk_reframe_zoom *= self.factor
        return {"FINISHED"}


def _subject_points(context):
    """World-space bounding-box corners of the chosen subject (object, or every object in a collection)."""
    sc = context.scene
    obs = []
    if sc.zgk_subject_collection:
        obs = [o for o in sc.zgk_subject_collection.all_objects if o.type in {"MESH", "CURVE", "FONT", "META", "EMPTY"}]
    elif sc.zgk_subject:
        obs = [sc.zgk_subject]
    pts = []
    for o in obs:
        if o.type == "EMPTY":
            pts.append(o.matrix_world.translation.copy())
        else:
            pts += [o.matrix_world @ __import__("mathutils").Vector(c) for c in o.bound_box]
    return pts


def _smooth(vals, window):
    if window <= 1 or len(vals) < 3:
        return vals
    h = window // 2
    out = []
    for i in range(len(vals)):
        seg = vals[max(0, i - h): i + h + 1]
        out.append(sum(seg) / len(seg))
    return out


class ZGK_OT_reframe_follow(bpy.types.Operator):
    """Keep the subject centred and inside the frame on every frame by keying the camera's lens shift
    (and optionally zoom). The camera move itself is untouched -- like Auto Reframe, but 3D-aware"""
    bl_idname = "zgk.reframe_follow"
    bl_label = "Auto-Follow Subject"
    bl_options = {"REGISTER", "UNDO"}

    follow_x: BoolProperty(name="Follow horizontally", default=True)
    follow_y: BoolProperty(name="Follow vertically", default=False)
    fit: BoolProperty(name="Zoom out to keep it inside", default=True)
    margin: FloatProperty(name="Safe margin", default=0.08, min=0.0, max=0.4)
    strength: FloatProperty(name="Strength", default=1.0, min=0.0, max=1.0,
                            description="1 = centre exactly, lower = gentle drift toward the subject")
    smoothing: IntProperty(name="Smoothing (frames)", default=9, min=1, max=97)

    def execute(self, context):
        from bpy_extras.object_utils import world_to_camera_view
        sc, cam = context.scene, context.scene.camera
        if not cam:
            self.report({"ERROR"}, "Scene has no active camera")
            return {"CANCELLED"}
        if not (sc.zgk_subject or sc.zgk_subject_collection):
            self.report({"ERROR"}, "Pick a subject object or collection first")
            return {"CANCELLED"}
        cd = cam.data
        # clear previous follow keys so we measure the raw framing
        for fc in _fcurves(cd):
            if fc.data_path in {"shift_x", "shift_y"}:
                fc.keyframe_points.clear()
        cd.shift_x = cd.shift_y = 0.0
        w, h = sc.render.resolution_x, sc.render.resolution_y
        big = max(w, h)
        frames = list(range(sc.frame_start, sc.frame_end + 1))
        sx, sy, lens = [], [], []
        f_keep = sc.frame_current
        for f in frames:
            sc.frame_set(f)
            cd.shift_x = cd.shift_y = 0.0
            base_lens = cd.lens
            pts = [world_to_camera_view(sc, sc.camera, p) for p in _subject_points(context)]
            pts = [p for p in pts if p.z > 0]
            if not pts:
                sx.append(0.0); sy.append(0.0); lens.append(base_lens)
                continue
            x0, x1 = min(p.x for p in pts), max(p.x for p in pts)
            y0, y1 = min(p.y for p in pts), max(p.y for p in pts)
            k = 1.0
            if self.fit:
                room = 1.0 - 2 * self.margin
                k = min(1.0, room / max(x1 - x0, 1e-6), room / max(y1 - y0, 1e-6))
            # shift is measured in units of the frame's largest side; zooming scales the offset by k
            sx.append(((x0 + x1) / 2 - 0.5) * (w / big) * k * self.strength if self.follow_x else 0.0)
            sy.append(((y0 + y1) / 2 - 0.5) * (h / big) * k * self.strength if self.follow_y else 0.0)
            lens.append(base_lens * k)
        sx, sy = _smooth(sx, self.smoothing), _smooth(sy, self.smoothing)
        lens = _smooth(lens, self.smoothing) if self.fit else lens
        for f, a, b, l in zip(frames, sx, sy, lens):
            if self.follow_x:
                cd.shift_x = a; cd.keyframe_insert("shift_x", frame=f)
            if self.follow_y:
                cd.shift_y = b; cd.keyframe_insert("shift_y", frame=f)
            if self.fit:
                cd.lens = l; cd.keyframe_insert("lens", frame=f)
        sc.frame_set(f_keep)
        self.report({"INFO"}, f"Followed subject over {len(frames)} frames")
        return {"FINISHED"}


# ---------------------------------------------------------------- social safe zones
# fraction of frame kept clear of platform UI (left, right, top, bottom), for 9:16 video
SAFE_ZONES = {
    "TIKTOK": ((0.06, 0.18, 0.08, 0.20), "TikTok: right-hand buttons, caption + music bar at the bottom"),
    "REELS": ((0.06, 0.16, 0.08, 0.22), "Instagram Reels: right-hand buttons, caption at the bottom"),
    "SHORTS": ((0.06, 0.15, 0.08, 0.18), "YouTube Shorts"),
}


class ZGK_OT_safe_zones(bpy.types.Operator):
    """Show where the platform's buttons and captions will cover your video (camera safe areas)"""
    bl_idname = "zgk.safe_zones"
    bl_label = "Social Safe Zones"
    bl_options = {"REGISTER", "UNDO"}

    platform: EnumProperty(name="Platform", items=[(k, k.title(), v[1]) for k, v in SAFE_ZONES.items()],
                           default="TIKTOK")

    def execute(self, context):
        sc = context.scene
        l, r, t, b = SAFE_ZONES[self.platform][0]
        # Blender safe areas are symmetric: use the tightest side on each axis
        sc.safe_areas.title = (2 * max(l, r), 2 * max(t, b))
        sc.safe_areas.action = (2 * min(l, r), 2 * min(t, b))
        cams = {sc.camera} if sc.camera else set()
        cams |= {m.camera for m in sc.timeline_markers if m.camera}
        for c in cams:
            c.data.show_safe_areas = True
            c.data.passepartout_alpha = 0.85
        self.report({"INFO"}, f"Inner box = keep text/product inside ({self.platform.title()})")
        return {"FINISHED"}


# ---------------------------------------------------------------- all formats + batch render
class ZGK_OT_reframe_all(bpy.types.Operator):
    """Create 9:16, 4:5 and 1:1 copies of this scene in one go"""
    bl_idname = "zgk.reframe_all"
    bl_label = "Make All Social Formats"
    bl_options = {"REGISTER", "UNDO"}

    subject_width: FloatProperty(name="Subject width", default=0.6, min=0.05, max=1.0)

    def execute(self, context):
        src = context.window.scene if context.window else context.scene
        made = []
        for asp in ("9x16", "4x5", "1x1"):
            if context.window:
                context.window.scene = src
            bpy.ops.zgk.reframe(aspect=asp, subject_width=self.subject_width, copy_scene=True)
            made.append(context.scene.name)
        if context.window:
            context.window.scene = src
        self.report({"INFO"}, "Created: " + ", ".join(made))
        return {"FINISHED"}


class ZGK_OT_render_formats(bpy.types.Operator):
    """Render the animation of this scene and every reframed copy of it to MP4s next to the .blend"""
    bl_idname = "zgk.render_formats"
    bl_label = "Render All Formats"

    def execute(self, context):
        import os
        base = context.scene.name.split("_")[0]
        scenes = [s for s in bpy.data.scenes if s.name == base or s.name.startswith(base + "_")]
        out_dir = bpy.path.abspath("//zgk_renders") if bpy.data.filepath else os.path.join(
            os.path.expanduser("~"), "zgk_renders")
        os.makedirs(out_dir, exist_ok=True)
        for s in scenes:
            r = s.render
            r.image_settings.file_format = "FFMPEG"
            r.ffmpeg.format = "MPEG4"
            r.ffmpeg.codec = "H264"
            r.ffmpeg.constant_rate_factor = "HIGH"
            r.filepath = os.path.join(out_dir, s.name + "_")
            bpy.ops.render.render(animation=True, scene=s.name)
        self.report({"INFO"}, f"Rendered {len(scenes)} format(s) to {out_dir}")
        return {"FINISHED"}


classes = (ZGK_OT_reframe, ZGK_OT_reframe_nudge, ZGK_OT_reframe_follow, ZGK_OT_safe_zones,
           ZGK_OT_reframe_all, ZGK_OT_render_formats)
