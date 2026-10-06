"""Where Social Video Kit writes files. One visible, user-changeable folder:
default '//Social Video Exports/' next to the .blend; for a never-saved file, the user's Videos folder."""
import os
import bpy

DEFAULT = "//Social Video Exports/"


def fallback_dir():
    home = os.path.expanduser("~")
    videos = os.path.join(home, "Videos")
    return os.path.join(videos if os.path.isdir(videos) else home, "Social Video Exports")


def output_dir(scene, sub="", create=False):
    raw = (scene.svk_output_dir or DEFAULT).strip()
    if raw.startswith("//") and not bpy.data.filepath:       # unsaved file: '//' has nothing to be relative to
        base = fallback_dir()
    else:
        base = bpy.path.abspath(raw)
    path = os.path.normpath(os.path.join(base, sub)) if sub else os.path.normpath(base)
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def short(path, n=34):
    return path if len(path) <= n else "…" + path[-(n - 1):]


def format_label(scene):
    r = scene.render
    from math import gcd
    g = gcd(r.resolution_x, r.resolution_y) or 1
    w, h = r.resolution_x // g, r.resolution_y // g
    known = {(9, 16): "9x16", (4, 5): "4x5", (1, 1): "1x1", (16, 9): "16x9"}
    return known.get((w, h), f"{r.resolution_x}x{r.resolution_y}")


class SVK_OT_open_output(bpy.types.Operator):
    """Open the export folder in your file browser"""
    bl_idname = "svk.open_output"
    bl_label = "Open Export Folder"

    sub: bpy.props.StringProperty(default="")

    def execute(self, context):
        path = output_dir(context.scene, self.sub, create=True)
        bpy.ops.wm.path_open(filepath=path)
        return {"FINISHED"}


class SVK_OT_open_file(bpy.types.Operator):
    """Open this file with your system's default app"""
    bl_idname = "svk.open_file"
    bl_label = "Open File"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        if not os.path.exists(self.filepath):
            self.report({"WARNING"}, "File not found (was it moved?)")
            return {"CANCELLED"}
        bpy.ops.wm.path_open(filepath=self.filepath)
        return {"FINISHED"}


class SVK_OT_choose_output(bpy.types.Operator):
    """Choose the folder where renders and contact sheets are saved"""
    bl_idname = "svk.choose_output"
    bl_label = "Choose Export Folder"

    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    def invoke(self, context, event):
        self.directory = output_dir(context.scene) + os.sep
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        context.scene.svk_output_dir = self.directory
        return {"FINISHED"}


classes = (SVK_OT_open_output, SVK_OT_open_file, SVK_OT_choose_output)
