"""In-app tutorial text: a Quick Start section and per-tool help popups (the '?' buttons)."""
import bpy
from bpy.props import StringProperty

DOCS_URL = "https://github.com/zerogeometry/zerogeometry-kit#readme"

# short lines: Blender labels don't wrap, so keep every line sidebar-width
HELP = {
    "QUICKSTART": ("Quick Start", [
        "1  Build your shot in 16:9 as usual.",
        "2  Reframe > 9:16 makes a vertical copy",
        "    of the scene (your original is safe).",
        "3  Pick your product as the Subject,",
        "    then Auto-Follow keeps it in frame.",
        "4  TikTok / Reels / Shorts shows where",
        "    the app's buttons cover the video.",
        "5  Render All Formats exports every",
        "    version as MP4 into //zgk_renders.",
        "",
        "Tip: look through the camera (Numpad 0)",
        "to see the ZeroGeometry overlay.",
    ]),
    "REFRAME": ("Vertical Reframe", [
        "9:16 / 4:5 / 1:1 duplicate the scene and",
        "re-fit every camera lens (animated zooms",
        "and beat-cut cameras included).",
        "Zoom In / Out nudges all lenses 10%.",
        "",
        "Auto-Follow: set Object (or Collection).",
        "It keys lens shift + zoom per frame so the",
        "subject stays inside the frame, or inside",
        "the platform safe box when one is active.",
        "Fill frame: also zooms IN so a small",
        "subject fills the safe box.",
        "X = Clear Follow, back to the original lens.",
    ]),
    "BEAT": ("Beat Sync", [
        "Detect Beats: pick an mp3/wav. Adds a",
        "marker on every beat + the sound strip.",
        "Beat Grid: markers from a BPM you know.",
        "Tempo ½ / x2 if it found half/double time.",
        "",
        "Select objects, then Squash / Hop / Light /",
        "Glow to key a pulse on the beat (redo panel:",
        "every N beats, amount, decay, stagger).",
        "Select cameras > Camera Cuts on Beats.",
    ]),
    "LOOP": ("Loop Doctor", [
        "Set the frame range to one loop first.",
        "Check Loop lists curves that don't end",
        "where they start, and video textures that",
        "will freeze (frame-offset bug).",
        "Fix Loop: Close (key the start value one",
        "frame after the end), Cycles, or both.",
    ]),
    "WEDGE": ("Wedge Batch", [
        "Right-click any number field >",
        "Copy Full Data Path, then Wedge Render",
        "and paste it. Choose From / To / Steps.",
        "Renders one still per value and saves a",
        "labelled contact sheet in //zgk_wedge.",
    ]),
}


class ZGK_OT_help(bpy.types.Operator):
    """How this tool works"""
    bl_idname = "zgk.help"
    bl_label = "ZeroGeometry Help"

    topic: StringProperty(default="QUICKSTART")

    @classmethod
    def description(cls, context, props):
        return HELP.get(props.topic, HELP["QUICKSTART"])[0] + ": how it works"

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=330)

    def draw(self, context):
        title, lines = HELP.get(self.topic, HELP["QUICKSTART"])
        l = self.layout
        l.label(text=title.upper(), icon="QUESTION")
        col = l.column(align=True)
        for line in lines:
            col.label(text=line)
        l.operator("wm.url_open", text="Full guide", icon="URL").url = DOCS_URL


def draw_quickstart(layout):
    col = layout.column(align=True)
    for line in HELP["QUICKSTART"][1]:
        col.label(text=line)
    layout.operator("wm.url_open", text="Full guide", icon="URL").url = DOCS_URL


classes = (ZGK_OT_help,)
