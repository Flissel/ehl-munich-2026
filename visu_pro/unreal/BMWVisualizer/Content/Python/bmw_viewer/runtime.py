"""BMW Studio viewer runtime.

Runs inside `UnrealEditor.exe BMWVisualizer.uproject -game -BMWViewer` (started from
init_unreal.py). Everything happens on the game thread inside a Slate post-tick callback:

* a NON-BLOCKING local TCP control server (127.0.0.1 only) speaking newline-delimited JSON;
  sockets are polled once per frame, so the game thread never waits on the network;
* an orbit camera (left-drag orbit, right-drag / mouse wheel zoom, R resets the view);
* a whitelist of design commands that only accept IDs from bmw_viewer.registry.

Protocol (one JSON object per line, response is one JSON line):
    -> {"id": 1, "token": "...", "command": "set_paint", "args": {"paint_id": "racing_red"}}
    <- {"id": 1, "ok": true, "result": {...}}   or   {"id": 1, "ok": false, "error": "..."}
"""
import hmac
import json
import math
import re
import socket
import time

import unreal

from bmw_viewer import registry

PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 64 * 1024
MAX_CLIENTS = 8
CAR_TAG = "BMWStudioCar"


def log(msg):
    unreal.log(f"[BMWViewer] {msg}")


def warn(msg):
    unreal.log_warning(f"[BMWViewer] {msg}")


def _arg(cmdline, name, default=None):
    m = re.search(r"-" + name + r"=(\"[^\"]*\"|\S+)", cmdline, re.IGNORECASE)
    return m.group(1).strip('"') if m else default


def _make_key(name):
    # FKey's KeyName isn't exposed as a Python property; import_text parses the key name.
    k = unreal.Key()
    if not k.import_text(name) or not unreal.InputLibrary.key_is_valid(k):
        raise ValueError(f"unknown input key {name!r}")
    return k


class OrbitCamera:
    def __init__(self):
        self.target = unreal.Vector(0, 0, 70)
        self.yaw, self.pitch, self.dist = 215.0, 12.0, 750.0
        self.goal = [self.yaw, self.pitch, self.dist]
        self.min_dist, self.max_dist = 350.0, 1600.0
        self.last_mouse = None
        self.keys = {n: _make_key(n) for n in (
            "LeftMouseButton", "RightMouseButton", "MouseScrollUp", "MouseScrollDown", "R")}

    def frame(self, center, radius):
        self.target = unreal.Vector(center.x, center.y, center.z * 0.8)
        self.min_dist, self.max_dist = radius * 1.1, radius * 6.0
        self.goal = [215.0, 10.0, radius * 3.4]

    def reset(self):
        self.goal = [215.0, 10.0, (self.min_dist / 1.1) * 3.4]

    def update(self, pc, camera, dt):
        down = lambda k: pc.is_input_key_down(self.keys[k])
        pressed = lambda k: pc.was_input_key_just_pressed(self.keys[k])
        pos = pc.get_mouse_position()
        pos = (pos[-2], pos[-1]) if pos else None
        if pos and self.last_mouse and (down("LeftMouseButton") or down("RightMouseButton")):
            dx, dy = pos[0] - self.last_mouse[0], pos[1] - self.last_mouse[1]
            if down("LeftMouseButton"):
                self.goal[0] += dx * 0.3
                self.goal[1] = max(-2.0, min(70.0, self.goal[1] + dy * 0.25))
            else:
                self.goal[2] *= 1.0 + dy * 0.004
        self.last_mouse = pos
        if pressed("MouseScrollUp"):
            self.goal[2] *= 0.9
        if pressed("MouseScrollDown"):
            self.goal[2] *= 1.1
        if pressed("R"):
            self.reset()
        self.goal[2] = max(self.min_dist, min(self.max_dist, self.goal[2]))

        a = 1.0 - math.exp(-dt * 10.0)  # frame-rate independent smoothing
        self.yaw += (self.goal[0] - self.yaw) * a
        self.pitch += (self.goal[1] - self.pitch) * a
        self.dist += (self.goal[2] - self.dist) * a
        y, p = math.radians(self.yaw), math.radians(self.pitch)
        loc = unreal.Vector(self.target.x + self.dist * math.cos(p) * math.cos(y),
                            self.target.y + self.dist * math.cos(p) * math.sin(y),
                            self.target.z + self.dist * math.sin(p))
        rot = unreal.MathLibrary.find_look_at_rotation(loc, self.target)
        camera.set_actor_location_and_rotation(loc, rot, False, False)


