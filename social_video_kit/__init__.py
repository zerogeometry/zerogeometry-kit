"""Social Video Kit -- tools for making social-media video in Blender.
Vertical Reframe (+ auto-follow, safe areas, all formats), Beat Sync, Loop Doctor, Wedge Batch.
Panel: 3D Viewport > Sidebar (N) > Social Video
"""
import os
import bpy
from bpy.props import FloatProperty, IntProperty, PointerProperty, BoolProperty, EnumProperty, StringProperty
from . import paths, reframe, beat, loop, wedge, overlay, help

MODULES = (paths, reframe, beat, loop, wedge, overlay, help)
FORMAT_TEXT = {"16x9": "16:9", "9x16": "9:16", "4x5": "4:5", "1x1": "1:1"}


def step(layout, n, text):
    """Section heading: numbered step."""
    row = layout.row()
    row.label(text=f"{n}  ·  {text}")
    return row


# ---------------------------------------------------------------- panels
class SVK_PT_base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Social Video"


class SVK_PT_main(SVK_PT_base, bpy.types.Panel):
    bl_label = "Social Video Kit"
    bl_idname = "SVK_PT_main"

    def draw_header(self, context):
        self.layout.label(text="", icon="SEQUENCE")

    def draw(self, context):
        sc, l = context.scene, self.layout
        box = l.box()
        col = box.column(align=True)
        fam = reframe.family(sc)
        master = sc.get("svk_source", sc.name)
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
                row.operator("svk.goto_scene", text=FORMAT_TEXT.get(lab, lab),
                             depress=(s == sc)).name = s.name
        if not sc.camera:
            col.label(text="Add a camera to get started", icon="ERROR")
        row = l.row(align=True)
        row.scale_y = 1.2
        row.operator("svk.overlay_toggle", text="Camera Guides", depress=sc.svk_overlay, icon="OVERLAY")
        row.operator("svk.look_through", text="", icon="HIDE_OFF")
        row.operator("svk.help", text="", icon="QUESTION").topic = "GUIDES"


class SVK_PT_child(SVK_PT_base):
    bl_parent_id = "SVK_PT_main"
    help_topic = "QUICKSTART"

    def draw_header_preset(self, context):
        self.layout.operator("svk.help", text="", icon="QUESTION", emboss=False).topic = self.help_topic


