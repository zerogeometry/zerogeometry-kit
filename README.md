# ZeroGeometry Kit

Social-video tools for Blender 4.2+ (tested on 5.2). Make one great 16:9 animation, then ship it everywhere.
By [ZeroGeometry](https://zerogeometry.com).

**Panel:** 3D Viewport → Sidebar (`N`) → **ZeroGeometry**. Every section has a **?** button, and a full offline guide ships with the add-on (**Guide** button).

## Vertical Reframe
- **9:16 / 4:5 / 1:1:** each click makes a real reframed copy of your scene with every camera lens re-fitted, including animated zooms and beat-cut cameras. It's always built from your original, and clicking a format that already exists just switches to it. **All Three** makes every format at once.
- **Version switcher:** the 16:9 · 9:16 · 4:5 · 1:1 buttons at the top of the panel jump between versions.
- **Auto-Follow Subject:** pick your product (an object or a collection) and it keys lens shift and zoom on every frame so the product stays inside the frame. **Fill frame** also zooms in on small subjects. **X** restores the original lens, and re-running never stacks.
- **TikTok / Reels / Shorts:** shows the real, asymmetric areas the app UI covers. Auto-Follow then centres the product in the safe area.
- **Render All Formats:** exports the original and every version as H.264 MP4 (with the scene's audio) named `Scene_9x16.mp4` and so on. Your own render settings are restored afterwards.

## Camera Guides
Drawn in camera view only, never rendered: a ZERO **GEOMETRY** format badge, the platform safe area, and a lime dot that pulses on every beat marker. The eye button jumps to camera view.

## Beat Sync
- **Detect Beats** (mp3 / wav / flac / ogg / m4a): tempo and beat phase, a marker on every beat, and the track added as a sound strip. Re-running replaces it rather than stacking.
- **BPM Grid**, plus **Tempo ½ / ×2**.
- **Squash / Hop / Light / Glow:** keys a pulse on the selected objects every N beats (redo panel: amount, decay, stagger).
- **Camera Cuts on Beats:** select two or more cameras and it cuts between them on the beat.

## Loop Doctor
**Check** lists every curve that doesn't end where it starts, and every video texture that will freeze. **Fix** closes them (or adds Cycles). A full 360° spin counts as closed. Works on the selection, or on everything when nothing is selected.

## Wedge Batch
Houdini-style wedging. Copy any number field's data path, click **Wedge Render** (the path is pasted for you), and get one still per value plus a branded, labelled contact sheet.

## Where files go
Everything is saved to the **Export Folder** shown in the panel. The default is `ZeroGeometry Exports/` next to your .blend; if the file hasn't been saved yet, it's `Videos/ZeroGeometry Exports`. Inside: `Renders/` and `Wedges/<property>_<time>/`. Use **Open** to view it, or the folder button to choose another location.

## Install
In Blender: **Edit → Preferences → Get Extensions → ⌄ → Install from Disk**, then pick `zerogeometry_kit-1.0.0.zip`. Try it on `demo/zgk_demo.blend`, an original scene with a royalty-free generated beat.

## Develop / test
```
blender -b --factory-startup -P tests/test_headless.py      # 12 checks
blender -b --factory-startup -P tests/test_more.py -- song.mp3   # 16 checks
blender demo/zgk_demo.blend -P tests/gui_handtest.py -- out_dir  # 25 checks, real UI
blender --command extension build --source-dir zerogeometry_kit --output-dir dist
```

GPL-3.0-or-later. Fonts: Poppins and IBM Plex Mono (SIL Open Font License, included).
