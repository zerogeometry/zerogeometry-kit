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
    snap = cam_data.get("zgk_lens_orig")
    if snap:                                   # keep Auto-Follow's saved original in step
        snap = list(snap)
        cam_data["zgk_lens_orig"] = [v * k if (i % 2 or snap[0] == -1.0) and i > 0 else v
                                     for i, v in enumerate(snap)]
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
            sc["zgk_source"] = src.get("zgk_source", src.name)        # remember the master scene
            # make sure the copy owns its cameras: never rescale the master's lenses by accident
            for ob in sc.objects:
                if ob.type == "CAMERA" and ob.data.users > 1:
                    ob.data = ob.data.copy()
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
    fill: BoolProperty(name="Fill frame (zoom in too)", default=False,
                       description="Also punch in when the subject is small, so it fills the frame / safe box")
    margin: FloatProperty(name="Safe margin", default=0.08, min=0.0, max=0.4)
    strength: FloatProperty(name="Strength", default=1.0, min=0.0, max=1.0,
                            description="1 = centre exactly, lower = gentle drift toward the subject")
    smoothing: IntProperty(name="Smoothing (frames)", default=9, min=1, max=97)
    use_safe_zone: BoolProperty(name="Centre in the platform safe box", default=True,
                                description="Aim for the centre of the area not covered by TikTok/Reels UI")

    # ---- original-lens snapshot, so re-running never compounds the zoom
    @staticmethod
    def _snapshot_lens(cd):
        if "zgk_lens_orig" in cd:
            return
        keys = [(kp.co.x, kp.co.y) for fc in _fcurves(cd) if fc.data_path == "lens" for kp in fc.keyframe_points]
        cd["zgk_lens_orig"] = [v for xy in keys for v in xy] if keys else [-1.0, cd.lens]

    @staticmethod
    def _restore_lens(cd):
        snap = list(cd.get("zgk_lens_orig", []))
        if not snap:
            return
        for fc in _fcurves(cd):
            if fc.data_path in {"lens", "shift_x", "shift_y"}:
                fc.keyframe_points.clear()
        if snap[0] == -1.0:
            cd.lens = snap[1]
        else:
            for f, v in zip(snap[::2], snap[1::2]):
                cd.lens = v
                cd.keyframe_insert("lens", frame=f)
        cd.shift_x = cd.shift_y = 0.0

    def execute(self, context):
        from bpy_extras.object_utils import world_to_camera_view
        sc = context.scene
        if not sc.camera:
            self.report({"ERROR"}, "Scene has no active camera")
            return {"CANCELLED"}
        if not (sc.zgk_subject or sc.zgk_subject_collection):
            self.report({"ERROR"}, "Pick a subject object or collection first")
            return {"CANCELLED"}
        # every camera this scene cuts to (beat cuts bind cameras to markers)
        cams = {sc.camera} | {m.camera for m in sc.timeline_markers if m.camera}
        for c in cams:
            self._snapshot_lens(c.data)
            self._restore_lens(c.data)
        w, h = sc.render.resolution_x, sc.render.resolution_y
        big = max(w, h)
        # target point in the frame: centre of the platform safe box, or the frame centre
        from .overlay import PLATFORMS
        p = PLATFORMS.get(sc.zgk_platform, PLATFORMS["NONE"])
        if self.use_safe_zone and sc.zgk_platform != "NONE" and h > w:
            tx = (p["l"] + (1 - 0.17)) / 2
            ty = (p["b"] + (1 - p["t"])) / 2
            room_x, room_y = (1 - 0.17 - p["l"]), (1 - p["t"] - p["b"])
        else:
            tx = ty = 0.5
            room_x = room_y = 1.0
        frames = list(range(sc.frame_start, sc.frame_end + 1))
        per_cam = {}                                         # camera data -> [(frame, sx, sy, lens)]
        f_keep = sc.frame_current
        pts_world_cache = None
        for f in frames:
            sc.frame_set(f)
            cam = sc.camera
            cd = cam.data
            base_lens = cd.lens
            pts = [world_to_camera_view(sc, cam, q) for q in _subject_points(context)]
            pts = [q for q in pts if q.z > 0]
            if not pts:
                per_cam.setdefault(cd, []).append((f, 0.0, 0.0, base_lens))
                continue
            x0, x1 = min(q.x for q in pts), max(q.x for q in pts)
            y0, y1 = min(q.y for q in pts), max(q.y for q in pts)
            k = 1.0
            if self.fit or self.fill:
                k = min(room_x * (1 - 2 * self.margin) / max(x1 - x0, 1e-6),
                        room_y * (1 - 2 * self.margin) / max(y1 - y0, 1e-6))
                k = min(k, 8.0) if self.fill else min(k, 1.0)          # fill: up to 8x punch-in
            # zooming out by k pulls everything toward the centre; then shift so the subject lands on target.
            # shift is in units of the frame's largest side.
            cx = 0.5 + ((x0 + x1) / 2 - 0.5) * k
            cy = 0.5 + ((y0 + y1) / 2 - 0.5) * k
            sx = (cx - tx) * (w / big) * self.strength if self.follow_x else 0.0
            sy = (cy - ty) * (h / big) * self.strength if self.follow_y else 0.0
            per_cam.setdefault(cd, []).append((f, sx, sy, base_lens * k))
        for cd, rows in per_cam.items():
            fs = [r[0] for r in rows]
            sxs = _smooth([r[1] for r in rows], self.smoothing)
            sys_ = _smooth([r[2] for r in rows], self.smoothing)
            zoom = self.fit or self.fill
            ls = _smooth([r[3] for r in rows], self.smoothing) if zoom else [r[3] for r in rows]
            for f, a, b, l in zip(fs, sxs, sys_, ls):
                if self.follow_x:
                    cd.shift_x = a; cd.keyframe_insert("shift_x", frame=f)
                if self.follow_y:
                    cd.shift_y = b; cd.keyframe_insert("shift_y", frame=f)
                if zoom:
                    cd.lens = l; cd.keyframe_insert("lens", frame=f)
        sc.frame_set(f_keep)
        self.report({"INFO"}, f"Followed subject over {len(frames)} frames on {len(per_cam)} camera(s)")
        return {"FINISHED"}


