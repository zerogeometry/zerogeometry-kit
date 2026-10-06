"""Beat Sync: detect beats in an audio file, drop timeline markers, and key motion / light / camera
cuts to them. Pure numpy + Blender's bundled `aud` module -- no extra dependencies."""
import math
import bpy
import numpy as np
from bpy.props import StringProperty, FloatProperty, IntProperty, EnumProperty, BoolProperty

MARKER_PREFIX = "beat_"


# ---------------------------------------------------------------- analysis
def load_mono(path):
    import aud
    snd = aud.Sound(bpy.path.abspath(path))
    rate = int(snd.specs[0])
    data = np.asarray(snd.data(), dtype=np.float32)
    if data.ndim == 2:
        data = data.mean(axis=1)
    while rate > 24000:                       # beats live well below 6 kHz: halve the work for full songs
        data = data[: len(data) // 2 * 2].reshape(-1, 2).mean(axis=1)
        rate //= 2
    return data, rate


def onset_envelope(x, rate, hop=512, win=2048):
    """Spectral flux: how much new energy appears per hop, summed over frequency bins."""
    n = 1 + max(0, (len(x) - win) // hop)
    if n < 4:
        return np.zeros(1), hop / rate
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    frames = x[idx] * np.hanning(win)[None, :]
    mag = np.log1p(np.abs(np.fft.rfft(frames, axis=1)) * 10)
    flux = np.maximum(np.diff(mag, axis=0), 0).sum(axis=1)
    flux = np.concatenate([[0.0], flux])
    flux -= np.convolve(flux, np.ones(16) / 16, mode="same")     # remove slow loudness drift
    return np.maximum(flux, 0), hop / rate


def estimate_beats(path, bpm_min=70.0, bpm_max=180.0, bpm_hint=0.0):
    """Returns (bpm, beat_times_seconds)."""
    x, rate = load_mono(path)
    env, dt = onset_envelope(x, rate)
    if bpm_hint > 0:
        bpm = bpm_hint
    else:
        ac = np.correlate(env, env, mode="full")[len(env) - 1:]
        lags = np.arange(len(ac)) * dt
        valid = (lags >= 60.0 / bpm_max) & (lags <= 60.0 / bpm_min)
        if not valid.any():
            return 120.0, []
        # favour musically common tempos a little (log-gaussian around 120 bpm)
        cand = np.where(valid)[0]
        weight = np.exp(-0.5 * (np.log2(60.0 / lags[cand] / 120.0) / 0.9) ** 2)
        best = int(cand[np.argmax(ac[cand] * weight)])
        # sub-frame precision: fit a parabola through the peak and its neighbours
        lag = float(best)
        if 0 < best < len(ac) - 1:
            a, b, c = ac[best - 1], ac[best], ac[best + 1]
            den = a - 2 * b + c
            if den != 0:
                lag += 0.5 * (a - c) / den
        # refine further using the peaks at 2x..4x the lag (errors shrink by the multiple)
        for mult in (2, 3, 4):
            m = int(round(lag * mult))
            if m + 2 >= len(ac):
                break
            lo, hi = max(1, m - 2), m + 3
            pk = lo + int(np.argmax(ac[lo:hi]))
            a, b, c = ac[pk - 1], ac[pk], ac[pk + 1]
            den = a - 2 * b + c
            lag = (pk + (0.5 * (a - c) / den if den != 0 else 0.0)) / mult
        bpm = 60.0 / (lag * dt)
    period = 60.0 / bpm / dt                      # in envelope frames
    # phase: offset whose comb of beat positions collects the most onset energy
    best_phase, best_score = 0.0, -1.0
    for ph in np.linspace(0, period, 64, endpoint=False):
        pos = np.arange(ph, len(env) - 1, period).astype(int)
        s = env[pos].sum()
        if s > best_score:
            best_phase, best_score = ph, s
    beats = np.arange(best_phase, len(env) - 1, period) * dt
    return float(bpm), beats.tolist()


# ---------------------------------------------------------------- helpers
def beat_frames(scene):
    return sorted(m.frame for m in scene.timeline_markers if m.name.startswith(MARKER_PREFIX))


def _fcurves(idb):
    ad = idb.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    return [c for l in act.layers for s in l.strips for b in s.channelbags for c in b.fcurves]


# ---------------------------------------------------------------- operators
class SVK_OT_beat_detect(bpy.types.Operator):
    """Detect beats in an audio file and add timeline markers on every beat"""
    bl_idname = "svk.beat_detect"
    bl_label = "Detect Beats"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.mp3;*.wav;*.flac;*.ogg;*.m4a;*.aac", options={"HIDDEN"})
    bpm_hint: FloatProperty(name="BPM (0 = auto)", default=0.0, min=0.0, max=300.0)
    add_sound: BoolProperty(name="Add sound strip", default=True)
    offset_frames: IntProperty(name="Start frame", default=1)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        sc = context.scene
        try:
            bpm, times = estimate_beats(self.filepath, bpm_hint=self.bpm_hint)
        except Exception as ex:
            self.report({"ERROR"}, f"Could not read audio: {ex}")
            return {"CANCELLED"}
        fps = sc.render.fps / sc.render.fps_base
        for m in [m for m in sc.timeline_markers if m.name.startswith(MARKER_PREFIX)]:
            sc.timeline_markers.remove(m)
        for i, t in enumerate(times):
            sc.timeline_markers.new(f"{MARKER_PREFIX}{i + 1:03d}", frame=self.offset_frames + round(t * fps))
        sc.svk_bpm = bpm
        if self.add_sound:
            if not sc.sequence_editor:
                sc.sequence_editor_create()
            se = sc.sequence_editor
            coll = se.strips if hasattr(se, "strips") else se.sequences     # 4.4+ renamed it
            for old in [st for st in coll if st.get("svk_audio")]:         # re-running replaces our track
                coll.remove(old)
            used = {st.channel for st in coll}
            ch = next(c for c in range(1, 128) if c not in used)
            strip = coll.new_sound("Beat Track", bpy.path.abspath(self.filepath), ch, self.offset_frames)
            strip["svk_audio"] = True
        self.report({"INFO"}, f"{len(times)} beats at {bpm:.1f} BPM")
        return {"FINISHED"}


class SVK_OT_beat_grid(bpy.types.Operator):
    """Add beat markers from a known BPM (no audio needed)"""
    bl_idname = "svk.beat_grid"
    bl_label = "Beat Grid from BPM"
    bl_options = {"REGISTER", "UNDO"}

    bpm: FloatProperty(name="BPM", default=120.0, min=20.0, max=300.0)
    start: IntProperty(name="First beat frame", default=1)

    def execute(self, context):
        sc = context.scene
        fps = sc.render.fps / sc.render.fps_base
        step = 60.0 / self.bpm * fps
        for m in [m for m in sc.timeline_markers if m.name.startswith(MARKER_PREFIX)]:
            sc.timeline_markers.remove(m)
        f, i = float(self.start), 1
        while f <= sc.frame_end:
            sc.timeline_markers.new(f"{MARKER_PREFIX}{i:03d}", frame=round(f))
            f += step
            i += 1
        sc.svk_bpm = self.bpm
        return {"FINISHED"}


class SVK_OT_beat_key(bpy.types.Operator):
    """Key a pulse on selected objects at every Nth beat marker"""
    bl_idname = "svk.beat_key"
    bl_label = "Key Pulses to Beats"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(name="Effect", items=[
        ("BOUNCE", "Squash Bounce", "Squash & stretch on the beat"),
        ("HOP", "Hop", "Jump up on the beat"),
        ("FLASH", "Light Flash", "Light energy spikes (lights only)"),
        ("EMIT", "Emission Flash", "Material emission strength spikes"),
    ], default="BOUNCE")
    every: IntProperty(name="Every N beats", default=1, min=1)
    amount: FloatProperty(name="Amount", default=0.2, min=0.0)
    decay: IntProperty(name="Decay frames", default=6, min=1)
    stagger: IntProperty(name="Stagger frames", default=0, min=0,
                         description="Offset each selected object by this many frames")

    @classmethod
    def poll(cls, context):
        if not context.selected_objects:
            cls.poll_message_set("Select the objects to pulse")
            return False
        if not beat_frames(context.scene):
            cls.poll_message_set("Add beats first (Detect Beats or Beat Grid)")
            return False
        return True

    def execute(self, context):
        beats = beat_frames(context.scene)[::self.every]
        if not beats:
            self.report({"ERROR"}, "No beat markers -- run Detect Beats or Beat Grid first")
            return {"CANCELLED"}
        for n, ob in enumerate(sorted(context.selected_objects, key=lambda o: o.name)):
            off = n * self.stagger
            for b in beats:
                f0, f1 = b + off, b + off + self.decay
                if self.mode == "BOUNCE":
                    base = ob.scale.copy()
                    s = 1 - self.amount
                    ob.scale = (base.x / math.sqrt(s), base.y / math.sqrt(s), base.z * s)
                    ob.keyframe_insert("scale", frame=f0)
                    ob.scale = base
                    ob.keyframe_insert("scale", frame=f0 - 1)
                    ob.keyframe_insert("scale", frame=f1)
                elif self.mode == "HOP":
                    z = ob.location.z
                    ob.keyframe_insert("location", index=2, frame=f0)
                    ob.location.z = z + self.amount
                    ob.keyframe_insert("location", index=2, frame=f0 + self.decay // 2)
                    ob.location.z = z
                    ob.keyframe_insert("location", index=2, frame=f1)
                elif self.mode == "FLASH" and ob.type == "LIGHT":
                    e = ob.data.energy
                    ob.data.keyframe_insert("energy", frame=f0 - 1)
                    ob.data.energy = e * (1 + self.amount * 10)
                    ob.data.keyframe_insert("energy", frame=f0)
                    ob.data.energy = e
                    ob.data.keyframe_insert("energy", frame=f1)
                elif self.mode == "EMIT":
                    for slot in ob.material_slots:
                        m = slot.material
                        if not (m and m.use_nodes):
                            continue
                        for node in m.node_tree.nodes:
                            inp = node.inputs.get("Emission Strength") or (
                                node.inputs.get("Strength") if node.type == "EMISSION" else None)
                            if inp is None:
                                continue
                            v = inp.default_value
                            inp.keyframe_insert("default_value", frame=f0 - 1)
                            inp.default_value = v + self.amount * 10
                            inp.keyframe_insert("default_value", frame=f0)
                            inp.default_value = v
                            inp.keyframe_insert("default_value", frame=f1)
        return {"FINISHED"}


class SVK_OT_beat_cuts(bpy.types.Operator):
    """Cycle through the selected cameras, cutting every N beats (camera-bound markers)"""
    bl_idname = "svk.beat_cuts"
    bl_label = "Camera Cuts on Beats"
    bl_options = {"REGISTER", "UNDO"}

    every: IntProperty(name="Cut every N beats", default=2, min=1)

    @classmethod
    def poll(cls, context):
        if sum(o.type == "CAMERA" for o in context.selected_objects) < 2:
            cls.poll_message_set("Select two or more cameras")
            return False
        if not beat_frames(context.scene):
            cls.poll_message_set("Add beats first (Detect Beats or Beat Grid)")
            return False
        return True

    def execute(self, context):
        sc = context.scene
        cams = sorted((o for o in context.selected_objects if o.type == "CAMERA"), key=lambda o: o.name)
        if not cams:
            self.report({"ERROR"}, "Select one or more cameras")
            return {"CANCELLED"}
        beats = beat_frames(sc)[::self.every]
        for m in [m for m in sc.timeline_markers if m.name.startswith("cut_")]:
            sc.timeline_markers.remove(m)
        for i, b in enumerate(beats):
            m = sc.timeline_markers.new(f"cut_{i + 1:03d}", frame=b)
            m.camera = cams[i % len(cams)]
        self.report({"INFO"}, f"{len(beats)} cuts across {len(cams)} cameras")
        return {"FINISHED"}


class SVK_OT_beat_tempo(bpy.types.Operator):
    """Double or halve the detected tempo (e.g. it found 70 BPM but the song feels like 140)"""
    bl_idname = "svk.beat_tempo"
    bl_label = "Tempo x2 / ½"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(items=[("DOUBLE", "x2", "Add a beat between every pair"),
                              ("HALF", "½", "Keep every other beat")], default="DOUBLE")

    def execute(self, context):
        sc = context.scene
        beats = beat_frames(sc)
        if len(beats) < 2:
            self.report({"ERROR"}, "No beat markers")
            return {"CANCELLED"}
        if self.mode == "DOUBLE":
            new = []
            for a, b in zip(beats, beats[1:]):
                new += [a, round((a + b) / 2)]
            new.append(beats[-1])
            sc.svk_bpm *= 2
        else:
            new = beats[::2]
            sc.svk_bpm /= 2
        for m in [m for m in sc.timeline_markers if m.name.startswith(MARKER_PREFIX)]:
            sc.timeline_markers.remove(m)
        for i, f in enumerate(new):
            sc.timeline_markers.new(f"{MARKER_PREFIX}{i + 1:03d}", frame=f)
        return {"FINISHED"}


classes = (SVK_OT_beat_detect, SVK_OT_beat_grid, SVK_OT_beat_key, SVK_OT_beat_cuts, SVK_OT_beat_tempo)
