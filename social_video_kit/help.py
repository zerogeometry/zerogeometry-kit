"""In-app help: '?' popups per section, the Quick Start list and the bundled guide page."""
import os
import bpy
from bpy.props import StringProperty

VERSION = "1.1.0"
GUIDE = os.path.join(os.path.dirname(__file__), "assets", "guide.html")

# short lines: Blender labels don't wrap, so keep every line sidebar-width
HELP = {
    "QUICKSTART": ("Quick Start", [
        "1  Build your shot in 16:9 as usual.",
        "2  Click 9:16. A vertical copy of the",
        "    scene is made; your original is safe.",
        "3  Pick your product as the Subject,",
        "    then Auto-Follow keeps it in frame.",
        "4  All Platforms shows where TikTok,",
        "    Reels and Shorts buttons cover video.",
        "5  Render All Formats exports every",
        "    version as MP4 to your Export Folder.",
    ]),
    "REFRAME": ("Vertical Reframe", [
        "9:16 / 4:5 / 1:1 duplicate the scene and",
        "re-fit every camera lens (animated zooms",
        "and beat-cut cameras included).",
        "Switch versions with the buttons on top.",
        "",
        "Auto-Follow keys lens shift + zoom on",
        "every frame so the subject stays inside",
        "the frame (or the platform safe area).",
        "Fill frame also zooms IN on small subjects.",
        "X restores the original lens.",
    ]),
    "GUIDES": ("Camera Guides", [
        "Drawn in camera view only, never rendered.",
        "  Badge: the frame format and size.",
        "  Lime box: the safe area (All Platforms,",
        "  TikTok, Reels or Shorts). Keep text",
        "  and product inside it.",
        "  Lime dot: pulses on every beat marker.",
        "Use the eye button to look through the camera.",
    ]),
    "BEAT": ("Beat Sync", [
        "Detect Beats: pick an mp3/wav. Adds a",
        "marker on every beat + the sound strip.",
        "Beat Grid: markers from a BPM you know.",
        "Tempo ½ / x2 if it found half/double time.",
        "",
        "Select objects, then Squash / Hop / Light /",
        "Glow keys a pulse on every beat. Tweak it",
        "in the redo panel (bottom-left corner).",
        "Select 2+ cameras > Camera Cuts on Beats.",
    ]),
    "LOOP": ("Loop Doctor", [
        "Set the frame range to one loop first.",
        "Check Loop lists curves that don't end",
        "where they start, and video textures",
        "that will freeze.",
        "Fix Loop: Close (key the start value one",
        "frame after the end), Cycles, or both.",
        "Works on the selection, or everything",
        "when nothing is selected.",
    ]),
    "WEDGE": ("Wedge Batch", [
        "Right-click any number field >",
        "Copy Full Data Path, then Wedge Render",
        "(the path is pasted for you).",
        "Choose From / To / Steps: one still per",
        "value + a labelled contact sheet in",
        "your Export Folder > Wedges.",
    ]),
}


class SVK_OT_help(bpy.types.Operator):
    """How this tool works"""
    bl_idname = "svk.help"
    bl_label = "Social Video Kit Help"

    topic: StringProperty(default="QUICKSTART")

    @classmethod
    def description(cls, context, props):
        return HELP.get(props.topic, HELP["QUICKSTART"])[0] + ": how it works"

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=340)

    def draw(self, context):
        title, lines = HELP.get(self.topic, HELP["QUICKSTART"])
        l = self.layout
        l.label(text=title.upper(), icon="QUESTION")
        col = l.column(align=True)
        for line in lines:
            col.label(text=line)
        l.operator("svk.open_guide", text="Full Guide", icon="HELP")


class SVK_OT_open_guide(bpy.types.Operator):
    """Open the Social Video Kit guide (works offline, it ships with the add-on)"""
    bl_idname = "svk.open_guide"
    bl_label = "Open Guide"

    def execute(self, context):
        bpy.ops.wm.url_open(url="file:///" + GUIDE.replace(os.sep, "/"))
        return {"FINISHED"}


def draw_quickstart(layout):
    col = layout.column(align=True)
    for line in HELP["QUICKSTART"][1]:
        col.label(text=line)


classes = (SVK_OT_help, SVK_OT_open_guide)
