"""Loop Doctor: find what breaks a seamless loop (curves that don't return to their start value,
movie/sequence textures that clamp instead of cycling) and fix it."""
import bpy
from bpy.props import EnumProperty, FloatProperty
from .beat import _fcurves


def _anim_blocks(context, selected_only):
    objs = context.selected_objects if selected_only else context.scene.objects
    seen = set()
    for ob in objs:
        for idb in (ob, getattr(ob, "data", None)):
            if idb is not None and idb.animation_data and id(idb) not in seen:
                seen.add(id(idb))
                yield ob.name, idb
        for slot in getattr(ob, "material_slots", []):
            m = slot.material
            if m and m.use_nodes and m.node_tree.animation_data and id(m) not in seen:
                seen.add(id(m))
                yield ob.name, m.node_tree


def loop_report(context, selected_only=True, tol=1e-4):
    """[(owner, data_path, index, start_value, end_value)] for curves that don't close the loop."""
    sc = context.scene
    f0, f1 = sc.frame_start, sc.frame_end + 1          # frame_end+1 must equal frame_start
    bad = []
    for owner, idb in _anim_blocks(context, selected_only):
        for fc in _fcurves(idb):
            if any(m.type == "CYCLES" for m in fc.modifiers):
                continue
            a, b = fc.evaluate(f0), fc.evaluate(f1)
            if abs(a - b) > tol * max(1.0, abs(a)):
                bad.append((owner, fc.data_path, fc.array_index, a, b))
    return bad


def texture_report(context):
    """Image textures playing a movie/sequence that won't loop over the scene range."""
    sc = context.scene
    length = sc.frame_end - sc.frame_start + 1
    issues = []
    for m in bpy.data.materials:
        if not (m.use_nodes and m.node_tree):
            continue
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image and n.image.source in {"MOVIE", "SEQUENCE"}:
                iu = n.image_user
                if not iu.use_cyclic:
                    issues.append((m.name, n.name, "not cyclic"))
                elif iu.frame_offset > 0:
                    # Blender adds the offset AFTER wrapping, so late frames ask for frames past the clip
                    # end and hold on the last one -- re-cut the clip instead of offsetting it
                    issues.append((m.name, n.name, "frame offset > 0: late frames will freeze on the last clip frame"))
                elif length % max(1, iu.frame_duration):
                    issues.append((m.name, n.name, f"clip is {iu.frame_duration} frames, loop is {length}: not a multiple"))
    return issues


class ZGK_OT_loop_check(bpy.types.Operator):
    """Report every animation curve / texture that breaks a seamless loop over the scene range"""
    bl_idname = "zgk.loop_check"
    bl_label = "Check Loop"

    def execute(self, context):
        bad = loop_report(context, selected_only=bool(context.selected_objects))
        tex = texture_report(context)
        for owner, path, idx, a, b in bad[:40]:
            self.report({"WARNING"}, f"{owner}: {path}[{idx}] starts {a:.4g}, ends {b:.4g}")
        for mat, node, why in tex:
            self.report({"WARNING"}, f"{mat}/{node}: {why}")
        if not bad and not tex:
            self.report({"INFO"}, "Loop is seamless")
        else:
            self.report({"INFO"}, f"{len(bad)} curve(s) and {len(tex)} texture(s) break the loop")
        context.scene.zgk_loop_issues = len(bad) + len(tex)
        return {"FINISHED"}


class ZGK_OT_loop_fix(bpy.types.Operator):
    """Make the animation loop seamlessly over the scene frame range"""
    bl_idname = "zgk.loop_fix"
    bl_label = "Fix Loop"
    bl_options = {"REGISTER", "UNDO"}

    method: EnumProperty(name="Method", items=[
        ("CLOSE", "Close the loop", "Key the start value one frame after the end (keeps timing)"),
        ("CYCLES", "Cycles modifier", "Repeat each curve's key range forever"),
        ("BOTH", "Close + Cycles", "Close the loop, then repeat it"),
    ], default="CLOSE")

    def execute(self, context):
        sc = context.scene
        f0, f1 = sc.frame_start, sc.frame_end + 1
        fixed = 0
        for owner, idb in _anim_blocks(context, bool(context.selected_objects)):
            for fc in _fcurves(idb):
                if self.method in {"CLOSE", "BOTH"}:
                    a, b = fc.evaluate(f0), fc.evaluate(f1)
                    if abs(a - b) > 1e-6:
                        fc.keyframe_points.insert(f1, a, options={"FAST"})
                        # drop keys that extended past the loop end
                        for kp in [k for k in fc.keyframe_points if k.co.x > f1 + 1e-6]:
                            fc.keyframe_points.remove(kp, fast=True)
                        fc.update()
                        fixed += 1
                if self.method in {"CYCLES", "BOTH"} and not any(m.type == "CYCLES" for m in fc.modifiers):
                    fc.modifiers.new("CYCLES")
                    fixed += 1
        for m in bpy.data.materials:
            if m.use_nodes and m.node_tree:
                for n in m.node_tree.nodes:
                    if n.type == "TEX_IMAGE" and n.image and n.image.source in {"MOVIE", "SEQUENCE"}:
                        iu = n.image_user
                        iu.use_cyclic = True
                        iu.use_auto_refresh = True
                        if iu.frame_offset > 0:
                            # shift the playback start instead of offsetting (offset is applied after wrap)
                            iu.frame_start -= iu.frame_offset
                            iu.frame_offset = 0
        self.report({"INFO"}, f"Fixed {fixed} curve(s)")
        return {"FINISHED"}


class ZGK_OT_loop_set_range(bpy.types.Operator):
    """Set the scene range to a whole number of loops of a given length"""
    bl_idname = "zgk.loop_set_range"
    bl_label = "Set Loop Range"
    bl_options = {"REGISTER", "UNDO"}

    length: FloatProperty(name="Loop length (frames)", default=112, min=2)

    def execute(self, context):
        sc = context.scene
        sc.frame_end = sc.frame_start + round(self.length) - 1
        return {"FINISHED"}


classes = (ZGK_OT_loop_check, ZGK_OT_loop_fix, ZGK_OT_loop_set_range)
