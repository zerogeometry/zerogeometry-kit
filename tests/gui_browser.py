"""Open Detect Beats like a click (file browser), screenshot it, then finish it as the user would by
picking the demo beat track. blender demo/svk_demo.blend -P tests/gui_browser.py -- <out.png>"""
import os, sys
import bpy

OUT = sys.argv[sys.argv.index("--") + 1]
WAV = os.path.join(os.path.dirname(bpy.data.filepath), "svk_beat_120.wav")


def view3d():
    return next(a for a in bpy.context.screen.areas if a.type == "VIEW_3D")


def open_browser():
    a = view3d()
    with bpy.context.temp_override(area=a, region=next(r for r in a.regions if r.type == "UI")):
        r = bpy.ops.svk.beat_detect("INVOKE_DEFAULT")
    print("BROWSER invoke ->", r)
    return None


def snap():
    bpy.ops.screen.screenshot(filepath=OUT)
    fb = [a for w in bpy.context.window_manager.windows for a in w.screen.areas if a.type == "FILE_BROWSER"]
    if fb:
        p = fb[0].spaces.active.params
        print("BROWSER open:", True, "filter:", p.filter_glob)
    else:
        print("BROWSER open:", False)
    return None


def finish():
    sc = bpy.context.scene
    bpy.ops.svk.beat_detect("EXEC_DEFAULT", filepath=WAV)
    n = len([m for m in sc.timeline_markers if m.name.startswith("beat_")])
    se = sc.sequence_editor
    strips = list(getattr(se, "strips_all", None) or getattr(se, "sequences_all", []))
    print("BROWSER after pick:", n, "beats @", round(sc.svk_bpm, 1), "BPM, audio strips:",
          sum(s.type == "SOUND" for s in strips))
    bpy.ops.svk.beat_detect("EXEC_DEFAULT", filepath=WAV)            # run twice: must not stack audio
    strips = list(getattr(se, "strips_all", None) or getattr(se, "sequences_all", []))
    print("BROWSER second run audio strips:", sum(s.type == "SOUND" for s in strips))
    bpy.ops.wm.quit_blender()


bpy.app.timers.register(open_browser, first_interval=3.0)
bpy.app.timers.register(snap, first_interval=6.0)
bpy.app.timers.register(finish, first_interval=8.0)
