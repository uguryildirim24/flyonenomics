"""Encode a finished PNG frame sequence to H.264 with Blender's own FFmpeg.

    blender -b --factory-startup -P scripts/blender/encode.py -- job.json

Job: {"frames": dir, "fps": 60, "outputs": [{"path": "x.mp4", "percent": 100, "crf": 16}]}.
Frames are already composed and labelled; this only packs them.
"""
import json
from pathlib import Path
import sys

import bpy

job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text())
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
frames = sorted(Path(job["frames"]).glob("*.png"))
strip = scene.sequence_editor_create().strips.new_image("frames", str(frames[0]), 1, 1)
for frame in frames[1:]:
    strip.elements.append(frame.name)
width, height = bpy.data.images.load(str(frames[0])).size
scene.frame_start, scene.frame_end = 1, len(frames)
scene.render.fps, scene.render.fps_base = job["fps"], 1
scene.render.resolution_x, scene.render.resolution_y = width, height
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
settings = scene.render.image_settings
settings.media_type = "VIDEO"
settings.file_format = "FFMPEG"
settings.color_mode = "RGB"
ffmpeg = scene.render.ffmpeg
ffmpeg.format, ffmpeg.codec = "MPEG4", "H264"
ffmpeg.ffmpeg_preset = "BEST"
ffmpeg.gopsize = job["fps"]
ffmpeg.audio_codec = "NONE"
for out in job["outputs"]:
    ffmpeg.constant_rate_factor = "CUSTOM"
    ffmpeg.custom_constant_rate_factor = out["crf"]
    scene.render.resolution_percentage = out["percent"]
    path = Path(out["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.use_file_extension = False
    scene.render.filepath = str(path)
    bpy.ops.render.render(animation=True)
    print(f"wrote {path}", flush=True)