class Viewer:
    def __init__(self, cmdline):
        self.port = int(_arg(cmdline, "BMWControlPort", "30777"))
        self.token = _arg(cmdline, "BMWToken", "") or ""
        self.pending_model = _arg(cmdline, "BMWModel")
        self.server = None
        self.clients = {}  # socket -> bytearray
        self.pc = self.camera = self.car = None
        self.model_id = None
        self.slot_cache = {}  # slot kind -> [(index, original material)]
        self.design = {"paint": None, "wheel_style": None}
        self.orbit = OrbitCamera()
        self.started = time.time()
        self.fps = 0.0
        self._errors_logged = set()
        self.handle = None

    # ------------------------------------------------------------------ lifecycle
    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows: refuse to share the port
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        self.server.bind(("127.0.0.1", self.port))
        self.server.listen(MAX_CLIENTS)
        self.server.setblocking(False)
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        log(f"Control server listening on 127.0.0.1:{self.port} (token {'required' if self.token else 'not set'})")

    def tick(self, dt):
        try:
            if dt > 0:
                self.fps = self.fps * 0.95 + (1.0 / dt) * 0.05
            self._ensure_world()
            if self.pc and self.camera:
                self.orbit.update(self.pc, self.camera, dt)
            self._poll_network()
        except Exception as e:  # never let an exception kill the tick callback
            key = f"{type(e).__name__}:{e}"
            if key not in self._errors_logged:
                self._errors_logged.add(key)
                unreal.log_error(f"[BMWViewer] tick error: {key}")

    def _ensure_world(self):
        if self.pc is not None and unreal.SystemLibrary.is_valid(self.pc):
            return
        self.pc = self.camera = self.car = None
        for pc in unreal.ObjectIterator(unreal.PlayerController):
            if unreal.SystemLibrary.is_valid(pc) and pc.get_world() is not None \
                    and not pc.get_path_name().startswith("/Script/"):
                self.pc = pc
                break
        if self.pc is None:
            return
        cams = unreal.GameplayStatics.get_all_actors_with_tag(self.pc, "ShowroomCamera")
        if not cams:
            warn("ShowroomCamera not found in level")
            return
        self.camera = cams[0]
        self.pc.set_view_target_with_blend(self.camera, 0.0)
        self.pc.set_editor_property("show_mouse_cursor", True)
        log("World ready")
        if self.pending_model:
            try:
                self.cmd_open_model({"model_id": self.pending_model})
            except Exception as e:
                unreal.log_error(f"[BMWViewer] initial open_model failed: {e}")
            self.pending_model = None

    # ------------------------------------------------------------------ networking
    def _poll_network(self):
        for _ in range(4):  # accept a few new connections per frame
            try:
                conn, addr = self.server.accept()
            except (BlockingIOError, OSError):
                break
            if addr[0] != "127.0.0.1" or len(self.clients) >= MAX_CLIENTS:
                conn.close()
                continue
            conn.setblocking(False)
            self.clients[conn] = bytearray()
        for conn in list(self.clients):
            buf = self.clients[conn]
            try:
                data = conn.recv(65536)
                if not data:
                    self._drop(conn)
                    continue
                buf.extend(data)
            except BlockingIOError:
                pass
            except OSError:
                self._drop(conn)
                continue
            if len(buf) > MAX_MESSAGE_BYTES and b"\n" not in buf:
                self._send(conn, {"id": None, "ok": False, "error": "message too large"})
                self._drop(conn)
                continue
            while b"\n" in buf:
                line, _, rest = bytes(buf).partition(b"\n")
                buf[:] = rest
                if line.strip():
                    self._send(conn, self._handle_line(line))

    def _drop(self, conn):
        self.clients.pop(conn, None)
        try:
            conn.close()
        except OSError:
            pass

    def _send(self, conn, obj):
        try:
            conn.setblocking(True)
            conn.settimeout(0.25)
            conn.sendall((json.dumps(obj) + "\n").encode("utf-8"))
            conn.setblocking(False)
        except OSError:
            self._drop(conn)

    def _handle_line(self, line):
        try:
            msg = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"id": None, "ok": False, "error": "invalid JSON"}
        if not isinstance(msg, dict):
            return {"id": None, "ok": False, "error": "message must be an object"}
        mid = msg.get("id")
        if self.token and not hmac.compare_digest(str(msg.get("token", "")), self.token):
            return {"id": mid, "ok": False, "error": "unauthorized"}
        command, args = msg.get("command"), msg.get("args") or {}
        handler = COMMANDS.get(command)
        if handler is None or not isinstance(args, dict):
            return {"id": mid, "ok": False, "error": f"unsupported command: {command!r}"}
        try:
            return {"id": mid, "ok": True, "result": handler(self, args)}
        except CommandError as e:
            return {"id": mid, "ok": False, "error": str(e)}
        except Exception as e:
            unreal.log_error(f"[BMWViewer] command {command} failed: {e}")
            return {"id": mid, "ok": False, "error": f"internal error in {command}"}

    # ------------------------------------------------------------------ commands
    def _require_car(self):
        if self.car is None or not unreal.SystemLibrary.is_valid(self.car):
            raise CommandError("no model loaded; call open_model first")
        return self.car.static_mesh_component

    def cmd_status(self, _args):
        return {
            "protocol": PROTOCOL_VERSION,
            "world_ready": bool(self.pc and self.camera),
            "ready": bool(self.pc and self.camera and self.car and unreal.SystemLibrary.is_valid(self.car)),
            "model_id": self.model_id,
            "design": dict(self.design),
            "fps": round(self.fps, 1),
            "uptime_s": round(time.time() - self.started, 1),
        }

    def cmd_open_model(self, args):
        model_id = args.get("model_id")
        spec = registry.MODELS.get(model_id)
        if spec is None:
            raise CommandError(f"unknown model_id {model_id!r}")
        if not (self.pc and self.camera):
            self.pending_model = model_id
            return {"model_id": model_id, "loaded": False, "queued": True}
        if self.car is not None and unreal.SystemLibrary.is_valid(self.car) and self.model_id == model_id:
            return {"model_id": model_id, "loaded": True, "already_loaded": True}
        mesh = unreal.load_asset(spec["mesh"])
        if mesh is None:
            raise CommandError(f"asset for {model_id} missing; run scripts/build_unreal.ps1")
        # The level contains one movable StaticMeshActor tagged CAR_TAG ("car slot"); loading a
        # model assigns the registered mesh to it (no runtime actor spawning needed).
        slots = unreal.GameplayStatics.get_all_actors_with_tag(self.pc, CAR_TAG)
        if not slots:
            raise CommandError("showroom level has no car slot actor; rebuild the showroom")
        car = slots[0]
        spawn = unreal.GameplayStatics.get_all_actors_with_tag(self.pc, "CarSpawnPoint")
        origin = spawn[0].get_actor_location() if spawn else unreal.Vector(0, 0, 0)
        comp = car.static_mesh_component
        comp.set_static_mesh(mesh)
        for i in range(comp.get_num_materials()):  # clear overrides -> mesh's own materials
            comp.set_material(i, None)
        car.set_actor_hidden_in_game(False)
        # Normalize scale/orientation from the registry, then put the car's bottom-center on the spawn point
        ext = mesh.get_bounds().box_extent
        scale = spec.get("target_length_cm", 2 * max(ext.x, ext.y)) / (2 * max(ext.x, ext.y))
        car.set_actor_location(origin, False, False)
        car.set_actor_scale3d(unreal.Vector(scale, scale, scale))
        car.set_actor_rotation(unreal.Rotator(0, 0, spec.get("yaw", 0.0)), False)
        b_origin, b_ext = car.get_actor_bounds(False)
        loc = car.get_actor_location()
        car.set_actor_location(unreal.Vector(loc.x - (b_origin.x - origin.x), loc.y - (b_origin.y - origin.y),
                                             loc.z - (b_origin.z - b_ext.z - origin.z)), False, False)
        b_origin, b_ext = car.get_actor_bounds(False)
        self.orbit.frame(b_origin, math.sqrt(b_ext.x ** 2 + b_ext.y ** 2 + b_ext.z ** 2))

        self.car, self.model_id = car, model_id
        self.design = {"paint": None, "wheel_style": None}
        self.slot_cache = {}
        for kind in ("paint_slots", "rim_slots"):
            wanted = set(spec[kind])
            self.slot_cache[kind] = [(i, comp.get_material(i)) for i, name in enumerate(comp.get_material_slot_names())
                                     if registry.normalize_slot(name) in wanted]
            if not self.slot_cache[kind]:
                warn(f"no material slots found for {kind} on {model_id}")
        log(f"Loaded {model_id} (scale {scale:.3f}, size {2*b_ext.x:.0f}x{2*b_ext.y:.0f}x{2*b_ext.z:.0f} cm)")
        return {"model_id": model_id, "loaded": True,
                "size_cm": [round(2 * b_ext.x), round(2 * b_ext.y), round(2 * b_ext.z)]}

    def _apply_to_slots(self, kind, vectors, scalars):
        comp = self._require_car()
        slots = self.slot_cache.get(kind) or []
        if not slots:
            raise CommandError(f"this model has no {kind.replace('_', ' ')} configured")
        confirmed = []
        for index, original in slots:
            mid = comp.create_dynamic_material_instance(index, original)
            for k, v in vectors.items():
                mid.set_vector_parameter_value(k, unreal.LinearColor(v[0], v[1], v[2], 1.0))
            for k, v in scalars.items():
                mid.set_scalar_parameter_value(k, float(v))
            # Read back from the material actually bound to the component to confirm the change
            bound = comp.get_material(index)
            name, v = next(iter(vectors.items()))
            got = None
            if isinstance(bound, unreal.MaterialInstanceDynamic):
                getter = getattr(bound, "get_vector_parameter_value", None) or \
                    getattr(bound, "k2_get_vector_parameter_value")
                got = getter(name)
            if got is None or abs(got.r - v[0]) > 1e-3 or abs(got.g - v[1]) > 1e-3 or abs(got.b - v[2]) > 1e-3:
                raise CommandError(f"material slot {index} did not accept the change")
            confirmed.append(index)
        return confirmed

    def cmd_set_paint(self, args):
        paint_id = args.get("paint_id")
        if paint_id not in registry.PAINTS:
            raise CommandError(f"unknown paint_id {paint_id!r}; allowed: {sorted(registry.PAINTS)}")
        label, color, metallic, roughness, _cc = registry.PAINTS[paint_id]
        slots = self._apply_to_slots("paint_slots", {"PaintColor": color},
                                     {"Metallic": metallic, "Roughness": roughness})
        self.design["paint"] = paint_id
        return {"applied": True, "paint_id": paint_id, "label": label, "slots": slots}

    def cmd_set_wheel_style(self, args):
        style_id = args.get("style_id")
        if style_id not in registry.WHEEL_STYLES:
            raise CommandError(f"unknown style_id {style_id!r}; allowed: {sorted(registry.WHEEL_STYLES)}")
        label, color, metallic, roughness = registry.WHEEL_STYLES[style_id]
        slots = self._apply_to_slots("rim_slots", {"BaseColor": color},
                                     {"Metallic": metallic, "Roughness": roughness})
        self.design["wheel_style"] = style_id
        return {"applied": True, "style_id": style_id, "label": label, "slots": slots}

    def cmd_reset_design(self, _args):
        comp = self._require_car()
        for kind in ("paint_slots", "rim_slots"):
            for index, original in self.slot_cache.get(kind, []):
                comp.set_material(index, original)
        self.design = {"paint": None, "wheel_style": None}
        return {"applied": True, "design": dict(self.design)}

    def cmd_reset_camera(self, _args):
        self.orbit.reset()
        return {"applied": True}

    def cmd_screenshot(self, _args):
        if not self.pc:
            raise CommandError("viewer world not ready")
        unreal.SystemLibrary.execute_console_command(self.pc, "HighResShot 1", self.pc)
        return {"requested": True, "location": "unreal/BMWVisualizer/Saved/Screenshots"}


class CommandError(Exception):
    pass


COMMANDS = {
    "get_viewer_status": Viewer.cmd_status,
    "open_model": Viewer.cmd_open_model,
    "set_paint": Viewer.cmd_set_paint,
    "set_wheel_style": Viewer.cmd_set_wheel_style,
    "reset_design": Viewer.cmd_reset_design,
    "reset_camera": Viewer.cmd_reset_camera,
    "screenshot": Viewer.cmd_screenshot,
}

_viewer = None


def start(cmdline):
    global _viewer
    if _viewer is None:
        _viewer = Viewer(cmdline)
        _viewer.start()
    return _viewer
