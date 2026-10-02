"""ZeroGeometry Kit demo scene: original products + a generated beat track (no third-party brands or music).
blender -b -P demo/build_demo.py      -> demo/zgk_demo.blend + demo/zgk_beat_120.wav
"""
import os, math, wave, struct
import bpy, bmesh

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "zerogeometry_kit", "assets")
END = 120                                   # 5 s @ 24 fps = 10 beats at 120 BPM


def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return (*[v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c], 1.0)
LIME, INK, WHITE = srgb("#CCFF00"), srgb("#0A0A0A"), srgb("#F2F2F2")

# ---------------------------------------------------------------- original beat track (synthesised)
wav = os.path.join(HERE, "zgk_beat_120.wav")
rate, secs = 22050, 8
with wave.open(wav, "w") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    buf = bytearray()
    for i in range(rate * secs):
        t = i / rate
        b = t % 0.5                                                  # beat every 0.5 s = 120 BPM
        kick = math.sin(2 * math.pi * (55 + 90 * math.exp(-b * 40)) * b) * math.exp(-b * 9) if b < 0.3 else 0
        h = (t + 0.25) % 0.5                                         # off-beat hat
        hat = (((i * 1103515245 + 12345) >> 16) % 2000 / 1000 - 1) * math.exp(-h * 70) * 0.25 if h < 0.05 else 0
        buf += struct.pack("<h", int(max(-1, min(1, kick * 0.9 + hat)) * 30000))
    w.writeframes(bytes(buf))

# ---------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.name = "ZG Demo"
sc.frame_start, sc.frame_end = 1, END
sc.render.fps = 24
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
col = sc.collection


def mat(name, color, rough=0.4, metal=0.0, emit=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = color
        b.inputs["Emission Strength"].default_value = emit
    return m


# studio: ink cyclorama with a glossy floor
bm = bmesh.new()
prof = [(3.0 - i * 0.1, 0.0) for i in range(34)]
for i in range(25):
    a = (math.pi / 2) * i / 24
    prof.append((-0.3 - 0.5 * math.sin(a), 0.5 * (1 - math.cos(a))))
prof.append((-0.8, 3.0))
rows = [[bm.verts.new((x, y, z)) for (x, z) in prof] for y in (-3.0, 3.0)]
for i in range(len(prof) - 1):
    f = bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1])); f.smooth = True
me = bpy.data.meshes.new("Cyc"); bm.to_mesh(me); bm.free()
cyc = bpy.data.objects.new("Studio", me); col.objects.link(cyc)
me.materials.append(mat("Studio Ink", srgb("#141414"), rough=0.75, coat=0.0))

# lime light strip on the wall (the brand accent)
bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.62, 0, 0.42))
strip = bpy.context.object; strip.name = "Lime Strip"
strip.scale = (0.01, 1.4, 0.006)
strip.data.materials.append(mat("Lime Glow", LIME, emit=12))


BODY_H = 0.205
LOGO_W, LOGO_Z = 0.052, 0.085            # printed mark: width (m) and centre height on the bottle