class ZGK_OT_reframe_follow_clear(bpy.types.Operator):
    """Remove Auto-Follow and restore every camera's original lens"""
    bl_idname = "zgk.reframe_follow_clear"
    bl_label = "Clear Follow"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sc = context.scene
        cams = ({sc.camera} if sc.camera else set()) | {m.camera for m in sc.timeline_markers if m.camera}
        n = 0
        for c in cams:
            if "zgk_lens_orig" in c.data:
                ZGK_OT_reframe_follow._restore_lens(c.data)
                del c.data["zgk_lens_orig"]
                n += 1
        self.report({"INFO"}, f"Restored {n} camera(s)")
        return {"FINISHED"}


# ---------------------------------------------------------------- social safe zones
class ZGK_OT_safe_zones(bpy.types.Operator):
    """Show where the platform's buttons and captions cover a vertical video (ZeroGeometry overlay)"""
    bl_idname = "zgk.safe_zones"
    bl_label = "Social Safe Zones"
    bl_options = {"REGISTER", "UNDO"}

    platform: EnumProperty(name="Platform", items=[
        ("TIKTOK", "TikTok", "Right-hand buttons, caption + music bar at the bottom"),
        ("REELS", "Reels", "Instagram Reels"),
        ("SHORTS", "Shorts", "YouTube Shorts"),
        ("NONE", "Off", "Hide the safe zones"),
    ], default="TIKTOK")

    def execute(self, context):
        sc = context.scene
        sc.zgk_platform = self.platform
        sc.zgk_overlay = True
        cams = ({sc.camera} if sc.camera else set()) | {m.camera for m in sc.timeline_markers if m.camera}
        for c in cams:
            c.data.show_passepartout = True
            c.data.passepartout_alpha = 0.85
        if context.screen:
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
        if self.platform != "NONE":
            self.report({"INFO"}, "Lime box = keep text and product inside (camera view)")
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
        master = context.scene.get("zgk_source", context.scene.name)
        scenes = [s for s in bpy.data.scenes if s.name == master or s.get("zgk_source") == master]
        out_dir = bpy.path.abspath("//zgk_renders") if bpy.data.filepath else os.path.join(
            os.path.expanduser("~"), "zgk_renders")
        os.makedirs(out_dir, exist_ok=True)
        done = []
        for s in scenes:
            r = s.render
            if hasattr(r.image_settings, "media_type"):       # Blender 5+: video is its own media type
                r.image_settings.media_type = "VIDEO"
            r.image_settings.file_format = "FFMPEG"
            r.ffmpeg.format = "MPEG4"
            r.ffmpeg.codec = "H264"
            r.ffmpeg.constant_rate_factor = "HIGH"
            r.ffmpeg.audio_codec = "AAC" if s.sequence_editor else "NONE"   # keep the beat-sync music
            r.filepath = os.path.join(out_dir, s.name + "_")
            # H.264 needs even pixel sizes: e.g. 4:5 (1080x1350) at 50% = 540x675 would fail.
            keep_res = (r.resolution_x, r.resolution_y)
            def eff(v):
                return int(v * r.resolution_percentage / 100)
            while eff(r.resolution_x) % 2:
                r.resolution_x += 1
            while eff(r.resolution_y) % 2:
                r.resolution_y += 1
            try:
                bpy.ops.render.render(animation=True, scene=s.name)
            finally:
                r.resolution_x, r.resolution_y = keep_res
            done.append(s.name)
        self.report({"INFO"}, f"Rendered {len(scenes)} format(s) to {out_dir}")
        return {"FINISHED"}


classes = (ZGK_OT_reframe, ZGK_OT_reframe_nudge, ZGK_OT_reframe_follow, ZGK_OT_reframe_follow_clear, ZGK_OT_safe_zones,
           ZGK_OT_reframe_all, ZGK_OT_render_formats)
