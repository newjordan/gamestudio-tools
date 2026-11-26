# How x_harvest could slot into existing datasets (nothing modified, no training, nothing uploaded)
Candidates only; Jordan decides. clean_v2 and benchmark were NOT touched.
- 2D sprites/tiles/VFX (PVFX Foundry, Super Grotto Escape, amber-pixel64): natural fit as extra source games/packs for clean_v2 sprite/tile classes.
  PVFX has per-effect sprite-sheet.png + manifest.json (frame metadata) -> usable as animation-sheet examples.
  amber-pixel64: filter out the 19,332 Kenney-tagged rows (author/pack column) first; per-row licence_id and source_url give provenance.
- For the benchmark (v1.x): treat as a NEW held-out source group; re-run the T1-norm / size-leak control on it before scoring (native-size leaks are the known issue). amber-pixel64 is already 64x64, so it carries no native-size leak but is not representative of real frames.
- 3D (OpenKit3D, SigilsVault Modular Dungeon Kit): no 3D class exists in clean_v2 as far as I know; would need rendered views or a separate 3D track.
- Code/tools/skills (pixelfx, godot-workbench, RenderLens, GodotDialogue Lite, spritefusion-sprite-normals, scenario/blender/threejs skills, sozai-search-mcp): fit the game-dev-tools corpus, not the image benchmark.
- lazyneon tileset is AI-generated: keep out of ground-truth sets.
