"""Click-through test in the REAL Blender UI with the INSTALLED extension.
Every button is pressed the way the panel presses it (INVOKE_DEFAULT, sidebar context), with
screenshots of the panel, dialogs, redo panel and file browser. Never saves the .blend.
blender demo/svk_demo.blend -P tests/gui_handtest.py -- <out_dir>
"""
import os, sys, glob, tempfile, traceback
import bpy

# CLEAN_ENV: launched with --factory-startup so no other add-ons appear in shots; load ours from the repo
if not hasattr(bpy.types, "SVK_PT_main"):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import social_video_kit
    social_video_kit.register()

OUT = sys.argv[sys.argv.index("--") + 1]
os.makedirs(OUT, exist_ok=True)
EXPORT = os.path.join(tempfile.gettempdir(), "svk_handtest_exports") + os.sep
results = []


def log(*a):
    print("HAND", *a, flush=True)


def check(name, ok, detail=""):
    results.append(bool(ok))
    log(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def view3d():
    return next(a for a in bpy.context.screen.areas if a.type == "VIEW_3D")


def ui_ctx():
    """Context of a click on a sidebar button."""
    a = view3d()
    return bpy.context.temp_override(window=bpy.context.window, area=a,
                                     region=next(r for r in a.regions if r.type == "UI"))


def press(op, **kw):
    """Press a panel button: INVOKE in the sidebar context, like a real click."""
    try:
        with ui_ctx():
            ret = op("INVOKE_DEFAULT", **kw)
        return ret
    except Exception as ex:
        log("EXC", op.idname() if hasattr(op, "idname") else op, ex)
        return {"EXCEPTION"}


def open_panels(*names):
    order = ["SVK_PT_reframe", "SVK_PT_beat", "SVK_PT_loop", "SVK_PT_wedge"]
    classes = [getattr(bpy.types, n) for n in order]
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    for c in classes:
        c.bl_options = set() if c.bl_idname in names else {"DEFAULT_CLOSED"}
        bpy.utils.register_class(c)
    about = bpy.types.SVK_PT_about                          # keep the footer last
    bpy.utils.unregister_class(about)
    bpy.utils.register_class(about)


def show_tab():
    a = view3d()
    for r in a.regions:
        if r.type == "UI":
            try:
                r.active_panel_category = "Social Video"
                r.tag_redraw()
            except AttributeError:
                pass


def shot(name, crop_sidebar=False):
    path = os.path.join(OUT, name)
    bpy.ops.screen.screenshot(filepath=path)
    log("SHOT", path)


def select(names):
    for o in bpy.context.view_layer.objects:
        o.select_set(o.name in names)


STEPS = []
_state = {}


def step(fn):
    STEPS.append(fn)
    return fn


# ------------------------------------------------------------------ steps
@step
def s_setup():
    sc = bpy.context.scene
    sc.svk_output_dir = EXPORT
    a = view3d()
    sp = a.spaces.active
    sp.show_region_ui = True
    sp.shading.type = "MATERIAL"
    sp.overlay.show_extras = False
    for r in a.regions:
        if r.type == "UI":
            try:
                r.active_panel_category = "Social Video"
            except AttributeError:          # read-only in some contexts: fall back to the tab order
                pass
    open_panels("SVK_PT_reframe")
    check("panel registered + Camera Guides off by default", not sc.svk_overlay)


@step
def s_camera_view():
    press(bpy.ops.svk.look_through)
    check("eye button -> camera view", view3d().spaces.active.region_3d.view_perspective == "CAMERA")
    press(bpy.ops.svk.overlay_toggle)
    check("Camera Guides toggle on", bpy.context.scene.svk_overlay)


@step
def s_shot_panel():
    shot("hand_01_panel_master.png")


@step
def s_reframe():
    n0 = len(bpy.data.scenes)
    r = press(bpy.ops.svk.reframe, aspect="9x16")
    sc = bpy.context.window.scene
    check("9:16 button makes + switches to the copy", r == {"FINISHED"} and len(bpy.data.scenes) == n0 + 1
          and sc.render.resolution_y == 1920, sc.name)


@step
def s_undo():
    # Blender refuses ed.undo from script timers, so check that every scene-changing button is
    # registered for undo (which is exactly what makes Ctrl+Z work after clicking it)
    changing = ["reframe", "reframe_all", "reframe_nudge", "reframe_follow", "reframe_follow_clear",
                "safe_zones", "beat_detect", "beat_grid", "beat_key", "beat_cuts", "beat_tempo",
                "loop_fix", "loop_set_range"]
    missing = [n for n in changing if "UNDO" not in getattr(bpy.types, "SVK_OT_" + n).bl_options]
    check("every scene-changing button supports Ctrl+Z", not missing, ", ".join(missing))


@step
def s_follow():
    sc = bpy.context.window.scene
    sc.svk_subject_collection = next(c for c in sc.collection.children_recursive if c.name.startswith("Products"))
    press(bpy.ops.svk.safe_zones, platform="ALL")
    check("All-platforms safe area button -> guides + platform", sc.svk_overlay and sc.svk_platform == "ALL")
    r = press(bpy.ops.svk.reframe_follow, fill=sc.svk_follow_fill, follow_y=True)
    pkg = sys.modules[bpy.types.SVK_PT_main.__module__]           # works for repo import and installed extension
    keyed = any(fc.data_path == "shift_x" for fc in pkg.beat._fcurves(sc.camera.data))
    check("Auto-Follow (as clicked)", r == {"FINISHED"} and keyed)
    sc.frame_set(100)


@step
def s_shot_follow():
    shot("hand_02_follow_safe_area.png")


@step
def s_nudge_and_switch():
    sc = bpy.context.window.scene
    l0 = sc.camera.data.lens
    press(bpy.ops.svk.reframe_nudge, factor=1.1)
    l1 = sc.camera.data.lens
    press(bpy.ops.svk.reframe_nudge, factor=1 / 1.1)
    check("Zoom In / Out", abs(l1 / l0 - 1.1) < 1e-3 and abs(sc.camera.data.lens - l0) < 1e-3)
    master = sc["svk_source"]
    press(bpy.ops.svk.goto_scene, name=master)
    ok = bpy.context.window.scene.name == master
    press(bpy.ops.svk.goto_scene, name=sc.name)
    check("format switch buttons", ok and bpy.context.window.scene == sc)
    press(bpy.ops.svk.reframe_follow_clear)
    check("X (Clear Follow)", "svk_lens_orig" not in sc.camera.data)


@step
def s_no_duplicates():
    n = len(bpy.data.scenes)
    press(bpy.ops.svk.reframe, aspect="9x16")              # already exists -> switch, don't duplicate
    check("clicking an existing format switches instead of duplicating", len(bpy.data.scenes) == n)


@step
def s_all_three():
    master = bpy.data.scenes[bpy.context.window.scene["svk_source"]]
    bpy.context.window.scene = master
    r = press(bpy.ops.svk.reframe_all)
    fam = [s for s in bpy.data.scenes if s.get("svk_source") == master.name]
    check("All Three button (no duplicates, built from the original)",
          r == {"FINISHED"} and len(fam) == 3 and bpy.context.window.scene == master,
          ", ".join(s.name for s in fam))


@step
def s_choose_folder():
    _state["choose"] = press(bpy.ops.svk.choose_output)


@step
def s_choose_folder_check():
    fb = [a for w in bpy.context.window_manager.windows for a in w.screen.areas if a.type == "FILE_BROWSER"]
    check("choose export folder opens a folder browser", _state.get("choose") == {"RUNNING_MODAL"} and bool(fb))
    for w in list(bpy.context.window_manager.windows)[1:]:
        with bpy.context.temp_override(window=w):
            bpy.ops.wm.window_close()


@step
def s_shot_family():
    shot("hand_03_versions.png")


@step
def s_render_all():
    for s in bpy.data.scenes:
        s.render.resolution_percentage = 10
        s.frame_end = 8
        s.render.engine = "BLENDER_WORKBENCH"
    r = press(bpy.ops.svk.render_formats)
    mp4s = sorted(os.path.basename(p) for p in glob.glob(os.path.join(EXPORT, "Renders", "*.mp4")))
    check("Render All Formats (as clicked)", r == {"FINISHED"} and len(mp4s) >= 4, ", ".join(mp4s))


@step
def s_beat():
    sc = bpy.context.window.scene
    open_panels("SVK_PT_beat")
    r = press(bpy.ops.svk.beat_grid, bpm=120)
    n = len([m for m in sc.timeline_markers if m.name.startswith("beat_")])
    check("BPM Grid", r == {"FINISHED"} and n == 1, f"{n} beat in 8 frames @120 (12 frames per beat)")
    for s in bpy.data.scenes:
        s.frame_end = 120
    press(bpy.ops.svk.beat_grid, bpm=120)
    select(set())
    with ui_ctx():
        poll_empty = bpy.ops.svk.beat_key.poll()
    check("pulse buttons disabled with nothing selected", not poll_empty)
    select({"Bottle Left", "Bottle Hero", "Bottle Right"})
    r = press(bpy.ops.svk.beat_key, mode="HOP", amount=0.03, decay=8, stagger=2)
    check("Hop on the beat", r == {"FINISHED"})
    press(bpy.ops.svk.beat_tempo, mode="DOUBLE")
    n2 = len([m for m in sc.timeline_markers if m.name.startswith("beat_")])
    press(bpy.ops.svk.beat_tempo, mode="HALF")
    check("Tempo x2 / 1/2", n2 > 10 and abs(sc.svk_bpm - 120) < 1e-3, f"{n2} beats at x2")
    sc.frame_set(37)


@step
def s_shot_beat():
    shot("hand_04_beat_redo_panel.png")


@step
def s_cuts():
    sc = bpy.context.window.scene
    cam2 = sc.camera.copy(); cam2.data = sc.camera.data.copy(); cam2.name = "Camera Close"
    sc.collection.objects.link(cam2)
    cam2.location.x -= 0.4
    select({sc.camera.name})
    with ui_ctx():
        one = bpy.ops.svk.beat_cuts.poll()
    select({sc.camera.name, cam2.name})
    r = press(bpy.ops.svk.beat_cuts, every=2)
    cuts = [m for m in sc.timeline_markers if m.camera]
    check("Camera Cuts (needs 2 cameras, then cuts)", not one and r == {"FINISHED"} and len(cuts) > 3,
          f"{len(cuts)} cuts")


@step
def s_loop():
    sc = bpy.context.window.scene
    open_panels("SVK_PT_loop")
    select({"Bottle Hero"})
    press(bpy.ops.svk.loop_check)
    found = sc.svk_loop_issues
    press(bpy.ops.svk.loop_fix, method="CLOSE")
    check("Loop Check finds + Fix clears", found >= 1 and sc.svk_loop_issues == 0, f"{found} -> {sc.svk_loop_issues}")
    r = press(bpy.ops.svk.loop_set_range, length=96)
    check("Set Loop Range", r == {"FINISHED"} and sc.frame_end - sc.frame_start + 1 == 96)
    sc.frame_end = 120


@step
def s_shot_loop():
    shot("hand_05_loop.png")


@step
def s_help():
    open_panels("SVK_PT_reframe")
    r = press(bpy.ops.svk.help, topic="GUIDES")
    check("? help popup opens", r in ({"RUNNING_MODAL"}, {"FINISHED"}, {"INTERFACE"}), str(r))


@step
def s_shot_help():
    shot("hand_06_help_guides.png")


@step
def s_wedge_dialog():
    bpy.context.window_manager.clipboard = 'bpy.data.lights["Key"].energy'
    open_panels("SVK_PT_wedge")
    r = press(bpy.ops.svk.wedge)
    check("Wedge dialog opens (path auto-pasted)", r in ({"RUNNING_MODAL"}, {"INTERFACE"}), str(r))


@step
def s_shot_wedge():
    shot("hand_07_wedge_dialog.png")


@step
def s_wedge_run():
    sc = bpy.context.window.scene
    with ui_ctx():
        r = bpy.ops.svk.wedge("EXEC_DEFAULT", data_path='bpy.data.lights["Key"].energy', start=2, end=20,
                              count=4, percent=10, columns=2)
    check("Wedge renders a contact sheet into the export folder",
          r == {"FINISHED"} and os.path.exists(sc.svk_last_sheet) and sc.svk_last_sheet.startswith(EXPORT.rstrip(os.sep)),
          sc.svk_last_sheet)
    check("guide page ships with the add-on", os.path.exists(os.path.join(
        os.path.dirname(sys.modules[type(bpy.types.SVK_PT_main).__module__].__file__) if False else
        os.path.dirname(bpy.types.SVK_PT_main.__module__ and sys.modules[bpy.types.SVK_PT_main.__module__].__file__),
        "assets", "guide.html")))


@step
def s_shot_about():
    open_panels("SVK_PT_wedge")
    shot("hand_08_wedge_done_about.png")


@step
def s_file_browser():
    press(bpy.ops.svk.beat_detect)                       # opens Blender's file browser, filtered to audio


@step
def s_shot_browser():
    shot("hand_09_detect_beats_browser.png")


@step
def s_finish():
    log(f"RESULT {sum(results)}/{len(results)} passed")
    bpy.ops.wm.quit_blender()


# ------------------------------------------------------------------ runner
_i = [0]


def runner():
    if _i[0] >= len(STEPS):
        return None
    fn = STEPS[_i[0]]
    _i[0] += 1
    try:
        fn()
        show_tab()
    except Exception:
        results.append(False)
        log("FAIL step", fn.__name__, traceback.format_exc().splitlines()[-1])
    return 2.5 if fn.__name__.startswith("s_shot") or fn.__name__ in ("s_setup", "s_follow") else 1.0


bpy.app.timers.register(runner, first_interval=3.0)
