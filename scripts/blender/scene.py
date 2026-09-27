"""Blender side of the tour figures. tour.py writes the job and runs:

    blender -b --factory-startup -P scripts/blender/scene.py -- job.json

The job names the scene and value tables, the camera views and the render tasks.
Only numpy and bpy are used here; every table join happens in tour.py.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
import numpy as np
from mathutils import Matrix, Quaternion, Vector

JOB = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text())
SCENE = np.load(JOB["scene"])
META = json.loads(bytes(SCENE["meta"]))
VALUES = np.load(JOB["values"])
VMETA = json.loads(bytes(VALUES["meta"]))
PATH_KEYS = [k for k, _ in META["path"]]

# The look, shared with tour.py and the browser viewer. Emission only: nothing is
# lit, every surface gives off its own light.
LOOK = json.loads((Path(__file__).with_name("look.json")).read_text())
LOOK.update(JOB.get("look", {}))


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear(hex_colour: str) -> np.ndarray:
    return srgb_to_linear([int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)])


def ramp(stops, t: np.ndarray) -> np.ndarray:
    """Palette stops are sRGB; interpolate there, convert to linear for emission."""
    pos = np.array([s[0] for s in stops])
    srgb = np.array([[int(s[1][i:i + 2], 16) / 255 for i in (1, 3, 5)] for s in stops])
    return srgb_to_linear(np.stack([np.interp(t, pos, srgb[:, j]) for j in range(3)], 1))


def scaled(v: np.ndarray) -> np.ndarray:
    """Signed log scale, fixed across all conditions: -1 … 0 … +1."""
    cap, knee = VMETA["cap"], VMETA["knee"]
    return np.sign(v) * np.minimum(np.log1p(np.abs(v) / knee) / math.log1p(cap / knee), 1.0)


def look(v: np.ndarray):
    """Per-neuron colour, glow, size and opacity. Unchanged neurons stay dim slate;
    increases run hot (amber to gold), decreases cold (deep to pale blue)."""
    m = scaled(v)
    a = np.abs(m)
    colour = np.where((m >= 0)[:, None], ramp(LOOK["palette"]["up"], a), ramp(LOOK["palette"]["down"], a))
    gain = np.where(m >= 0, 1.0, LOOK["down_gain"])
    glow = LOOK["neutral_glow"] + LOOK["change_glow"] * gain * a ** 0.85
    alpha = LOOK["neutral_alpha"] + (LOOK["change_alpha"] - LOOK["neutral_alpha"]) * np.minimum(a * 3, 1)
    return colour, glow, 1.0 + 1.1 * a, alpha


# ---------------------------------------------------------------- scene

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "METAL"
    c = scene.cycles
    c.device = "GPU"
    c.samples = LOOK["samples"]
    c.use_adaptive_sampling = True
    c.use_denoising = False
    c.max_bounces = 0
    c.transparent_max_bounces = 96
    c.seed = 0
    scene.render.filter_size = 1.2
    scene.render.use_persistent_data = True  # keep unchanged geometry between frames
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (*linear(LOOK["background"]), 1)
    scene.world = world
    return scene


def math_node(nt, op, a, b):
    node = nt.nodes.new("ShaderNodeMath")
    node.operation = op
    for socket, value in ((node.inputs[0], a), (node.inputs[1], b)):
        if isinstance(value, (int, float)):
            socket.default_value = value
        else:
            nt.links.new(value, socket)
    return node.outputs[0]


def emissive(name: str, *, rim: str | None = None, rim_power=3.0, rim_strength=0.5, fill=0.0,
             attribute=False, soft=False):
    """Anatomy shells add a fresnel rim of light. Attribute-driven dots and tubes
    take colour, glow and opacity from the geometry; dense regions keep their
    colour instead of summing to white."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    transparent = nt.nodes.new("ShaderNodeBsdfTransparent")
    emission = nt.nodes.new("ShaderNodeEmission")
    if attribute:
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(transparent.outputs[0], mix.inputs[1])
        nt.links.new(emission.outputs[0], mix.inputs[2])
        attrs = {}
        for key in ("col", "glow", "alpha"):
            node = nt.nodes.new("ShaderNodeAttribute")
            node.attribute_type = "GEOMETRY"
            node.attribute_name = key
            attrs[key] = node
        nt.links.new(attrs["alpha"].outputs["Fac"], mix.inputs[0])
        nt.links.new(attrs["col"].outputs["Color"], emission.inputs["Color"])
        strength = attrs["glow"].outputs["Fac"]
    else:
        mix = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(transparent.outputs[0], mix.inputs[0])
        nt.links.new(emission.outputs[0], mix.inputs[1])
        emission.inputs["Color"].default_value = (*linear(rim), 1)
        facing = nt.nodes.new("ShaderNodeLayerWeight")
        facing.inputs["Blend"].default_value = 0.5
        edge = math_node(nt, "POWER", facing.outputs["Facing"], rim_power)
        node = nt.nodes.new("ShaderNodeMath")
        node.operation = "MULTIPLY_ADD"
        nt.links.new(edge, node.inputs[0])
        node.inputs[1].default_value = rim_strength
        node.inputs[2].default_value = fill
        strength = node.outputs[0]
    if soft:
        # Round falloff across each dot so it reads as a soft point of light.
        facing = nt.nodes.new("ShaderNodeLayerWeight")
        facing.inputs["Blend"].default_value = 0.5
        centre = math_node(nt, "POWER", math_node(nt, "SUBTRACT", 1.0, facing.outputs["Facing"]), 1.6)
        strength = math_node(nt, "MULTIPLY", strength, centre)
    nt.links.new(strength, emission.inputs["Strength"])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return mat


