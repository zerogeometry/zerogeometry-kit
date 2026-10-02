"""ZeroGeometry Kit -- social-video tools for Blender.
Vertical Reframe (+ auto-follow, safe zones, all formats), Beat Sync, Loop Doctor, Wedge Batch.
Panel: 3D Viewport > Sidebar (N) > ZeroGeometry
"""
import os
import bpy
import bpy.utils.previews
from bpy.props import FloatProperty, IntProperty, PointerProperty, BoolProperty, EnumProperty, StringProperty
from . import paths, reframe, beat, loop, wedge, overlay, help

MODULES = (paths, reframe, beat, loop, wedge, overlay, help)
_icons = None
FORMAT_TEXT = {"16x9": "16:9", "9x16": "9:16", "4x5": "4:5", "1x1": "1:1"}


def icon(name="zg"):
    return _icons[name].icon_id if _icons and name in _icons else 0


def step(layout, n, text):
    """Section heading: lime-numbered step."""
    row = layout.row()
    row.label(text=f"{n}  ·  {text}")
    return row


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
        box = l.box()
        col = box.column(align=True)
        fam = reframe.family(sc)
        master = sc.get("zgk_source", sc.name)
        col.label(text=master, icon="SCENE_DATA")
        r = sc.render
        lab = paths.format_label(sc)
        col.label(text=f"{FORMAT_TEXT.get(lab, lab)}  ·  {r.resolution_x}×{r.resolution_y}  ·  "
                       f"{sc.frame_end - sc.frame_start + 1} frames", icon="BLANK1")
        if len(fam) > 1:                                   # switch between versions of this shot
            row = col.row(align=True)
            for s in sorted(fam, key=lambda s: list(FORMAT_TEXT).index(paths.format_label(s))
                            if paths.format_label(s) in FORMAT_TEXT else 9):
                lab = paths.format_label(s)
                row.operator("zgk.goto_scene", text=FORMAT_TEXT.get(lab, lab),
                             depress=(s == sc)).name = s.name
        if not sc.camera:
            col.label(text="Add a camera to get started", icon="ERROR")
        row = l.row(align=True)
        row.scale_y = 1.2
        row.operator("zgk.overlay_toggle", text="Camera Guides", depress=sc.zgk_overlay,
                     icon_value=icon("zg_white"))
        row.operator("zgk.look_through", text="", icon="HIDE_OFF")
        row.operator("zgk.help", text="", icon="QUESTION").topic = "GUIDES"


class ZGK_PT_child(ZGK_PT_base):
    bl_parent_id = "ZGK_PT_main"
    help_topic = "QUICKSTART"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=icon("zg"))

    def draw_header_preset(self, context):
        self.layout.operator("zgk.help", text="", icon="QUESTION", emboss=False).topic = self.help_topic


class ZGK_PT_reframe(ZGK_PT_child, bpy.types.Panel):
    bl_label = "Vertical Reframe"
    bl_idname = "ZGK_PT_reframe"
    help_topic = "REFRAME"

    def draw(self, context):
        sc, l = context.scene, self.layout
        on_copy = "zgk_source" in sc

        step(l, 1, "make the format")
        col = l.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.5
        for asp in ("9x16", "4x5", "1x1"):
            row.operator("zgk.reframe", text=FORMAT_TEXT[asp]).aspect = asp
        col.operator("zgk.reframe_all", text="All Three", icon="DUPLICATE")
        if on_copy:
            row = col.row(align=True)
            row.operator("zgk.reframe_nudge", text="Zoom In", icon="ZOOM_IN").factor = 1.1
            row.operator("zgk.reframe_nudge", text="Zoom Out", icon="ZOOM_OUT").factor = 1 / 1.1

        l.separator()
        step(l, 2, "keep the subject in frame")
        box = l.box()
        col = box.column(align=True)
        col.prop(sc, "zgk_subject", text="Object")
        col.prop(sc, "zgk_subject_collection", text="or Coll.")
        has_subject = bool(sc.zgk_subject or sc.zgk_subject_collection)
        row = box.row(align=True)
        row.scale_y = 1.3
        row.enabled = has_subject and bool(sc.camera)
        op = row.operator("zgk.reframe_follow", icon="CON_CAMERASOLVER")
        op.fill = sc.zgk_follow_fill
        op.follow_y = sc.render.resolution_y > sc.render.resolution_x
        row.operator("zgk.reframe_follow_clear", text="", icon="X")
        box.prop(sc, "zgk_follow_fill")
        if not has_subject:
            box.label(text="Pick the product to follow", icon="INFO")

        l.separator()
        step(l, 3, "check platform UI")
        row = l.row(align=True)
        for key, lab in (("TIKTOK", "TikTok"), ("REELS", "Reels"), ("SHORTS", "Shorts"), ("NONE", "Off")):
            row.operator("zgk.safe_zones", text=lab,
                         depress=sc.zgk_overlay and sc.zgk_platform == key).platform = key

        l.separator()
        step(l, 4, "export")
        col = l.column(align=True)
        row = col.row(align=True)
        row.prop(sc, "zgk_output_dir", text="", icon="FILE_FOLDER")
        row.operator("zgk.choose_output", text="", icon="FILEBROWSER")
        row = col.row(align=True)
        if sc.zgk_output_dir.startswith("//"):                      # say where '//' points, in plain words
            row.label(text="next to your .blend file" if bpy.data.filepath else "in Videos (file not saved yet)")
        else:
            row.label(text="custom folder")
        row.operator("zgk.open_output", text="Open", icon="FOLDER_REDIRECT").sub = ""
        row = l.row()
        row.scale_y = 1.5
        row.enabled = bool(sc.camera)
        row.operator("zgk.render_formats", text=f"Render All Formats  ({len(reframe.family(sc))})",
                     icon="RENDER_ANIMATION")


