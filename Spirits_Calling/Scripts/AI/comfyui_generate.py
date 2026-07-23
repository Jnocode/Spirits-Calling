#!/usr/bin/env python3
"""
Spirits Calling — ComfyUI batch asset generator.

Reads prompts_civilizations.json and drives a local ComfyUI instance
(default http://127.0.0.1:8188) through a standard txt2img graph, saving each
result as a PNG under RawAssets/AI/<category>/<name>.png ready to import into UE.

Usage:
    python comfyui_generate.py --checkpoint sd_xl_base_1.0.safetensors
    python comfyui_generate.py --only East_pattern,Cyber_pattern
    python comfyui_generate.py --list
    python comfyui_generate.py --dry-run          # print the queue, generate nothing

Notes:
  * No third-party deps — pure stdlib (urllib, json).
  * The workflow is a plain CheckpointLoaderSimple -> CLIPTextEncode x2 ->
    EmptyLatentImage -> KSampler -> VAEDecode -> SaveImage graph. If your
    ComfyUI uses different node class names (custom nodes), tweak build_workflow().
  * Tileable items set the latent to circular where supported; true seamless
    tiling is best finished in the SaveImage step or a tiling VAE — for most
    checkpoints the 'seamless tileable' prompt wording gets you 90% there.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
# Scripts/AI -> project root is two levels up; RawAssets sits under the project root.
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_ROOT = os.path.join(PROJECT_ROOT, "RawAssets", "AI")
PROMPTS = os.path.join(HERE, "prompts_civilizations.json")


def load_prompts(path=None):
    with open(path or PROMPTS, "r", encoding="utf-8") as f:
        return json.load(f)


def list_checkpoints(server):
    """Query ComfyUI for the checkpoint filenames it can see."""
    try:
        info = http_json(f"{server}/object_info/CheckpointLoaderSimple")
        names = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        print(f"[comfyui] {len(names)} checkpoint(s) available:")
        for n in names:
            print(f"    {n}")
        return names
    except Exception as e:
        print(f"[comfyui] could not list checkpoints from {server}: {e}")
        return []


def get_workflow(server, name):
    """Fetch a saved ComfyUI workflow (UI JSON) by name via the userdata API and print it."""
    import urllib.parse as _up

    # 1) find the exact stored path under the workflows dir.
    listing = None
    for base in ("/api/userdata", "/userdata"):
        for params in ("?dir=workflows&recurse=true", "?dir=workflows"):
            try:
                listing = http_json(f"{server}{base}{params}")
                if listing is not None:
                    break
            except Exception:
                continue
        if listing is not None:
            break

    candidates = []
    if isinstance(listing, list):
        for entry in listing:
            path = entry if isinstance(entry, str) else (entry.get("path") or entry.get("name") or "")
            if name.lower() in str(path).lower():
                candidates.append(str(path))
    print(f"[comfyui] workflow files matching '{name}': {candidates if candidates else 'none via listing'}")

    # 2) try fetching, using found candidates first, then common fallbacks.
    tries = []
    for c in candidates:
        rel = c if c.startswith("workflows") else f"workflows/{c}"
        tries.append(rel)
    for suffix in (f"workflows/{name}.json", f"workflows/{name}"):
        if suffix not in tries:
            tries.append(suffix)

    out_path = os.path.join(PROJECT_ROOT, "_workflow_dump.json")
    for base in ("/api/userdata", "/userdata"):
        for rel in tries:
            enc = _up.quote(rel, safe="")
            url = f"{server}{base}/{enc}"
            try:
                raw = http_bytes(url)
            except Exception:
                continue
            # Write bytes straight to a UTF-8 file (avoid cp950 console encoding errors).
            with open(out_path, "wb") as f:
                f.write(raw)
            print(f"[comfyui] fetched {base}/{rel} -> {out_path} ({len(raw)} bytes)")
            return
    print("[comfyui] could not fetch workflow (see listing count "
          + str(len(listing) if isinstance(listing, list) else 'n/a') + ")")


def dump_schemas(server, names):
    """Print the input schema (+ combo options / model filenames) for named node classes."""
    for name in [n.strip() for n in names.split(",") if n.strip()]:
        try:
            info = http_json(f"{server}/object_info/{name}")
        except Exception as e:
            print(f"### {name}: ERROR {e}")
            continue
        spec = info.get(name)
        if not spec:
            print(f"### {name}: NOT FOUND")
            continue
        print(f"### {name}")
        inp = spec.get("input", {})
        for section in ("required", "optional"):
            fields = inp.get(section, {})
            if not fields:
                continue
            print(f"  [{section}]")
            for fname, fdef in fields.items():
                t = fdef[0] if isinstance(fdef, (list, tuple)) and fdef else fdef
                if isinstance(t, list):
                    opts = ", ".join(str(x) for x in t[:40])
                    more = " ..." if len(t) > 40 else ""
                    print(f"    {fname}: COMBO[{opts}{more}]")
                else:
                    extra = fdef[1] if isinstance(fdef, (list, tuple)) and len(fdef) > 1 else {}
                    print(f"    {fname}: {t}  {extra if extra else ''}")
        outs = spec.get("output", [])
        onames = spec.get("output_name", outs)
        print(f"  [output] {list(zip(outs, onames)) if outs else outs}")
        print()


def dump_nodes(server, keyword=""):
    """List the installed node class names (optionally filtered by a substring)."""
    try:
        info = http_json(f"{server}/object_info")
    except Exception as e:
        print(f"[comfyui] could not fetch /object_info from {server}: {e}")
        return
    kw = keyword.lower()
    names = sorted(info.keys())
    if kw:
        names = [n for n in names if kw in n.lower()]
    print(f"[comfyui] {len(names)} node type(s)" + (f" matching '{keyword}'" if keyword else "") + ":")
    for n in names:
        print(f"    {n}")


def http_json(url, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def http_bytes(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def build_workflow(item, defaults, checkpoint, seed):
    """Return a ComfyUI prompt graph (dict of node_id -> node)."""
    w = item.get("width", defaults["width"])
    h = item.get("height", defaults["height"])
    positive = item["prompt"]
    negative = item.get("negative", defaults["negative"])
    steps = item.get("steps", defaults["steps"])
    cfg = item.get("cfg", defaults["cfg"])
    sampler = item.get("sampler", defaults["sampler"])
    scheduler = item.get("scheduler", defaults["scheduler"])

    return {
        "4": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": checkpoint}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["4", 1], "text": positive}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["4", 1], "text": negative}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "3": {"class_type": "KSampler",
              "inputs": {"model": ["4", 0], "positive": ["6", 0],
                         "negative": ["7", 0], "latent_image": ["5", 0],
                         "seed": seed, "steps": steps, "cfg": cfg,
                         "sampler_name": sampler, "scheduler": scheduler,
                         "denoise": 1.0}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["8", 0], "filename_prefix": "spirits_" + item["name"]}},
    }


def queue_prompt(server, workflow, client_id):
    res = http_json(f"{server}/prompt", {"prompt": workflow, "client_id": client_id})
    return res["prompt_id"]


def wait_for(server, prompt_id, timeout=600):
    start = time.time()
    while time.time() - start < timeout:
        try:
            hist = http_json(f"{server}/history/{prompt_id}")
        except urllib.error.URLError:
            time.sleep(1.5)
            continue
        if prompt_id in hist:
            return hist[prompt_id]
        time.sleep(1.5)
    raise TimeoutError(f"Timed out waiting for prompt {prompt_id}")


def save_outputs(server, record, item):
    out_dir = os.path.join(OUT_ROOT, item["category"].replace("/", os.sep))
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    multi = 0
    for node in record.get("outputs", {}).values():
        for img in node.get("images", []):
            qs = urllib.parse.urlencode({
                "filename": img["filename"],
                "subfolder": img.get("subfolder", ""),
                "type": img.get("type", "output"),
            })
            data = http_bytes(f"{server}/view?{qs}")
            suffix = "" if multi == 0 else f"_{multi}"
            dest = os.path.join(out_dir, f"{item['name']}{suffix}.png")
            with open(dest, "wb") as f:
                f.write(data)
            saved.append(dest)
            multi += 1
    return saved


def main():
    ap = argparse.ArgumentParser(description="ComfyUI batch generator for Spirits Calling")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--checkpoint", default="sd_xl_base_1.0.safetensors",
                    help="Checkpoint filename as it appears in ComfyUI/models/checkpoints")
    ap.add_argument("--only", default="", help="Comma-separated item names to generate")
    ap.add_argument("--seed", type=int, default=-1, help="Fixed seed (-1 = random per item)")
    ap.add_argument("--list", action="store_true", help="List items and exit")
    ap.add_argument("--list-checkpoints", action="store_true", help="Ask ComfyUI which checkpoints exist, then exit")
    ap.add_argument("--dry-run", action="store_true", help="Show the queue, generate nothing")
    ap.add_argument("--steps", type=int, default=0, help="Override sampler steps (e.g. 8 for SDXL Turbo)")
    ap.add_argument("--cfg", type=float, default=0.0, help="Override CFG scale (e.g. 2.0 for Turbo)")
    ap.add_argument("--sampler", default="", help="Override sampler_name")
    ap.add_argument("--scheduler", default="", help="Override scheduler")
    ap.add_argument("--prompts", default="", help="Alternate prompt table JSON (e.g. prompts_vfx.json)")
    ap.add_argument("--list-nodes", action="store_true", help="List installed node class names, then exit")
    ap.add_argument("--nodes-filter", default="", help="Substring filter for --list-nodes")
    ap.add_argument("--dump-schemas", default="", help="Comma-separated node classes: print their input schemas, then exit")
    ap.add_argument("--get-workflow", default="", help="Fetch a saved ComfyUI workflow (UI JSON) by name, then exit")
    args = ap.parse_args()

    if args.get_workflow:
        get_workflow(args.server, args.get_workflow)
        return

    if getattr(args, "list_checkpoints", False):
        list_checkpoints(args.server)
        return

    if getattr(args, "list_nodes", False):
        dump_nodes(args.server, args.nodes_filter)
        return

    if args.dump_schemas:
        dump_schemas(args.server, args.dump_schemas)
        return

    cfg = load_prompts(args.prompts or None)
    defaults = cfg["defaults"]
    items = cfg["items"]

    # CLI overrides (handy for Turbo-style checkpoints that need few steps / low CFG).
    if args.steps > 0:
        defaults["steps"] = args.steps
    if args.cfg > 0:
        defaults["cfg"] = args.cfg
    if args.sampler:
        defaults["sampler"] = args.sampler
    if args.scheduler:
        defaults["scheduler"] = args.scheduler

    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        items = [it for it in items if it["name"] in wanted]

    if args.list:
        for it in cfg["items"]:
            print(f"  {it['name']:22s} -> RawAssets/AI/{it['category']}/{it['name']}.png")
        return

    print(f"[comfyui] server   : {args.server}")
    print(f"[comfyui] checkpoint: {args.checkpoint}")
    print(f"[comfyui] output    : {OUT_ROOT}")
    print(f"[comfyui] items     : {len(items)}")

    if args.dry_run:
        for it in items:
            w = it.get("width", defaults["width"])
            h = it.get("height", defaults["height"])
            print(f"  - {it['name']} ({w}x{h})  {it['category']}")
        print("[comfyui] dry-run: nothing generated.")
        return

    # Fail fast if the server isn't up (respects the no-fallback rule: we only
    # talk to the local ComfyUI API, never scrape the web).
    try:
        http_json(f"{args.server}/system_stats")
    except Exception as e:
        print(f"[comfyui] ERROR: cannot reach ComfyUI at {args.server}: {e}")
        print("          Start ComfyUI first (python main.py) and retry.")
        sys.exit(1)

    client_id = str(uuid.uuid4())
    for i, it in enumerate(items, 1):
        seed = args.seed if args.seed >= 0 else uuid.uuid4().int % (2**31)
        print(f"[{i}/{len(items)}] {it['name']} (seed {seed}) ...", flush=True)
        wf = build_workflow(it, defaults, args.checkpoint, seed)
        try:
            pid = queue_prompt(args.server, wf, client_id)
            record = wait_for(args.server, pid)
            saved = save_outputs(args.server, record, it)
            for s in saved:
                print(f"        saved {s}")
        except Exception as e:
            print(f"        FAILED: {e}")

    print("[comfyui] done.")


if __name__ == "__main__":
    main()
