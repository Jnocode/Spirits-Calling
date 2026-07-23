# VR Optimization Guide (Spirits-Calling)

> [!IMPORTANT]
> **Performance Target**: Maintain **72 FPS (Quest)** or **90 FPS (PCVR)** at all times. Drops cause motion sickness.

## 1. Project Settings Check

- [ ] **Instanced Stereo**: ENABLED (Project Settings > Rendering > VR)
- [ ] **Mobile HDR**: DISABLED (for independent Quest builds)
- [ ] **Forward Shading**: ENABLED (Project Settings > Rendering > Forward Renderer)
  - *Why?* Better definition, lower overhead than Deferred in VR.
- [ ] **Anti-Aliasing**: MSAA (4x recommeded with Forward Shading).

## 2. Texture Optimization

Run the script `Scripts/CheckTextureSettings.py` to audit textures.

- **Power of Two**: All textures must be PoT (256, 512, 1024, 2048) or they won't stream/compress.
- **Max Size**: Cap normal maps at 1024, Reference textures at 2048. 4K textures are rarely needed in VR unless it's a Skybox.
- **Compression**: Use `Default` (DXT1/5) or `VectorDisplacementmap` (RGBA8). Avoid `UserInterface` (uncompressed) for scene objects.

## 3. Mesh & Draw Calls

- **Triangle Count**: Keep heroic assets under 15k tris. Background props under 1k.
- **LODs**: Force generate LODs for all Static Meshes.
- **Draw Calls**: Use `Merge Actors` tool for static background clusters.

## 4. Lighting

- **Dynamic Lights**: Minimize. 1 Directional Light (Sun) is fine.
- **Shadows**: Use **Cascaded Shadow Maps** (CSM) for near distance only.
- **Baking**: If targeting Standalone VR, bake lighting (GPU Lightmass) is mandatory.

## 5. Blueprint Performance

- **Tick**: Avoid `Event Tick`. Use Timers or Custom Events.
- **Casting**: Avoid `Cast To` in update loops. Use Interfaces (`BPI_Interactable`).
- **Physics**: Disable "Generate Overlap Events" on anything that doesn't need it.
