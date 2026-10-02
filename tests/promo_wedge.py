"""Promo contact sheet from the demo scene (key light 2 -> 20 W). blender -b demo/zgk_demo.blend -P tests/promo_wedge.py"""
import os, shutil, tempfile
import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sc = bpy.context.scene
sc.zgk_output_dir = os.path.join(tempfile.gettempdir(), "zgk_promo_exports") + os.sep
sc.frame_set(60)
bpy.ops.zgk.wedge(data_path='bpy.data.lights["Key"].energy', start=2, end=20, count=6, percent=30, columns=3)
shutil.copy(sc.zgk_last_sheet, os.path.join(ROOT, "promo", "06_wedge_sheet.png"))
print("PROMO wedge sheet")
