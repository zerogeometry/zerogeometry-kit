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
        ims = sc.render.image_settings
        keep = (sc.render.filepath, sc.render.resolution_percentage, ims.file_format)
        keep_media = getattr(ims, "media_type", None)
        sc.render.resolution_percentage = self.percent
        if keep_media is not None:                # Blender 5+: a scene set to video must switch to images
            ims.media_type = "IMAGE"
        ims.file_format = "PNG"
        values = np.linspace(self.start, self.end, self.count)
        tiles = []
        # an animated property would override every wedge value at render time: mute its curve(s)
        muted = []
        try:
            from .beat import _fcurves
            rel = owner.path_from_id(attr)
            for fc in _fcurves(owner.id_data):
                if fc.data_path == rel and (idx is None or fc.array_index == idx) and not fc.mute:
                    fc.mute = True
                    muted.append(fc)
        except Exception:
            pass
        if muted:
            self.report({"INFO"}, "Animated property: its keys are muted during the wedge")
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
            for fc in muted:
                fc.mute = False
            _set(owner, attr, idx, original)
            if keep_media is not None:
                ims.media_type = keep_media
            sc.render.filepath, sc.render.resolution_percentage, ims.file_format = keep
        # ---- ZeroGeometry contact sheet: ink background, header with lime rule, lime value labels
        INK, LIME = (0.039, 0.039, 0.039, 1.0), (0.8, 1.0, 0.0, 1.0)
        th, tw = tiles[0].shape[:2]
        cols = min(self.columns, len(tiles))
        rows = -(-len(tiles) // cols)
        gap = max(6, tw // 50)
        lab = 28                                                # label strip under each tile
        head = 64
        W = (tw + gap) * cols + gap
        H = (th + lab + gap) * rows + gap + head
        sheet = np.empty((H, W, 4), dtype=np.float32)
        sheet[:] = INK
        sheet[H - head:H - head + 3, :] = LIME                   # rule under the header (rows are bottom-up)
        cells = []
        for i, t in enumerate(tiles):
            r, c = divmod(i, cols)
            top = H - head - gap - r * (th + lab + gap)          # top edge of this cell (bottom-up coords)
            x = gap + c * (tw + gap)
            sheet[top - th:top, x:x + tw] = t
            sheet[top - th - lab:top - th, x:x + 3] = LIME       # lime tick beside the value
            cells.append((x, top - th - lab))
        path = os.path.join(out_dir, "wedge_sheet.png")
        sh = bpy.data.images.new("ZGK_Wedge_Sheet", W, H, alpha=True)
        sh.pixels[:] = sheet.ravel()
        sh.filepath_raw = path
        sh.file_format = "PNG"
        sh.save()
        bpy.data.images.remove(sh)
        self._burn_text(path, W, H, head, cells, values)
        with open(os.path.join(out_dir, "wedge_values.txt"), "w") as fh:
            fh.write(f"{self.data_path}\n" + "\n".join(f"{i:02d}: {v:.6g}" for i, v in enumerate(values)))
        self.report({"INFO"}, f"Contact sheet: {path}")
        return {"FINISHED"}

    def _burn_text(self, path, W, H, head, cells, values):
        """Brand type on the sheet: 'ZERO GEOMETRY · WEDGE' header + each tile's value (needs Blender 4.1+)."""
        try:
            import blf, imbuf
            from .overlay import fonts
            f = fonts()
            _draw = blf.draw_buffer if hasattr(blf, "draw_buffer") else blf.draw   # image buffers need draw_buffer
            ib = imbuf.load(path)
            prop = self.data_path.split(".")[-1][:60]
            with blf.bind_imbuf(f.get("light", 0), ib):
                blf.size(f.get("light", 0), 22)
                blf.color(f.get("light", 0), 1, 1, 1, 1)
                blf.position(f.get("light", 0), 16, H - 40, 0)
                _draw(f.get("light", 0), "ZERO ")
                zw = blf.dimensions(f.get("light", 0), "ZERO ")[0]
            with blf.bind_imbuf(f.get("bold", 0), ib):
                blf.size(f.get("bold", 0), 22)
                blf.color(f.get("bold", 0), 1, 1, 1, 1)
                blf.position(f.get("bold", 0), 16 + zw, H - 40, 0)
                _draw(f.get("bold", 0), "GEOMETRY")
                gw = blf.dimensions(f.get("bold", 0), "GEOMETRY")[0]
            with blf.bind_imbuf(f.get("mono", 0), ib):
                m = f.get("mono", 0)
                blf.size(m, 15)
                blf.color(m, 0.8, 1.0, 0.0, 1)
                blf.position(m, 30 + zw + gw, H - 38, 0)
                _draw(m, f"WEDGE  ·  {prop}  ·  {self.start:g} to {self.end:g}")
                blf.color(m, 0.9, 0.9, 0.9, 1)
                for i, ((x, y), v) in enumerate(zip(cells, values)):
                    blf.position(m, x + 10, y + 8, 0)
                    _draw(m, f"{i:02d}   {v:.4g}")
            imbuf.write(ib, filepath=path) if hasattr(imbuf, "write") else ib.save(filepath=path)
        except Exception as ex:                                  # older Blender: sheet still works, no labels
            print("ZeroGeometry Kit: wedge labels skipped:", ex)


classes = (ZGK_OT_wedge,)