class ZGK_PT_beat(ZGK_PT_child, bpy.types.Panel):
    bl_label = "Beat Sync"
    bl_idname = "ZGK_PT_beat"
    help_topic = "BEAT"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        sc, l = context.scene, self.layout
        n = len(beat.beat_frames(sc))
        box = l.box()
        box.label(text=(f"{n} beats  ·  {sc.zgk_bpm:.1f} BPM" if n else "No beats yet"),
                  icon="SOUND" if n else "INFO")
        row = l.row(align=True)
        row.scale_y = 1.3
        row.operator("zgk.beat_detect", text="Detect Beats", icon="FILE_SOUND")
        row.operator("zgk.beat_grid", text="BPM Grid", icon="SNAP_INCREMENT")
        if n:
            row = l.row(align=True)
            row.operator("zgk.beat_tempo", text="Tempo ½").mode = "HALF"
            row.operator("zgk.beat_tempo", text="Tempo ×2").mode = "DOUBLE"
        l.separator()
        sel = len(context.selected_objects)
        l.label(text=f"pulse {sel} selected on the beat" if sel else "select objects to pulse on the beat")
        grid = l.grid_flow(columns=2, align=True)
        for mode, label, ic in (("BOUNCE", "Squash", "MOD_SIMPLEDEFORM"), ("HOP", "Hop", "ANIM"),
                                ("FLASH", "Light", "LIGHT"), ("EMIT", "Glow", "SHADING_RENDERED")):
            grid.operator("zgk.beat_key", text=label, icon=ic).mode = mode
        l.operator("zgk.beat_cuts", icon="VIEW_CAMERA")


class ZGK_PT_loop(ZGK_PT_child, bpy.types.Panel):
    bl_label = "Loop Doctor"
    bl_idname = "ZGK_PT_loop"
    help_topic = "LOOP"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        sc, l = context.scene, self.layout
        issues = sc.zgk_loop_issues
        box = l.box()
        box.label(text=f"Loop: frames {sc.frame_start}–{sc.frame_end}", icon="FILE_REFRESH")
        if issues > 0:
            box.label(text=f"{issues} thing(s) won't loop", icon="ERROR")
        elif issues == 0:
            box.label(text="Seamless", icon="CHECKMARK")
        scope = f"{len(context.selected_objects)} selected" if context.selected_objects else "all objects"
        l.label(text=f"checks: {scope}")
        row = l.row(align=True)
        row.scale_y = 1.3
        row.operator("zgk.loop_check", text="Check", icon="VIEWZOOM")
        row.operator("zgk.loop_fix", text="Fix", icon="CHECKMARK")
        l.operator("zgk.loop_set_range", icon="PREVIEW_RANGE")


