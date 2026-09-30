"""Wedge Batch (Houdini-style wedging): sweep one property across N values, render a still for each,
and assemble a single contact sheet so you can compare variations at a glance."""
import os
import bpy
import numpy as np
from bpy.props import StringProperty, FloatProperty, IntProperty, EnumProperty


def _resolve(path):
    """'bpy.data.objects["Cube"].location[2]' -> (owner, attr, index|None). Only bpy.data paths."""
    if not path.startswith("bpy.data."):
        raise ValueError("Path must start with bpy.data.")
    idx = None
    body = path
    if body.endswith("]") and body[body.rfind("[") + 1:-1].isdigit():
        idx = int(body[body.rfind("[") + 1:-1])
        body = body[:body.rfind("[")]
    owner_expr, attr = body.rsplit(".", 1)
    owner = eval(owner_expr, {"bpy": bpy, "__builtins__": {}})
    return owner, attr, idx


def _get(owner, attr, idx):
    v = getattr(owner, attr)
    return v[idx] if idx is not None else v


def _set(owner, attr, idx, value):
    if idx is None:
        setattr(owner, attr, value)
    else:
        v = getattr(owner, attr)
        v[idx] = value


class ZGK_OT_wedge(bpy.types.Operator):
    """Render one still per value of a property and build a contact sheet"""
    bl_idname = "zgk.wedge"
    bl_label = "Wedge Render"

    data_path: StringProperty(name="Property",
                              description='Full path, e.g. bpy.data.objects["Cube"].location[2] '
                                          '(tip: right-click a field > Copy Full Data Path)')
    start: FloatProperty(name="From", default=0.0)
    end: FloatProperty(name="To", default=1.0)
    count: IntProperty(name="Steps", default=6, min=2, max=64)
    percent: IntProperty(name="Resolution %", default=35, min=5, max=100)
    columns: IntProperty(name="Columns", default=3, min=1, max=12)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520)

    def execute(self, context):
        sc = context.scene
        try:
            owner, attr, idx = _resolve(self.data_path.strip())
            original = _get(owner, attr, idx)
            float(original)
        except Exception as ex:
            self.report({"ERROR"}, f"Can't use that property: {ex}")
            return {"CANCELLED"}
        out_dir = bpy.path.abspath("//zgk_wedge") if bpy.data.filepath else os.path.join(
            os.path.expanduser("~"), "zgk_wedge")
        os.makedirs(out_dir, exist_ok=True)
        keep = (sc.render.filepath, sc.render.resolution_percentage, sc.render.image_settings.file_format)
        sc.render.resolution_percentage = self.percent
        sc.render.image_settings.file_format = "PNG"
        values = np.linspace(self.start, self.end, self.count)
        tiles = []
        try:
            for i, v in enumerate(values):
                _set(owner, attr, idx, type(original)(v) if isinstance(original, int) else float(v))
                sc.render.filepath = os.path.join(out_dir, f"wedge_{i:02d}.png")
                bpy.ops.render.render(write_still=True)
                img = bpy.data.images.load(sc.render.filepath, check_existing=False)
                px = np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)
                tiles.append(px)
                bpy.data.images.remove(img)
        finally:
            _set(owner, attr, idx, original)
            sc.render.filepath, sc.render.resolution_percentage, sc.render.image_settings.file_format = keep
        th, tw = tiles[0].shape[:2]
        cols = min(self.columns, len(tiles))
        rows = -(-len(tiles) // cols)
        gap = max(4, tw // 60)
        sheet = np.ones(((th + gap) * rows + gap, (tw + gap) * cols + gap, 4), dtype=np.float32) * 0.08
        sheet[..., 3] = 1
        for i, t in enumerate(tiles):
            r, c = divmod(i, cols)
            y = sheet.shape[0] - (r + 1) * (th + gap)            # Blender pixels start bottom-left
            x = gap + c * (tw + gap)
            sheet[y:y + th, x:x + tw] = t
        sh = bpy.data.images.new("ZGK_Wedge_Sheet", sheet.shape[1], sheet.shape[0], alpha=True)
        sh.pixels[:] = sheet.ravel()
        sh.filepath_raw = os.path.join(out_dir, "wedge_sheet.png")
        sh.file_format = "PNG"
        sh.save()
        with open(os.path.join(out_dir, "wedge_values.txt"), "w") as fh:
            fh.write(f"{self.data_path}\n" + "\n".join(f"{i:02d}: {v:.6g}" for i, v in enumerate(values)))
        self.report({"INFO"}, f"Contact sheet: {sh.filepath_raw}")
        return {"FINISHED"}


classes = (ZGK_OT_wedge,)
