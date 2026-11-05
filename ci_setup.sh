#!/bin/bash
# Подготовка машины GitHub к сборке ролика.
set -e
pip install -q numpy pillow requests
command -v ffmpeg >/dev/null || (sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg)
python make_outline.py || true
