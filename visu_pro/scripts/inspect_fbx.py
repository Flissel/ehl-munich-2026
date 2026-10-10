"""Read-only inspector for binary FBX files (7.x).

Lists models (scene nodes), materials, textures and which materials/textures are
connected to which model. Used to understand the BMW asset before import.

Usage:  python -I scripts/inspect_fbx.py "path/to/file.fbx" [--json out.json]
"""
from __future__ import annotations

import json
import struct
import sys
import zlib
from collections import defaultdict


class Node:
    __slots__ = ("name", "props", "children")

    def __init__(self, name, props, children):
        self.name, self.props, self.children = name, props, children

    def find(self, name):
        return [c for c in self.children if c.name == name]


def _read_prop(buf, pos):
    t = chr(buf[pos]); pos += 1
    scalar = {"Y": "<h", "C": "<?", "I": "<i", "F": "<f", "D": "<d", "L": "<q"}
    if t in scalar:
        fmt = scalar[t]; size = struct.calcsize(fmt)
        return struct.unpack_from(fmt, buf, pos)[0], pos + size
    if t in "fdlib":
        n, enc, clen = struct.unpack_from("<III", buf, pos); pos += 12
        data = buf[pos:pos + clen]; pos += clen
        if enc == 1:
            data = zlib.decompress(data)
        fmt = {"f": "f", "d": "d", "l": "q", "i": "i", "b": "?"}[t]
        return list(struct.unpack(f"<{n}{fmt}", data)) if n < 64 else f"<array {t} x{n}>", pos
    if t in "SR":
        n = struct.unpack_from("<I", buf, pos)[0]; pos += 4
        raw = buf[pos:pos + n]; pos += n
        if t == "S":
            # FBX stores "Name\x00\x01Class"; keep the human-readable part.
            return raw.split(b"\x00\x01")[0].decode("utf-8", "replace"), pos
        return f"<raw {n} bytes>", pos
    raise ValueError(f"unknown property type {t!r} at {pos - 1}")


def _read_node(buf, pos, wide):
    if wide:
        end, nprops, _plen = struct.unpack_from("<QQQ", buf, pos); pos += 24
    else:
        end, nprops, _plen = struct.unpack_from("<III", buf, pos); pos += 12
    nlen = buf[pos]; pos += 1
    if end == 0:
        return None, pos + 0
    name = buf[pos:pos + nlen].decode("ascii", "replace"); pos += nlen
    props = []
    for _ in range(nprops):
        v, pos = _read_prop(buf, pos)
        props.append(v)
    children = []
    sentinel = 25 if wide else 13
    while pos < end - sentinel:
        child, pos = _read_node(buf, pos, wide)
        if child is None:
            break
        children.append(child)
    return Node(name, props, children), end


def parse(path):
    buf = open(path, "rb").read()
    if not buf.startswith(b"Kaydara FBX Binary"):
        raise SystemExit("Not a binary FBX file")
    version = struct.unpack_from("<I", buf, 23)[0]
    wide = version >= 7500
    pos, top = 27, []
    while pos < len(buf):
        node, pos = _read_node(buf, pos, wide)
        if node is None:
            break
        top.append(node)
    return version, top


def main():
    path = sys.argv[1]
    version, top = parse(path)
    by_name = {n.name: n for n in top}
    objects = by_name["Objects"].children
    objs = {}
    for o in objects:
        if len(o.props) >= 3:
            objs[o.props[0]] = (o.name, o.props[1], o.props[2], o)
    links = defaultdict(list)  # parent id -> child ids
    for c in by_name["Connections"].children:
        if c.props[0] in ("OO", "OP"):
            links[c.props[2]].append(c.props[1])

    def kids(oid, kind):
        return [objs[k] for k in links.get(oid, []) if k in objs and objs[k][0] == kind]

    settings = by_name.get("GlobalSettings")
    unit = None
    if settings:
        for p70 in settings.find("Properties70"):
            for p in p70.children:
                if p.props and p.props[0] in ("UnitScaleFactor", "UpAxis", "FrontAxis"):
                    unit = (unit or {}) | {p.props[0]: p.props[-1]}

    models, materials, textures = [], [], []
    for oid, (kind, name, sub, node) in objs.items():
        if kind == "Model":
            geos = kids(oid, "Geometry")
            mats = [m[1] for m in kids(oid, "Material")]
            models.append({"name": name, "type": sub, "has_geometry": bool(geos), "materials": mats})
        elif kind == "Material":
            texs = []
            for tid, (tk, tname, _, tnode) in ((k, objs[k]) for k in links.get(oid, []) if k in objs):
                pass
            materials.append({"name": name})
        elif kind == "Texture":
            fn = next((c.props[0] for c in node.children if c.name in ("RelativeFilename", "FileName")), None)
            textures.append({"name": name, "file": fn})
    # texture -> material connections are OP (texture is child of material)
    mat_tex = defaultdict(list)
    for c in by_name["Connections"].children:
        if c.props[0] == "OP" and c.props[1] in objs and c.props[2] in objs:
            child, parent = objs[c.props[1]], objs[c.props[2]]
            if child[0] == "Texture" and parent[0] == "Material":
                mat_tex[parent[1]].append({"slot": c.props[3], "texture": child[1]})
    for m in materials:
        m["textures"] = mat_tex.get(m["name"], [])

    report = {"fbx_version": version, "global_settings": unit, "models": models,
              "materials": materials, "textures": textures}
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump(report, open(out, "w", encoding="utf-8"), indent=2)
    print(f"FBX version {version}; settings {unit}")
    meshes = [m for m in models if m["has_geometry"]]
    print(f"{len(models)} models ({len(meshes)} with geometry), {len(materials)} materials, {len(textures)} textures")
    print("\n== Mesh models ==")
    for m in meshes:
        print(f"  {m['name']!r:45} mats={m['materials']}")
    print("\n== Materials ==")
    for m in materials:
        print(f"  {m['name']!r:40} {m['textures']}")
    print("\n== Textures ==")
    for t in textures:
        print(f"  {t['name']!r:40} {t['file']}")


if __name__ == "__main__":
    main()
