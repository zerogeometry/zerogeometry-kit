"""ZeroGeometry Kit -- social-video tools for Blender.
Vertical Reframe (+ auto-follow, safe zones, all formats), Beat Sync, Loop Doctor, Wedge Batch.
Panel: 3D Viewport > Sidebar (N) > ZeroGeometry
"""
import bpy
from bpy.props import FloatProperty, IntProperty, PointerProperty
from . import reframe, beat, loop, wedge

MODULES = (reframe, beat, loop, wedge)


class ZGK_PT_base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ZeroGeometry"


class ZGK_PT_reframe(ZGK_PT_base, bpy.types.Panel):
    bl_label = "Vertical Reframe"
    bl_idname = "ZGK_PT_reframe"

    def draw(self, context):
        sc, l = context.scene, self.layout
        r = sc.render
        l.label(text=f"{sc.name}: {r.resolution_x}x{r.resolution_y}", icon="CAMERA_DATA")
        col = l.column(align=True)
        row = col.row(align=True)
        for asp in ("9x16", "4x5", "1x1"):
            op = row.operator("zgk.reframe", text=asp.replace("x", ":"))
            op.aspect = asp
        col.operator("zgk.reframe_all", icon="DUPLICATE")
        row = l.row(align=True)
        row.operator("zgk.reframe_nudge", text="Zoom In").factor = 1.1
        row.operator("zgk.reframe_nudge", text="Zoom Out").factor = 1 / 1.1
        box = l.box()
        box.label(text="Auto-Follow", icon="TRACKER")
        box.prop(sc, "zgk_subject", text="Object")
        box.prop(sc, "zgk_subject_collection", text="or Collection")
        box.operator("zgk.reframe_follow", icon="CON_CAMERASOLVER")
        row = l.row(align=True)
        for p in ("TIKTOK", "REELS", "SHORTS"):
            row.operator("zgk.safe_zones", text=p.title()).platform = p
        l.operator("zgk.render_formats", icon="RENDER_ANIMATION")


class ZGK_PT_beat(ZGK_PT_base, bpy.types.Panel):
    bl_label = "Beat Sync"
    bl_idname = "ZGK_PT_beat"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        sc, l = context.scene, self.layout
        n = len(beat.beat_frames(sc))
        l.label(text=f"{n} beats" + (f" @ {sc.zgk_bpm:.1f} BPM" if n else ""), icon="SOUND")
        row = l.row(align=True)
        row.operator("zgk.beat_detect", icon="FILE_SOUND")
        row.operator("zgk.beat_grid", icon="SNAP_INCREMENT")
        col = l.column(align=True)
        for mode, label in (("BOUNCE", "Squash Bounce"), ("HOP", "Hop"), ("FLASH", "Light Flash"), ("EMIT", "Emission Flash")):
            col.operator("zgk.beat_key", text=label).mode = mode
        l.operator("zgk.beat_cuts", icon="VIEW_CAMERA")


class ZGK_PT_loop(ZGK_PT_base, bpy.types.Panel):
    bl_label = "Loop Doctor"
    bl_idname = "ZGK_PT_loop"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        l = self.layout
        l.label(text=f"Range {context.scene.frame_start}-{context.scene.frame_end}", icon="FILE_REFRESH")
        row = l.row(align=True)
        row.operator("zgk.loop_check", icon="VIEWZOOM")
        row.operator("zgk.loop_fix", icon="CHECKMARK")
        l.operator("zgk.loop_set_range")


class ZGK_PT_wedge(ZGK_PT_base, bpy.types.Panel):
    bl_label = "Wedge Batch"
    bl_idname = "ZGK_PT_wedge"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        l = self.layout
        l.label(text="Right-click a field > Copy Full Data Path", icon="INFO")
        l.operator("zgk.wedge", icon="IMGDISPLAY")


PANELS = (ZGK_PT_reframe, ZGK_PT_beat, ZGK_PT_loop, ZGK_PT_wedge)
PROPS = {
    "zgk_bpm": FloatProperty(name="BPM", default=0.0),
    "zgk_loop_issues": IntProperty(default=0),
    "zgk_reframe_zoom": FloatProperty(name="Reframe zoom", default=1.0),
    "zgk_subject": PointerProperty(name="Subject", type=bpy.types.Object),
    "zgk_subject_collection": PointerProperty(name="Subject collection", type=bpy.types.Collection),
}


def register():
    for name, prop in PROPS.items():
        setattr(bpy.types.Scene, name, prop)
    for m in MODULES:
        for c in m.classes:
            bpy.utils.register_class(c)
    for p in PANELS:
        bpy.utils.register_class(p)


def unregister():
    for p in reversed(PANELS):
        bpy.utils.unregister_class(p)
    for m in reversed(MODULES):
        for c in reversed(m.classes):
            bpy.utils.unregister_class(c)
    for name in PROPS:
        delattr(bpy.types.Scene, name)