class SVK_PT_reframe(SVK_PT_child, bpy.types.Panel):
    bl_label = "Vertical Reframe"
    bl_idname = "SVK_PT_reframe"
    help_topic = "REFRAME"

    def draw(self, context):
        sc, l = context.scene, self.layout
        on_copy = "svk_source" in sc

        step(l, 1, "make the format")
        col = l.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.5
        for asp in ("9x16", "4x5", "1x1"):
            row.operator("svk.reframe", text=FORMAT_TEXT[asp]).aspect = asp
        col.operator("svk.reframe_all", text="All Three", icon="DUPLICATE")
        if on_copy:
            row = col.row(align=True)
            row.operator("svk.reframe_nudge", text="Zoom In", icon="ZOOM_IN").factor = 1.1
            row.operator("svk.reframe_nudge", text="Zoom Out", icon="ZOOM_OUT").factor = 1 / 1.1

        l.separator()
        step(l, 2, "keep the subject in frame")
        box = l.box()
        col = box.column(align=True)
        col.prop(sc, "svk_subject", text="Object")
        col.prop(sc, "svk_subject_collection", text="or Coll.")
        has_subject = bool(sc.svk_subject or sc.svk_subject_collection)
        row = box.row(align=True)
        row.scale_y = 1.3
        row.enabled = has_subject and bool(sc.camera)
        op = row.operator("svk.reframe_follow", icon="CON_CAMERASOLVER")
        op.fill = sc.svk_follow_fill
        op.follow_y = sc.render.resolution_y > sc.render.resolution_x
        row.operator("svk.reframe_follow_clear", text="", icon="X")
        box.prop(sc, "svk_follow_fill")
        if not has_subject:
            box.label(text="Pick the product to follow", icon="INFO")

        l.separator()
        step(l, 3, "check the app's safe area")
        col = l.column(align=True)
        on = sc.svk_overlay
        row = col.row(align=True)
        row.operator("svk.safe_zones", text="All Platforms", icon="CHECKMARK",
                     depress=on and sc.svk_platform == "ALL").platform = "ALL"
        row.operator("svk.safe_zones", text="Off", depress=not on or sc.svk_platform == "NONE").platform = "NONE"
        row = col.row(align=True)
        for key, lab in (("TIKTOK", "TikTok"), ("REELS", "Reels"), ("SHORTS", "Shorts")):
            row.operator("svk.safe_zones", text=lab, depress=on and sc.svk_platform == key).platform = key

        l.separator()
        step(l, 4, "export")
        col = l.column(align=True)
        row = col.row(align=True)
        row.prop(sc, "svk_output_dir", text="", icon="FILE_FOLDER")
        row.operator("svk.choose_output", text="", icon="FILEBROWSER")
        row = col.row(align=True)
        if sc.svk_output_dir.startswith("//"):                      # say where '//' points, in plain words
            row.label(text="next to your .blend file" if bpy.data.filepath else "in Videos (file not saved yet)")
        else:
            row.label(text="custom folder")
        row.operator("svk.open_output", text="Open", icon="FOLDER_REDIRECT").sub = ""
        row = l.row()
        row.scale_y = 1.5
        row.enabled = bool(sc.camera)
        row.operator("svk.render_formats", text=f"Render All Formats  ({len(reframe.family(sc))})",
                     icon="RENDER_ANIMATION")


class SVK_PT_beat(SVK_PT_child, bpy.types.Panel):
    bl_label = "Beat Sync"
    bl_idname = "SVK_PT_beat"
    help_topic = "BEAT"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        sc, l = context.scene, self.layout
        n = len(beat.beat_frames(sc))
        box = l.box()
        box.label(text=(f"{n} beats  ·  {sc.svk_bpm:.1f} BPM" if n else "No beats yet"),
                  icon="SOUND" if n else "INFO")
        row = l.row(align=True)
        row.scale_y = 1.3
        row.operator("svk.beat_detect", text="Detect Beats", icon="FILE_SOUND")
        row.operator("svk.beat_grid", text="BPM Grid", icon="SNAP_INCREMENT")
        if n:
            row = l.row(align=True)
            row.operator("svk.beat_tempo", text="Tempo ½").mode = "HALF"
            row.operator("svk.beat_tempo", text="Tempo ×2").mode = "DOUBLE"
        l.separator()
        sel = len(context.selected_objects)
        l.label(text=f"pulse {sel} selected on the beat" if sel else "select objects to pulse on the beat")
        grid = l.grid_flow(columns=2, align=True)
        for mode, label, ic in (("BOUNCE", "Squash", "MOD_SIMPLEDEFORM"), ("HOP", "Hop", "ANIM"),
                                ("FLASH", "Light", "LIGHT"), ("EMIT", "Glow", "SHADING_RENDERED")):
            grid.operator("svk.beat_key", text=label, icon=ic).mode = mode
        l.operator("svk.beat_cuts", icon="VIEW_CAMERA")


class SVK_PT_loop(SVK_PT_child, bpy.types.Panel):
    bl_label = "Loop Doctor"
    bl_idname = "SVK_PT_loop"
    help_topic = "LOOP"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        sc, l = context.scene, self.layout
        issues = sc.svk_loop_issues
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
        row.operator("svk.loop_check", text="Check", icon="VIEWZOOM")
        row.operator("svk.loop_fix", text="Fix", icon="CHECKMARK")
        l.operator("svk.loop_set_range", icon="PREVIEW_RANGE")