def mesh_object(name, verts, faces=None, edges=None, parent=None):
    mesh = bpy.data.meshes.new(name)
    mesh.vertices.add(len(verts))
    mesh.vertices.foreach_set("co", np.ascontiguousarray(verts, np.float32).ravel())
    if faces is not None:
        faces = np.ascontiguousarray(faces, np.int32)
        mesh.loops.add(faces.size)
        mesh.polygons.add(len(faces))
        mesh.loops.foreach_set("vertex_index", faces.ravel())
        mesh.polygons.foreach_set("loop_start", np.arange(0, faces.size, 3, dtype=np.int32))
        mesh.polygons.foreach_set("use_smooth", np.ones(len(faces), bool))
    if edges is not None:
        mesh.edges.add(len(edges))
        mesh.edges.foreach_set("vertices", np.ascontiguousarray(edges, np.int32).ravel())
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    return obj


def geometry_nodes(obj, kind: str, material):
    ng = bpy.data.node_groups.new(f"{obj.name}-gn", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, link = ng.nodes, ng.links.new
    gin, gout = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    radius = n.new("GeometryNodeInputNamedAttribute")
    radius.data_type = "FLOAT"
    radius.inputs["Name"].default_value = "rad"
    if kind == "points":
        last = n.new("GeometryNodeMeshToPoints")
        link(gin.outputs[0], last.inputs["Mesh"])
        link(radius.outputs["Attribute"], last.inputs["Radius"])
    else:
        # Centerlines become thin round tubes; Cycles skips bare curve geometry here.
        curve = n.new("GeometryNodeMeshToCurve")
        link(gin.outputs[0], curve.inputs["Mesh"])
        profile = n.new("GeometryNodeCurvePrimitiveCircle")
        profile.inputs["Resolution"].default_value = 6
        profile.inputs["Radius"].default_value = 1.0
        last = n.new("GeometryNodeCurveToMesh")
        link(curve.outputs[0], last.inputs["Curve"])
        link(profile.outputs["Curve"], last.inputs["Profile Curve"])
        link(radius.outputs["Attribute"], last.inputs["Scale"])
    material_node = n.new("GeometryNodeSetMaterial")
    material_node.inputs["Material"].default_value = material
    link(last.outputs[0], material_node.inputs[0])
    link(material_node.outputs[0], gout.inputs[0])
    obj.modifiers.new("gn", "NODES").node_group = ng


def set_attributes(obj, colour, glow, radius, alpha):
    mesh = obj.data
    for name, kind in (("col", "FLOAT_COLOR"), ("glow", "FLOAT"), ("rad", "FLOAT"), ("alpha", "FLOAT")):
        if name not in mesh.attributes:
            mesh.attributes.new(name, kind, "POINT")
    rgba = np.concatenate([colour, np.ones((len(colour), 1))], 1).astype(np.float32)
    mesh.attributes["col"].data.foreach_set("color", rgba.ravel())
    for name, value in (("glow", glow), ("rad", radius), ("alpha", alpha)):
        mesh.attributes[name].data.foreach_set("value", np.broadcast_to(value, (len(colour),)).astype(np.float32))
    mesh.update()


VNC_PARTS = ("VNC", "CV", "LegNp", "ANm", "LTct", "IntTct")


class Brain:
    """Anatomy shells, one dot per sampled synapse site of every simulated neuron,
    and the courtship path's centerlines."""

    def __init__(self):
        self.root = bpy.data.objects.new("brain", None)
        bpy.context.scene.collection.objects.link(self.root)
        # Atlas frame is +y dorsal, +z anterior; Blender is Z-up. A +90° turn about
        # X puts dorsal at +Z and the front of the head toward -Y.
        self.root.rotation_euler = (math.pi / 2, 0, 0)
        shell = emissive("shell", rim=LOOK["shell"], rim_power=LOOK["shell_power"],
                         rim_strength=LOOK["shell_rim"], fill=LOOK["shell_fill"])
        neuropil = emissive("neuropil", rim=LOOK["neuropil"], rim_power=2.4, rim_strength=LOOK["neuropil_rim"])
        self.meshes = []
        for i, m in enumerate(META["meshes"]):
            # The optic-lobe compartments end in flat lamina slabs; the medulla,
            # lobula and lobula plate meshes carry that outline instead.
            if m["name"].startswith(("LA(", "Optic(")):
                continue
            obj = mesh_object(m["name"], SCENE[f"mesh{i}_v"], faces=SCENE[f"mesh{i}_f"], parent=self.root)
            outline = m["group"] == "shell" or m["name"].startswith(("ME(", "LO(", "LOP("))
            obj.data.materials.append(shell if outline else neuropil)
            self.meshes.append(obj)
        self.dust = mesh_object("dust", SCENE["dust_points"], parent=self.root)
        geometry_nodes(self.dust, "points", emissive("dust", attribute=True, soft=True))
        self.path = mesh_object("path", SCENE["skel_v"], edges=SCENE["skel_e"], parent=self.root)
        geometry_nodes(self.path, "tubes", emissive("path", attribute=True))
        position = {int(b): i for i, b in enumerate(VALUES["body_ids"])}
        self.path_neuron = np.array([position[int(b)] for b in SCENE["path_body"]])
        self.vertex_group = SCENE["path_group"][SCENE["skel_cell"]]
        self.vertex_neuron = self.path_neuron[SCENE["skel_cell"]]
        bpy.context.view_layer.update()

    def paint(self, v: np.ndarray):
        colour, glow, size, alpha = look(v)
        n = SCENE["dust_neuron"]
        set_attributes(self.dust, colour[n], glow[n], LOOK["dot_radius"] * size[n], alpha[n])

    def paint_path(self, v: np.ndarray | None):
        """Each path cell in its own rate-change colour; hidden when v is None."""
        self.path.hide_render = v is None
        if v is None:
            return
        colour, glow, size, _ = look(v[self.vertex_neuron])
        set_attributes(self.path, colour, LOOK["path_glow"] * glow, LOOK["path_radius"] * (1 + 0.6 * (size - 1)),
                       np.full(len(colour), LOOK["path_alpha"]))

    def flash_path(self, flashes: np.ndarray):
        """flashes[cell]: that cell's recent spikes (tour.spike_flashes). A resting
        cell is dim anatomy; each spike lights it up the warm ramp and fades."""
        self.path.hide_render = False
        b = 1 - np.exp(-LOOK["flash_gain"] * flashes[SCENE["skel_cell"]])
        _, dim_g, _, _ = look(np.zeros(1))
        rest = LOOK["path_alpha"] * 0.35
        glow = LOOK["path_glow"] * dim_g[0] * (1 - b) + LOOK["flash_glow"] * b
        set_attributes(self.path, ramp(LOOK["palette"]["up"], b), glow, LOOK["path_radius"] * (1 + 0.5 * b),
                       rest + (1 - rest) * b)

    def show_vnc(self, on: bool):
        for obj in self.meshes:
            if obj.name.startswith(VNC_PARTS):
                obj.hide_render = not on

    def anchors(self, cam, scene) -> dict:
        """Screen point (0..1, origin top-left) for each path group's label, and
        whether the label sits above (-1) or below (+1). pIP10 is marked where its
        axons run through the neck; the others at their median centerline point."""
        world = self.root.matrix_world
        result = {}
        for g, key in enumerate(PATH_KEYS):
            verts = SCENE["skel_v"][self.vertex_group == g]
            if key == "pIP10":
                verts = verts[(verts[:, 2] < -140) & (verts[:, 2] > -240)]
            p = world_to_camera_view(scene, cam, world @ Vector(np.median(verts, 0).tolist()))
            result[key] = [p.x, 1 - p.y, 1 if key == "wing" else -1]
        return result


def blender_point(p):
    """Atlas µm (x, +y dorsal, +z anterior) to Blender (X, -Y anterior, Z dorsal)."""
    return Vector((p[0], -p[2], p[1]))


def camera():
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.data.clip_start = 10
    cam.data.clip_end = 20000
    cam.data.sensor_width = 36
    return cam


def aim(cam, view: dict, t: float = 0.0):
    """Place the camera on `direction` from `target` (both atlas µm), with `up` the
    atlas direction that points up on screen. `spin` turns the view about an
    atlas axis by degrees over the clip (t from 0 to 1)."""
    target = blender_point(view["target"])
    direction = blender_point(view["direction"]).normalized()
    up = blender_point(view["up"]).normalized()
    if "spin" in view:
        spin = view["spin"]
        angle = math.radians(spin.get("start", 0) + spin["degrees"] * t)
        q = Quaternion(blender_point(spin["axis"]).normalized(), angle)
        direction, up = q @ direction, q @ up
    cam.location = target + direction * view["distance"] * (1 + view.get("dolly", 0) * t)
    forward = -direction
    right = forward.cross(up).normalized()
    screen_up = right.cross(forward)
    cam.matrix_world = Matrix.Translation(cam.location) @ Matrix((right, screen_up, -forward)).transposed().to_4x4()
    cam.data.lens = view["lens"]


def compositor(scene):
    tree = bpy.data.node_groups.new("Compositor", "CompositorNodeTree")
    tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    layers = tree.nodes.new("CompositorNodeRLayers")
    glare = tree.nodes.new("CompositorNodeGlare")
    glare.inputs["Type"].default_value = "Bloom"
    glare.inputs["Quality"].default_value = "High"
    glare.inputs["Threshold"].default_value = LOOK["bloom_threshold"]
    glare.inputs["Strength"].default_value = LOOK["bloom"]
    glare.inputs["Size"].default_value = LOOK["bloom_size"]
    out = tree.nodes.new("NodeGroupOutput")
    tree.links.new(layers.outputs["Image"], glare.inputs["Image"])
    tree.links.new(glare.outputs["Image"], out.inputs[0])
    scene.compositing_node_group = tree
    scene.render.use_compositing = True


def render(scene, size, path: Path):
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    settings = scene.render.image_settings
    settings.file_format = "PNG"
    settings.color_depth = "8"
    settings.color_mode = "RGB"
    settings.compression = 30
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print(f"wrote {path}", flush=True)


def condition(name: str) -> np.ndarray:
    return VALUES["values"][VMETA["conditions"].index(name)].astype(np.float64)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def shoot(scene, cam, brain, size, out: Path):
    """Render one frame; when the path shows, first save where its labels go."""
    if not brain.path.hide_render:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.with_suffix(".json").write_text(json.dumps(dict(anchors=brain.anchors(cam, scene))))
    render(scene, size, out)


def run():
    scene = reset()
    compositor(scene)
    cam = camera()
    brain = Brain()
    for task in JOB["tasks"]:
        view = JOB["views"][task["view"]]
        brain.show_vnc(view.get("vnc", True))
        brain.paint(condition(task["dust"]))
        brain.paint_path(condition(task["path"]) if task.get("path") else None)
        if task["kind"] == "still":
            aim(cam, view, task.get("t", 0.0))
            shoot(scene, cam, brain, task["size"], Path(task["out"]))
            continue
        # A clip: a moving camera, optionally the path cells flashing with each spike.
        flashes = np.load(task["spikes"]) if task.get("spikes") else None
        frames = round(task["fps"] * task["seconds"])
        for f in range(frames):
            out = Path(task["out"]) / f"{f:04d}.png"
            if out.exists():
                continue  # resume an interrupted clip
            if flashes is not None:
                brain.flash_path(flashes[f])
            aim(cam, view, ease(f / (frames - 1)))
            shoot(scene, cam, brain, task["size"], out)


if __name__ == "__main__":
    run()
