"""Launch the real Blender UI with the add-on, set up a 9:16 product shot, open the ZeroGeometry sidebar
and camera view with the overlay, then save a screenshot and quit.
blender --factory-startup -P tests/gui_screenshot.py -- <out.png>
"""
import os, sys, math
import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import zerogeometry_kit as zgk
zgk.register()
OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.join(ROOT, "ui.png")


def setup():
    sc = bpy.context.scene
    for o in list(sc.objects):
        bpy.data.objects.remove(o)
    sc.frame_start, sc.frame_end = 1, 48
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    bpy.ops.mesh.primitive_cylinder_add(radius=0.33, depth=1.2, location=(0, -0.8, 0.6))
    can = bpy.context.object
    can.name = "Product"
    m = bpy.data.materials.new("Lime"); m.diffuse_color = (0.8, 1, 0, 1); can.data.materials.append(m)
    bpy.ops.mesh.primitive_plane_add(size=10)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    sc.collection.objects.link(cam)
    cam.location = (7, 0, 1.4); cam.rotation_euler = (math.radians(84), 0, math.radians(90)); cam.data.lens = 40
    sc.camera = cam
    bpy.ops.zgk.beat_grid(bpm=120)
    bpy.ops.zgk.reframe(aspect="9x16", copy_scene=True)
    v = bpy.context.scene
    v.zgk_subject = next(o for o in v.objects if o.name.startswith("Product"))
    bpy.ops.zgk.safe_zones(platform="TIKTOK")
    bpy.ops.zgk.reframe_follow(use_safe_zone=True)
    v.frame_set(2)
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            space = area.spaces.active
            space.show_region_ui = True
            space.region_3d.view_perspective = "CAMERA"
            space.shading.type = "SOLID"
            space.shading.color_type = "MATERIAL"
            for region in area.regions:
                if region.type == "UI":
                    try:
                        region.active_panel_category = "ZeroGeometry"
                    except Exception:
                        pass
            with bpy.context.temp_override(area=area, region=[r for r in area.regions if r.type == "WINDOW"][0]):
                bpy.ops.view3d.view_center_camera()
    return None


def shoot():
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for region in area.regions:
                if region.type == "UI" and hasattr(region, "active_panel_category"):
                    region.active_panel_category = "ZeroGeometry"
                    region.tag_redraw()
    bpy.app.timers.register(lambda: (bpy.ops.screen.screenshot(filepath=OUT), print("SCREENSHOT", OUT),
                                     bpy.ops.wm.quit_blender()) and None, first_interval=1.0)
    return None


def _unused():
    bpy.ops.screen.screenshot(filepath=OUT)
    print("SCREENSHOT", OUT)
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(setup, first_interval=1.5)
bpy.app.timers.register(shoot, first_interval=4.5)