def printed(name, color, rough, coat, logo_png):
    """Bottle material with the ZG mark printed into it (UV-mapped, follows the curve, same gloss)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Coat Weight"].default_value = coat
    uv = nt.nodes.new("ShaderNodeUVMap")
    mp = nt.nodes.new("ShaderNodeMapping")
    # front of the bottle is u = 0.5; the label occupies LOGO_W of the circumference around it
    circ = 2 * math.pi * 0.04
    du, dv = LOGO_W / circ, LOGO_W / BODY_H
    mp.inputs["Location"].default_value = (-(0.5 - du / 2) / du, -(LOGO_Z / BODY_H - dv / 2) / dv, 0)
    mp.inputs["Scale"].default_value = (1 / du, 1 / dv, 1)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(ASSETS, logo_png), check_existing=True)
    tex.extension = "CLIP"
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs["A"].default_value = color
    L = nt.links.new
    L(uv.outputs["UV"], mp.inputs["Vector"])
    L(mp.outputs["Vector"], tex.inputs["Vector"])
    L(tex.outputs["Alpha"], mix.inputs["Factor"])
    L(tex.outputs["Color"], mix.inputs["B"])
    L(mix.outputs["Result"], bsdf.inputs["Base Color"])
    return m


def bottle(name, body, cap, y):
    """Original product: rounded bottle + cap, ZG mark printed in its material. Front faces +X."""
    prof = [(0, 0), (0.033, 0), (0.038, 0.004), (0.04, 0.012), (0.04, 0.14), (0.036, 0.165),
            (0.024, 0.185), (0.014, 0.195), (0.014, 0.205), (0, 0.205)]
    bm = bmesh.new()
    seg = 96
    # angle starts at -pi so the front (+X) sits at u = 0.5, far from the UV seam at the back
    ring = [[bm.verts.new((r * math.cos(2 * math.pi * i / seg - math.pi),
                           r * math.sin(2 * math.pi * i / seg - math.pi), z))
             for i in range(seg)] for r, z in prof]
    uvl = bm.loops.layers.uv.new("UVMap")
    for p in range(len(prof) - 1):
        for i in range(seg):
            j = (i + 1) % seg
            f = bm.faces.new((ring[p][i], ring[p][j], ring[p + 1][j], ring[p + 1][i])); f.smooth = True
            for loop, u, z in zip(f.loops, (i / seg, (i + 1) / seg, (i + 1) / seg, i / seg),
                                  (prof[p][1], prof[p][1], prof[p + 1][1], prof[p + 1][1])):
                loop[uvl].uv = (u, z / BODY_H)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    ob.location = (0, y, 0)
    me.materials.append(body)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.017, depth=0.04, location=(0, 0, 0.222))
    c = bpy.context.object; c.name = name + " Cap"; c.parent = ob
    bpy.ops.object.shade_smooth(); c.data.materials.append(cap)
    c.modifiers.new("Bevel", "BEVEL").width = 0.003
    return ob


black = printed("Matte Black", srgb("#111111"), 0.55, 0.0, "zg_icon_lime.png")
white = printed("Soft White", WHITE, 0.3, 0.5, "zg_icon_lime.png")
lime = printed("Lime Gloss", LIME, 0.25, 0.8, "zg_icon_white.png")
capl = mat("Cap Lime", LIME, rough=0.3, metal=0.3)
capb = mat("Cap Black", srgb("#0D0D0D"), rough=0.2, metal=0.8)
products = bpy.data.collections.new("Products")
col.children.link(products)
for name, body, cap, y in (("Bottle Left", white, capb, -0.13), ("Bottle Hero", black, capl, 0.0),
                           ("Bottle Right", lime, capb, 0.13)):
    ob = bottle(name, body, cap, y)
    col.objects.unlink(ob); products.objects.link(ob)
hero = bpy.data.objects["Bottle Hero"]
# the hero turns slowly so it reads as 3D
hero.rotation_euler = (0, 0, math.radians(-25)); hero.keyframe_insert("rotation_euler", index=2, frame=1)
hero.rotation_euler = (0, 0, math.radians(25)); hero.keyframe_insert("rotation_euler", index=2, frame=END)

# camera: a 16:9 dolly that slides past the products (the product drifts out of a 9:16 frame)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")); col.objects.link(cam)
cam.data.lens = 50
cam.rotation_euler = (math.radians(88), 0, math.radians(90))
cam.location = (1.0, 0.24, 0.13); cam.keyframe_insert("location", frame=1)
cam.location = (1.0, -0.24, 0.13); cam.keyframe_insert("location", frame=END)
sc.camera = cam

# light: soft key, cool fill, lime rim from behind
def area(name, energy, size, loc, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA"); ld.energy, ld.size, ld.color = energy, size, color[:3]
    lo = bpy.data.objects.new(name, ld); col.objects.link(lo); lo.location = loc
    t = bpy.data.objects.new(name + " Target", None); col.objects.link(t); t.location = (0, 0, 0.1)
    lo.constraints.new("TRACK_TO").target = t
    return ld
for lt in (area("Key", 10, 0.6, (0.6, 0.45, 0.55)), area("Fill", 3, 1.0, (0.7, -0.7, 0.2), (0.85, 0.9, 1))):
    lt.specular_factor = 0.35       # no hard light-panel reflections on the glossy floor
for side, y in (("L", -0.35), ("R", 0.35)):
    rim = area("Lime Rim " + side, 7, 0.06, (-0.3, y, 0.35), LIME)
    rim.specular_factor = 0.15          # rim the bottles, don't paint lime hotspots on the glossy floor
sc.world = bpy.data.worlds.new("Ink"); sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs[0].default_value = INK
sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.4

engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "zgk_demo.blend"))
print("DEMO_BUILT", wav)
