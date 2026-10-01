"""ZeroGeometry Kit -- social-video tools for Blender.
Vertical Reframe (+ auto-follow, safe zones, all formats), Beat Sync, Loop Doctor, Wedge Batch.
Panel: 3D Viewport > Sidebar (N) > ZeroGeometry
"""
import os
import bpy
import bpy.utils.previews
from bpy.props import FloatProperty, IntProperty, PointerProperty, BoolProperty, EnumProperty
from . import reframe, beat, loop, wedge, overlay

MODULES = (reframe, beat, loop, wedge, overlay)
_icons = None


def icon(name="zg"):
    return _icons[name].icon_id if _icons and name in _icons else 0


# ---------------------------------------------------------------- panels
class ZGK_PT_base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ZeroGeometry"


class ZGK_PT_main(ZGK_PT_base, bpy.types.Panel):
    bl_label = "ZERO GEOMETRY"
    bl_idname = "ZGK_PT_main"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=icon("zg"))

    def draw(self, context):
        sc, l = context.scene, self.layout
        r = sc.render
        row = l.row()
        row.label(text="vision. precision. soul.")
        split = l.split(factor=0.62, align=True)
        split.label(text=f"{r.resolution_x} x {r.resolution_y}  ·  {sc.frame_end - sc.frame_start + 1}f",
                    icon="CAMERA_DATA")
        split.operator("zgk.overlay_toggle", text="Overlay", depress=sc.zgk_overlay, icon_value=icon("zg_white"))


class ZGK_PT_child(ZGK_PT_base):
    bl_parent_id = "ZGK_PT_main"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=icon("zg"))


class ZGK_PT_reframe(ZGK_PT_child, bpy.types.Panel):
    bl_label = "Vertical Reframe"
    bl_idname = "ZGK_PT_reframe"

    def draw(self, context):
        sc, l = context.scene, self.layout
        col = l.column(align=True)
        col.label(text="1  ·  make the format")
        row = col.row(align=True)
        row.scale_y = 1.4
        for asp in ("9x16", "4x5", "1x1"):
            row.operator("zgk.reframe", text=asp.replace("x", ":")).aspect = asp
        col.operator("zgk.reframe_all", icon="DUPLICATE")
        row = col.row(align=True)
        row.operator("zgk.reframe_nudge", text="Zoom In", icon="ZOOM_IN").factor = 1.1
        row.operator("zgk.reframe_nudge", text="Zoom Out", icon="ZOOM_OUT").factor = 1 / 1.1

        col = l.column(align=True)
        col.separator()
        col.label(text="2  ·  keep the subject in frame")
        box = col.box()
        box.prop(sc, "zgk_subject", text="Object")
        box.prop(sc, "zgk_subject_collection", text="or Coll.")
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("zgk.reframe_follow", icon="CON_CAMERASOLVER")
        row.operator("zgk.reframe_follow_clear", text="", icon="X")

        col = l.column(align=True)
        col.separator()
        col.label(text="3  ·  check platform UI")
        row = col.row(align=True)
        for key, lab in (("TIKTOK", "TikTok"), ("REELS", "Reels"), ("SHORTS", "Shorts"), ("NONE", "Off")):
            row.operator("zgk.safe_zones", text=lab, depress=sc.zgk_overlay and sc.zgk_platform == key).platform = key

        col = l.column(align=True)
        col.separator()
        col.label(text="4  ·  ship it")
        row = col.row()
        row.scale_y = 1.4
        row.operator("zgk.render_formats", icon="RENDER_ANIMATION")


