"""Blender 5 headless renderer: the playback's bodies side by side, labels from the poses file.

/opt/homebrew/bin/blender -b -t 6 --python scripts/courtship_body/render.py -- \
  --poses /path/to/poses.npz --out figures/3d/courtship-body/courtship-4k.mp4 [--preview --frame N]
"""
import argparse
from pathlib import Path
import sys
import subprocess
import tempfile

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

p = argparse.ArgumentParser()
p.add_argument('--poses', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--preview', action='store_true', help='one labelled still at --frame, no video')
p.add_argument('--frame', type=int, default=1)
a = p.parse_args(sys.argv[sys.argv.index('--')+1:])

FFMPEG = next((Path(__file__).resolve().parent /
               '.venv/lib/python3.12/site-packages/imageio_ffmpeg/binaries').glob('ffmpeg-*'))
FONT = '/Library/Fonts/SF-Pro-Display-Light.otf'
YAW = 0.55  # all bodies turned the same way, so they are seen from the same angle

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.eevee.taa_render_samples = 96
scene.eevee.use_raytracing = True
scene.eevee.use_shadows = True
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = .5
scene.render.resolution_x = 3840
scene.render.resolution_y = 2160
scene.render.resolution_percentage = 50 if a.preview else 100
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
world = scene.world
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (.006, .008, .012, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.


def material(name, color, metallic=0., roughness=.5, alpha=1., coat=0., sss=0.):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Alpha'].default_value = alpha
    bsdf.inputs['Coat Weight'].default_value = coat
    bsdf.inputs['Subsurface Weight'].default_value = sss
    bsdf.inputs['Subsurface Radius'].default_value = (.08, .04, .02)
    if alpha < 1:
        mat.surface_render_method = 'BLENDED'
        mat.use_transparency_overlap = True
    return mat


body = material('amber cuticle', (.30, .15, .045), .0, .40, coat=.2, sss=.15)
legs = material('dark cuticle', (.10, .055, .03), .0, .42, coat=.2)
wings = material('wing membrane', (.72, .80, .86), .0, .12, alpha=.16, coat=.6)
eyes = material('compound eyes', (.36, .035, .03), .0, .3, coat=.8)
floor = material('stage', (.020, .022, .026), .0, .62)

with np.load(a.poses, allow_pickle=False) as data:
    fps, on_seconds = int(data['fps']), float(data['on_seconds'])
    # (body, horizontal offset in mm, label while input is on, label after it stops)
    FLIES = tuple(zip(data['bodies'].tolist(), data['offsets'].tolist(),
                      data['labels_on'].tolist(), data['labels_off'].tolist()))
    label_size = float(data['label_size'])
    names = data['names'].tolist()
    mesh_ids = data['mesh_ids']
    meshes = {}
    for i, mesh_id in enumerate(int(x) for x in mesh_ids):
        if mesh_id >= 0 and mesh_id not in meshes:
            mesh = bpy.data.meshes.new(f'mesh_{mesh_id}')
            mesh.from_pydata(data[f'vert_{mesh_id}'].tolist(), [], data[f'face_{mesh_id}'].tolist())
            mesh.shade_smooth()
            mesh.update()
            meshes[mesh_id] = mesh
    n_frames = data[f'{FLIES[0][0]}_positions'].shape[0]
    if a.preview and not 1 <= a.frame <= n_frames:
        raise ValueError('preview frame is outside trajectory')
    frame_ids = [a.frame - 1] if a.preview else range(n_frames)
    lowest = np.inf
    for fly, offset, _, _ in FLIES:
        pos, rot = data[f'{fly}_positions'], data[f'{fly}_rotations']
        rig = bpy.data.objects.new(fly, None)
        bpy.context.collection.objects.link(rig)
        rig.location = (0, offset, 0)
        rig.rotation_euler = (0, 0, YAW)
        for i, name in enumerate(names):
            mesh_id = int(mesh_ids[i])
            if mesh_id < 0:
                continue
            obj = bpy.data.objects.new(f'{fly} {name}', meshes[mesh_id])
            bpy.context.collection.objects.link(obj)
            obj.parent = rig
            obj.rotation_mode = 'QUATERNION'
            tag = name.lower()
            # Both bodies share mesh data, so materials attach to objects.
            if not obj.data.materials:
                obj.data.materials.append(None)
            obj.material_slots[0].link = 'OBJECT'
            obj.material_slots[0].material = (
                wings if 'wing' in tag else eyes if 'eye' in tag else
                legs if any(s in tag for s in ('coxa', 'femur', 'tibia', 'tarsus')) else body)
            if 'tarsus' in tag:
                lowest = min(lowest, float((data[f'vert_{mesh_id}'] @ rot[0, i].T + pos[0, i])[:, 2].min()))
            # Compiled MuJoCo mesh vertices are local to geom; use measured geom poses.
            moving = bool(np.ptp(pos[:, i], axis=0).max() > 1e-6 or np.ptp(rot[:, i], axis=0).max() > 1e-6)
            for f in (frame_ids if moving else [frame_ids[0]]):
                obj.location = Vector(pos[f, i].tolist())
                obj.rotation_quaternion = Matrix(rot[f, i].tolist()).to_quaternion()
                if moving:
                    obj.keyframe_insert(data_path='location', frame=f+1)
                    obj.keyframe_insert(data_path='rotation_quaternion', frame=f+1)

bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, lowest))
bpy.context.object.name = 'stage'
bpy.context.object.data.materials.append(floor)


