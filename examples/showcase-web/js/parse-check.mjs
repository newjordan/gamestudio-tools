import { readJSON, readText, readBytes, parseTiledMap, parseAtlas, parseBMFont, parseWav } from "./gst-loader.mjs";
import { resolve } from "node:path";

const base = resolve(process.argv[2] || ".");
const map = parseTiledMap(await readJSON("art/level.json", { base }));
const atlas = parseAtlas(await readJSON("art/player.json", { base }));
const font = parseBMFont(await readText("font/label.fnt", { base }));
const wav = parseWav(await readBytes("sfx/coin.wav", { base }));
const ground = map.layers.find((l) => l.name === "ground");
const walls = map.layers.find((l) => l.name === "walls");
const objs = (map.layers.find((l) => l.type === "objectgroup") || {}).objects || [];
if (!ground || !ground.data || !ground.data.length) throw new Error("map has no ground data");
if (!walls) throw new Error("map has no walls layer");
if (!atlas.frames.walk_01 || !atlas.frames.coin) throw new Error("atlas missing walk_01 or coin");
if (!font.chars[67]) throw new Error("font missing C");
if (!(wav.frames > 0 && wav.sampleRate > 0)) throw new Error("wav failed to parse");
const rec = {
  ok: true,
  map: { width: map.width, height: map.height, layers: map.layers.length, objects: objs.map((o) => o.name) },
  atlas: { names: atlas.names, image: atlas.meta.image },
  font: { chars: Object.keys(font.chars).length, lineHeight: font.common.lineHeight, page: font.pages[0] },
  wav: { sampleRate: wav.sampleRate, channels: wav.channels, bits: wav.bits, frames: wav.frames },
};
process.stdout.write(JSON.stringify(rec, null, 2) + "\n");