class ZGK_PT_beat(ZGK_PT_child, bpy.types.Panel):
    bl_label = "Beat Sync"
    bl_idname = "ZGK_PT_beat"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        sc, l = context.scene, self.layout
        n = len(beat.beat_frames(sc))
        l.label(text=(f"{n} beats  ·  {sc.zgk_bpm:.1f} BPM" if n else "no beats yet"), icon="SOUND")
        row = l.row(align=True)
        row.scale_y = 1.3
        row.operator("zgk.beat_detect", icon="FILE_SOUND")
        row.operator("zgk.beat_grid", icon="SNAP_INCREMENT")
        if n:
            row = l.row(align=True)
            row.operator("zgk.beat_tempo", text="Tempo ½").mode = "HALF"
            row.operator("zgk.beat_tempo", text="Tempo x2").mode = "DOUBLE"
        col = l.column(align=True)
        col.label(text="pulse selected on the beat")
        grid = col.grid_flow(columns=2, align=True)
        for mode, label, ic in (("BOUNCE", "Squash", "MOD_SIMPLEDEFORM"), ("HOP", "Hop", "ANIM"),
                                ("FLASH", "Light", "LIGHT"), ("EMIT", "Glow", "SHADING_RENDERED")):
            grid.operator("zgk.beat_key", text=label, icon=ic).mode = mode
        l.operator("zgk.beat_cuts", icon="VIEW_CAMERA")


class ZGK_PT_loop(ZGK_PT_child, bpy.types.Panel):
    bl_label = "Loop Doctor"
    bl_idname = "ZGK_PT_loop"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        sc, l = context.scene, self.layout
        issues = sc.zgk_loop_issues
        l.label(text=f"frames {sc.frame_start}–{sc.frame_end}" + (f"  ·  {issues} issue(s)" if issues else ""),
                icon="ERROR" if issues else "FILE_REFRESH")
        row = l.row(align=True)
        row.scale_y = 1.3
        row.operator("zgk.loop_check", icon="VIEWZOOM")
        row.operator("zgk.loop_fix", icon="CHECKMARK")
        l.operator("zgk.loop_set_range", icon="PREVIEW_RANGE")


class ZGK_PT_wedge(ZGK_PT_child, bpy.types.Panel):
    bl_label = "Wedge Batch"
    bl_idname = "ZGK_PT_wedge"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        l = self.layout
        l.label(text="right-click a field > Copy Full Data Path")
        row = l.row()
        row.scale_y = 1.3
        row.operator("zgk.wedge", icon="IMGDISPLAY")


PANELS = (ZGK_PT_main, ZGK_PT_reframe, ZGK_PT_beat, ZGK_PT_loop, ZGK_PT_wedge)
PROPS = {
    "zgk_bpm": FloatProperty(name="BPM", default=0.0),
    "zgk_loop_issues": IntProperty(default=0),
    "zgk_reframe_zoom": FloatProperty(name="Reframe zoom", default=1.0),
    "zgk_subject": PointerProperty(name="Subject", type=bpy.types.Object,
                                   description="The product / character to keep in frame"),
    "zgk_subject_collection": PointerProperty(name="Subject collection", type=bpy.types.Collection,
                                              description="Keep every object in this collection in frame"),
    "zgk_overlay": BoolProperty(name="ZeroGeometry overlay", default=False),
    "zgk_platform": EnumProperty(name="Platform", items=[
        ("TIKTOK", "TikTok", ""), ("REELS", "Reels", ""), ("SHORTS", "Shorts", ""), ("NONE", "Off", "")],
        default="NONE"),
}


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    adir = os.path.join(os.path.dirname(__file__), "assets")
    _icons.load("zg", os.path.join(adir, "zg_icon_lime.png"), "IMAGE")
    _icons.load("zg_white", os.path.join(adir, "zg_icon_white.png"), "IMAGE")
    for name, prop in PROPS.items():
        setattr(bpy.types.Scene, name, prop)
    for m in MODULES:
        for c in m.classes:
            bpy.utils.register_class(c)
    for p in PANELS:
        bpy.utils.register_class(p)
    overlay.register_handler()


def unregister():
    global _icons
    overlay.unregister_handler()
    for p in reversed(PANELS):
        bpy.utils.unregister_class(p)
    for m in reversed(MODULES):
        for c in reversed(m.classes):
            bpy.utils.unregister_class(c)
    for name in PROPS:
        delattr(bpy.types.Scene, name)
    if _icons:
        bpy.utils.previews.remove(_icons)
        _icons = None