def point(obj, at):
    obj.rotation_euler = (Vector(at) - obj.location).to_track_quat('-Z', 'Y').to_euler()


# Three-quarter front view from above, all bodies at the same depth. A wider
# row moves the camera and lights back along their lines to keep the framing.
TARGET = Vector((0, 0, .8))
spread = max(1., (np.ptp([offset for _, offset, _, _ in FLIES]) + 6.4) / 12.8)
bpy.ops.object.camera_add(location=TARGET + (Vector((27, 0, 21.5)) - TARGET) * spread)
cam = bpy.context.object
point(cam, TARGET)
cam.data.lens = 100
cam.data.sensor_width = 36
cam.data.dof.use_dof = True
cam.data.dof.focus_distance = (cam.location - TARGET).length
cam.data.dof.aperture_fstop = .12  # scene units are mm: a macro-lens depth of field
scene.camera = cam
for xyz, power, size, color in [((9, 0, 18), 9000, 12, (1, .86, .70)),     # warm key
                                 ((-16, 0, 9), 7000, 10, (.55, .70, 1)),   # cool rim
                                 ((14, -14, 5), 1800, 10, (.80, .85, 1))]:  # low fill
    bpy.ops.object.light_add(type='AREA', location=Vector(xyz) * spread)
    light = bpy.context.object
    light.data.energy = power * spread ** 2
    light.data.shape = 'DISK'
    light.data.size = size * spread
    light.data.color = color
    point(light, (0, 0, .3))

scene.frame_start = 1
scene.frame_end = n_frames
scene.render.fps = fps


def finish(src, dst, rate, t='t'):
    """Plain labels and a soft vignette, added in post so type stays crisp.

    A body whose input stops at on_seconds cross-fades its label there. A
    newline in a label starts a second centred line."""
    w = scene.render.resolution_x * scene.render.resolution_percentage // 100
    size = round(w * label_size)
    top = .5 + .365 / spread  # labels stay just under the bodies as the camera backs off
    parts = ['vignette=angle=PI/5']
    fade_out = f'if(lt({t},{on_seconds}),1,max(0,1-({t}-{on_seconds})/.4))'
    centres = [world_to_camera_view(scene, cam, Vector((0, offset, 0))).x for _, offset, _, _ in FLIES]
    for (_, _, before, after), centre in zip(FLIES, centres):
        cx = f'w*{centre:.4f}'
        texts = [(before, '1')] if before == after else [(before, fade_out), (after, f'1-{fade_out}')]
        for text, alpha in texts:
            for row, line in enumerate(text.split('\n')):
                parts.append(f"drawtext=fontfile='{FONT}':text='{line}':fontsize={size}:"
                             f"fontcolor=0xE6E9EE:x={cx}-tw/2:y=h*{top:.4f}+{round(row * size * 1.3)}:"
                             f"alpha='{alpha}'")
    vf = ','.join(parts)
    cmd = [str(FFMPEG), '-hide_banner', '-loglevel', 'error', '-y']
    if t != 't':
        subprocess.run(cmd + ['-i', str(src), '-vf', vf, str(dst)], check=True)
        return
    subprocess.run(cmd + ['-framerate', str(rate), '-i', str(src), '-vf', vf,
                          '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p',
                          '-movflags', '+faststart', str(dst)], check=True)


a.out.parent.mkdir(parents=True, exist_ok=True)
scene.render.image_settings.file_format = 'PNG'
with tempfile.TemporaryDirectory(prefix='courtship-frames-') as temp:
    if a.preview:
        scene.frame_set(a.frame)
        scene.render.filepath = str(Path(temp) / 'still.png')
        bpy.ops.render.render(write_still=True)
        finish(Path(temp) / 'still.png', a.out, fps, t=f'{(a.frame - 1) / fps:.4f}')
        print('Preview:', a.out)
    else:
        # Blender 5.2's headless image_settings enum excludes FFMPEG despite a
        # compiled-in encoder. Render 4K PNG frames then encode with the pinned
        # body environment's imageio-ffmpeg binary. Temp frames are not figures.
        scene.render.filepath = str(Path(temp) / 'frame_')
        bpy.ops.render.render(animation=True)
        finish(Path(temp) / 'frame_%04d.png', a.out, fps)
        second = a.out.with_name(a.out.stem.replace('4k', '1080p60') + a.out.suffix)
        subprocess.run([str(FFMPEG), '-hide_banner', '-loglevel', 'error', '-y', '-i', str(a.out),
                        '-vf', 'scale=1920:1080:flags=lanczos', '-r', '60',
                        '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p',
                        '-movflags', '+faststart', str(second)], check=True)
        print('Master:', a.out, '1080p60:', second)