class SVK_PT_wedge(SVK_PT_child, bpy.types.Panel):
    bl_label = "Wedge Batch"
    bl_idname = "SVK_PT_wedge"
    help_topic = "WEDGE"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        sc, l = context.scene, self.layout
        col = l.column(align=True)
        col.label(text="right-click a number field >")
        col.label(text="Copy Full Data Path, then:")
        row = l.row()
        row.scale_y = 1.3
        row.operator("svk.wedge", icon="IMGDISPLAY")
        if sc.svk_last_sheet and os.path.exists(sc.svk_last_sheet):
            l.operator("svk.open_file", text="Open Last Contact Sheet", icon="IMAGE_DATA").filepath = sc.svk_last_sheet


class SVK_PT_about(SVK_PT_base, bpy.types.Panel):
    bl_label = ""
    bl_idname = "SVK_PT_about"
    bl_parent_id = "SVK_PT_main"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        l = self.layout
        l.separator()
        row = l.row(align=True)
        row.operator("svk.open_guide", text="Guide", icon="HELP")
        row.operator("svk.help", text="Quick Start", icon="QUESTION").topic = "QUICKSTART"
        row = l.row()
        row.alignment = "CENTER"
        row.label(text=f"v{help.VERSION}")


class SVK_AP_prefs(bpy.types.AddonPreferences):
    bl_idname = __package__

    def draw(self, context):
        l = self.layout
        row = l.row()
        row.label(text="Panel: 3D Viewport > Sidebar (N) > Social Video", icon="INFO")
        row.operator("svk.open_guide", text="Guide", icon="HELP")


PANELS = (SVK_PT_main, SVK_PT_reframe, SVK_PT_beat, SVK_PT_loop, SVK_PT_wedge, SVK_PT_about)
PROPS = {
    "svk_bpm": FloatProperty(name="BPM", default=0.0),
    "svk_loop_issues": IntProperty(default=-1),
    "svk_reframe_zoom": FloatProperty(name="Reframe zoom", default=1.0),
    "svk_subject": PointerProperty(name="Subject", type=bpy.types.Object,
                                   description="The product / character to keep in frame"),
    "svk_subject_collection": PointerProperty(name="Subject collection", type=bpy.types.Collection,
                                              description="Keep every object in this collection in frame"),
    "svk_overlay": BoolProperty(name="Camera Guides", default=False),
    "svk_follow_fill": BoolProperty(name="Fill frame (zoom in too)", default=True,
                                    description="Auto-Follow also zooms in so a small subject fills the safe area"),
    "svk_platform": EnumProperty(name="Platform", items=[
        ("ALL", "All platforms", ""), ("TIKTOK", "TikTok", ""), ("REELS", "Instagram Reels", ""),
        ("SHORTS", "YouTube Shorts", ""), ("NONE", "Off", "")], default="NONE"),
    "svk_output_dir": StringProperty(name="Export Folder", default=paths.DEFAULT,      # plain field: no red
                                                                                       # 'missing' warning
                                     description="Where renders and wedge sheets are saved. '//' means next to "
                                                 "your .blend; unsaved files use Videos/Social Video Exports"),
    "svk_last_sheet": StringProperty(default=""),
    "svk_last_export": StringProperty(default=""),
}


def register():
    for name, prop in PROPS.items():
        setattr(bpy.types.Scene, name, prop)
    for m in MODULES:
        for c in m.classes:
            bpy.utils.register_class(c)
    bpy.utils.register_class(SVK_AP_prefs)
    for p in PANELS:
        bpy.utils.register_class(p)
    overlay.register_handler()


def unregister():
    overlay.unregister_handler()
    for p in reversed(PANELS):
        bpy.utils.unregister_class(p)
    bpy.utils.unregister_class(SVK_AP_prefs)
    for m in reversed(MODULES):
        for c in reversed(m.classes):
            bpy.utils.unregister_class(c)
    for name in PROPS:
        delattr(bpy.types.Scene, name)
