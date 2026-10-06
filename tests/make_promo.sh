#!/bin/bash
# Rebuild + reinstall the extension, rebuild the original demo scene, run the tests,
# then capture every promo screenshot from the demo (no client work, no third-party music).
cd "$(dirname "$0")/.."
B="${BLENDER:-/c/Program Files/Blender Foundation/Blender 5.2/blender.exe}"   # override with BLENDER=...
P="$(pwd)/promo"
D="$(pwd)/demo/svk_demo.blend"
"$B" -b --factory-startup -P tests/test_headless.py 2>&1 | grep -E "FAIL|RESULT|Traceback"
"$B" -b --factory-startup -P tests/test_more.py 2>&1 | grep -E "FAIL|RESULT|Traceback"
"$B" -b --factory-startup -P demo/build_demo.py 2>&1 | grep -E "DEMO_BUILT|Error"
"$B" --command extension build --source-dir social_video_kit --output-dir dist 2>&1 | tail -1
"$B" --command extension install-file -r user_default -e dist/zerogeometry_kit-1.1.0.zip 2>&1 | tail -1
shot() {
    timeout 180 "$B" --factory-startup "$D" -P tests/gui_promo.py -- "$1" "$P/$2" 2>&1 | grep -E "PROMO|Error|Traceback" | head -4
}
shot before  01_before_16x9.png
shot reframe 02_reframe_9x16_safe_area.png
shot beat    03_beat_sync.png
shot loop    04_loop_doctor.png
shot help    05_help_quickstart.png
# wedge contact sheet from the demo (key light 2 -> 20 W)
"$B" -b "$D" -P tests/promo_wedge.py 2>&1 | grep -E "PROMO|Error|Traceback"
echo PROMO_DONE
