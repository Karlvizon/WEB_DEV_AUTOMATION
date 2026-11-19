#!/bin/sh
# Full-page screenshots for the device matrix: sh tools/qa/matrix.sh
cd "$(dirname "$0")/../.."
for v in 3840x2160 3440x1440 2560x1440 1920x1080 1600x900 1440x900 1366x768 1280x720 1024x768 768x1024 430x932 390x844 375x812 320x568; do
  w=${v%x*}; h=${v#*x}; node tools/qa/fullshot.js $w qa/shots/$v.png $h | tail -1
done
