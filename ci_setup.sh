#!/bin/bash
# Подготовка машины GitHub к сборке ролика.
set -e
pip install -q numpy pillow requests
command -v ffmpeg >/dev/null || (sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg)
gcc -O2 -o phys phys.c -lm 2>/dev/null
