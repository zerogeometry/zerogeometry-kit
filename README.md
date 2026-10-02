# ZeroGeometry Kit

Social-video tools for Blender 4.2+ (tested on 5.2). Make one great 16:9 animation, then ship it everywhere.

**Panel:** 3D Viewport → Sidebar (`N`) → **ZeroGeometry**

## Vertical Reframe (the flagship)
Turn a finished 16:9 scene into real **9:16 / 4:5 / 1:1** versions. The camera is reframed, not the video cropped.
- **Reframe Scene:** makes a copy of the scene in the new format and rescales every lens, including animated zooms and every camera used in beat cuts.
- **Make All Social Formats:** creates 9:16, 4:5 and 1:1 copies in one click.
- **Auto-Follow Subject:** pick your product (an object or a whole collection). It keys the camera's lens shift, and optionally its zoom, on every frame so the subject stays centred and fully inside the tall frame, with smoothing. Like Auto Reframe, but it knows exactly where your 3D subject is, so it never guesses.
- **Social Safe Zones:** a ZeroGeometry camera overlay showing the real, asymmetric areas that TikTok / Reels / Shorts cover (right-hand buttons, caption bar), with a lime "safe" box. Auto-Follow can aim for the centre of that box.
- **Clear Follow:** removes the follow keys and restores every camera's original (even animated) lens. Re-running Auto-Follow never stacks zoom.
- **Render All Formats:** renders the master scene and every reframed copy to H.264 MP4 (with the music if the scene has a sound strip). It handles odd pixel sizes, such as 4:5 at preview percentages, automatically.

## The ZeroGeometry overlay
In camera view: the platform safe zones, a ZERO **GEOMETRY** format badge, and a lime dot that pulses on every beat marker. Toggle it with **Overlay** in the panel header.

## Beat Sync
- **Detect Beats:** analyses a music file (tempo plus beat phase), adds a marker on every beat and adds the sound strip.
- **Beat Grid:** markers from a known BPM.
- **Tempo ½ / x2:** halve or double the detected tempo when a track is read in half-time (e.g. 70 vs 140 BPM drill).
- **Key Pulses to Beats:** squash bounce, hop, light flash or emission flash on the selected objects, every N beats, with stagger.
- **Camera Cuts on Beats:** select cameras and it cuts between them every N beats (camera-bound markers, so there are no motion-blur smears across cuts).

## Loop Doctor
- **Check Loop:** lists every curve that doesn't return to its start value, and every movie texture that will freeze. This includes the classic *frame-offset* bug, where Blender applies the offset after wrapping, so late frames hold on the last frame.
- **Fix Loop:** closes the curves, adds a Cycles modifier, or both, and repairs movie textures.
- **Set Loop Range:** sets the scene length to a whole number of loops.

## Wedge Batch
Houdini-style wedging. Sweep any property (right-click → *Copy Full Data Path*) across N values, render a still for each, and get one **contact sheet** plus a values list.

See **TUTORIAL.md** for a step-by-step guide. Promo screenshots are in `promo/`; the demo scene is in `demo/`.

## Install
Download `zerogeometry_kit-<version>.zip`, then in Blender go to **Edit → Preferences → Get Extensions → ⌄ → Install from Disk**.

## Develop / test
```
blender -b --factory-startup -P tests/test_headless.py
blender --command extension build --source-dir zerogeometry_kit --output-dir dist
```

GPL-3.0-or-later.
