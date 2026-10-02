# ZeroGeometry Kit: Tutorial

Open the panel: **3D Viewport → press N → ZeroGeometry tab**. Every section has a **?** button with a short how-to, and the **Quick Start** section is at the bottom. Try it on `demo/zgk_demo.blend` (original scene, royalty-free beat included).

## 1. Turn a 16:9 shot into a vertical one (2 minutes)
1. Finish your animation in 16:9 as usual.
2. Click **9:16**. A copy of the scene called `<name>_9x16` is created; your original is never touched.
3. Set **Object** (or a whole **Collection**) to your product.
4. Click **TikTok** (or Reels / Shorts) to see where the app's buttons will cover your video.
5. Tick **Fill frame**, then click **Auto-Follow Subject**. Every frame is reframed so the product stays inside the lime safe box.
6. Not happy? Click **X** to restore the original lens, adjust, and run it again. It never stacks.
7. **Render All Formats** writes MP4s of the original and every reframed copy to `//zgk_renders`.

Want 4:5 and 1:1 too? **Make All Social Formats** creates all three copies in one click.

## 2. Cut to the music
1. **Beat Sync → Detect Beats**, then pick an mp3 or wav. You get a marker on every beat and the sound strip.
   If the tempo looks half or double, use **Tempo ½ / x2**.
2. Select objects, then **Squash / Hop / Light / Glow** keys a pulse on every beat. Use the redo panel (bottom-left) to set every N beats, amount, decay and stagger.
3. Select two or more cameras, then **Camera Cuts on Beats**.
4. In camera view, the lime dot pulses on every beat.

## 3. Make a perfect loop
1. Set the frame range to one loop.
2. **Check Loop** lists every curve that doesn't end where it starts, and any video texture that will freeze.
3. **Fix Loop** closes the curves (or adds Cycles). A full 360° spin counts as already closed.

## 4. Compare variations (wedge)
1. Right-click any number field, then **Copy Full Data Path**.
2. **Wedge Render**: paste it, set From / To / Steps.
3. You get a labelled ZeroGeometry contact sheet in `//zgk_wedge`.

## Tips
- The overlay only shows in **camera view** (Numpad 0). Toggle it with **Overlay** in the panel header.
- Auto-Follow works on every camera you cut to, including beat cuts.
- Small preview renders at odd sizes are adjusted automatically for MP4.