class ZGK_PT_wedge(ZGK_PT_child, bpy.types.Panel):
    bl_label = "Wedge Batch"
    bl_idname = "ZGK_PT_wedge"
    help_topic = "WEDGE"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        sc, l = context.scene, self.layout
        col = l.column(align=True)
        col.label(text="right-click a number field >")
        col.label(text="Copy Full Data Path, then:")
        row = l.row()
        row.scale_y = 1.3
        row.operator("zgk.wedge", icon="IMGDISPLAY")
        if sc.zgk_last_sheet and os.path.exists(sc.zgk_last_sheet):
            l.operator("zgk.open_file", text="Open Last Contact Sheet", icon="IMAGE_DATA").filepath = sc.zgk_last_sheet


class ZGK_PT_about(ZGK_PT_base, bpy.types.Panel):
    bl_label = ""
    bl_idname = "ZGK_PT_about"
    bl_parent_id = "ZGK_PT_main"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        l = self.layout
        l.separator()
        col = l.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.2
        row.operator("wm.url_open", text="zerogeometry.com", icon_value=icon("zg")).url = help.WEBSITE
        row = col.row(align=True)
        row.operator("zgk.open_guide", text="Guide", icon="HELP")
        row.operator("zgk.help", text="Quick Start", icon="QUESTION").topic = "QUICKSTART"
        col = l.column(align=True)
        col.alignment = "CENTER"
        row = col.row(); row.alignment = "CENTER"; row.label(text=f"ZeroGeometry Kit {help.VERSION}")
        row = col.row(); row.alignment = "CENTER"; row.label(text="vision. precision. soul.")


class ZGK_AP_prefs(bpy.types.AddonPreferences):
    bl_idname = __package__

    def draw(self, context):
        l = self.layout
        row = l.row()
        row.label(text=f"ZeroGeometry Kit {help.VERSION}", icon_value=icon("zg"))
        row.operator("wm.url_open", text="zerogeometry.com", icon="URL").url = help.WEBSITE
        row.operator("zgk.open_guide", text="Guide", icon="HELP")
        l.label(text="Panel: 3D Viewport > Sidebar (N) > ZeroGeometry")


PANELS = (ZGK_PT_main, ZGK_PT_reframe, ZGK_PT_beat, ZGK_PT_loop, ZGK_PT_wedge, ZGK_PT_about)
PROPS = {
    "zgk_bpm": FloatProperty(name="BPM", default=0.0),
    "zgk_loop_issues": IntProperty(default=-1),
    "zgk_reframe_zoom": FloatProperty(name="Reframe zoom", default=1.0),
    "zgk_subject": PointerProperty(name="Subject", type=bpy.types.Object,
                                   description="The product / character to keep in frame"),
    "zgk_subject_collection": PointerProperty(name="Subject collection", type=bpy.types.Collection,
                                              description="Keep every object in this collection in frame"),
    "zgk_overlay": BoolProperty(name="Camera Guides", default=False),
    "zgk_follow_fill": BoolProperty(name="Fill frame (zoom in too)", default=True,
                                    description="Auto-Follow also zooms in so a small subject fills the safe area"),
    "zgk_platform": EnumProperty(name="Platform", items=[
        ("TIKTOK", "TikTok", ""), ("REELS", "Reels", ""), ("SHORTS", "Shorts", ""), ("NONE", "Off", "")],
        default="NONE"),
    "zgk_output_dir": StringProperty(name="Export Folder", default=paths.DEFAULT,      # plain field: no red
                                                                                       # 'missing' warning
                                     description="Where renders and wedge sheets are saved. '//' means next to "
                                                 "your .blend; unsaved files use Videos/ZeroGeometry Exports"),
    "zgk_last_sheet": StringProperty(default=""),
    "zgk_last_export": StringProperty(default=""),
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
    bpy.utils.register_class(ZGK_AP_prefs)
    for p in PANELS:
        bpy.utils.register_class(p)
    overlay.register_handler()


def unregister():
    global _icons
    overlay.unregister_handler()
    for p in reversed(PANELS):
        bpy.utils.unregister_class(p)
    bpy.utils.unregister_class(ZGK_AP_prefs)
    for m in reversed(MODULES):
        for c in reversed(m.classes):
            bpy.utils.unregister_class(c)
    for name in PROPS:
        delattr(bpy.types.Scene, name)
    if _icons:
        bpy.utils.previews.remove(_icons)
        _icons = None
