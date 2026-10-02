"""Promo / QA screenshots of the INSTALLED extension in the real Blender UI, on the original demo scene.
Never saves the .blend.
blender demo/zgk_demo.blend -P tests/gui_promo.py -- <shot> <out.png>
shots: before | reframe | beat | loop | help
"""
import os, sys
import bpy

args = sys.argv[sys.argv.index("--") + 1:]
SHOT, OUT = args[0], args[1]
DEMO = os.path.dirname(bpy.data.filepath)
log = lambda *a: print("PROMO", *a)
ORDER = ["ZGK_PT_reframe", "ZGK_PT_beat", "ZGK_PT_loop", "ZGK_PT_wedge", "ZGK_PT_quickstart"]


def panels(open_set):
    """Open exactly the panels in open_set, keeping the sidebar order stable."""
    classes = [getattr(bpy.types, n) for n in ORDER if hasattr(bpy.types, n)]
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    for c in classes:
        c.bl_options = set() if c.bl_idname in open_set else {"DEFAULT_CLOSED"}
        bpy.utils.register_class(c)


def view3d():
    return next(a for a in bpy.context.screen.areas if a.type == "VIEW_3D")


def frame_camera(area):
    space = area.spaces.active
    space.show_region_ui = True
    space.region_3d.view_perspective = "CAMERA"
    space.shading.type = "RENDERED"                   # the real studio look, not the preview HDRI
    space.overlay.show_extras = False
    space.overlay.show_relationship_lines = False
    space.overlay.show_outline_selected = False
    win = [r for r in area.regions if r.type == "WINDOW"][0]
    with bpy.context.temp_override(area=area, region=win):
        bpy.ops.view3d.view_center_camera()


def select(names):
    for o in bpy.context.scene.objects:
        o.select_set(o.name in names)


def setup():
    sc = bpy.context.scene
    area = view3d()
    if SHOT == "before":
        panels({"ZGK_PT_reframe"})
        sc.zgk_overlay = True
        sc.zgk_platform = "NONE"
        sc.frame_set(50)
    elif SHOT == "reframe":
        panels({"ZGK_PT_reframe"})
        bpy.ops.zgk.reframe(aspect="9x16", copy_scene=True)
        v = bpy.context.scene
        v.zgk_subject_collection = next(c for c in v.collection.children_recursive if c.name.startswith("Products"))
        bpy.ops.zgk.safe_zones(platform="TIKTOK")
        bpy.ops.zgk.reframe_follow(use_safe_zone=True, fill=True, follow_y=True)
        v.frame_set(100)
        log("reframed", v.name, v.render.resolution_x, v.render.resolution_y)
    elif SHOT == "beat":
        panels({"ZGK_PT_beat"})
        bpy.ops.zgk.beat_detect(filepath=os.path.join(DEMO, "zgk_beat_120.wav"), add_sound=True)
        select({"Bottle Left", "Bottle Hero", "Bottle Right"})
        bpy.ops.zgk.beat_key(mode="HOP", amount=0.03, decay=8, stagger=2)
        select(set())
        beats = sorted(m.frame for m in sc.timeline_markers if m.name.startswith("beat_"))
        log("beats", len(beats), round(sc.zgk_bpm, 1))
        sc.zgk_overlay = True
        sc.zgk_platform = "NONE"
        sc.frame_set(beats[4] + 3)                                   # mid-hop, dot pulsing
    elif SHOT == "loop":
        panels({"ZGK_PT_loop"})
        select({"Bottle Hero"})
        bpy.ops.zgk.loop_check()
        log("loop issues", sc.zgk_loop_issues)
        select(set())
        sc.frame_set(1)
    elif SHOT == "help":
        panels({"ZGK_PT_quickstart"})
        sc.frame_set(60)
    frame_camera(area)
    return None


def shoot():
    area = view3d()
    for r in area.regions:
        if r.type == "UI" and hasattr(r, "active_panel_category"):
            r.active_panel_category = "ZeroGeometry"
            r.tag_redraw()
    if SHOT == "help":
        win = [r for r in area.regions if r.type == "WINDOW"][0]
        with bpy.context.temp_override(area=area, region=win):
            bpy.ops.zgk.help("INVOKE_DEFAULT", topic="REFRAME")

    def snap():
        bpy.ops.screen.screenshot(filepath=OUT)
        log("SCREENSHOT", OUT)
        bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=0.5)
        return None
    bpy.app.timers.register(snap, first_interval=2.0)
    return None


bpy.app.timers.register(setup, first_interval=2.0)
bpy.app.timers.register(shoot, first_interval=22.0)   # rendered viewport needs to converge
