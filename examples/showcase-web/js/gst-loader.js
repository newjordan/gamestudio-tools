/* gst-loader.js — parse Tiled JSON maps, TexturePacker-style atlas JSON,
 * AngelCode BMFont, and PCM WAV, plus canvas helpers. No dependencies.
 *
 * Browser: <script src="gst-loader.js"></script>  →  window.GSTLoader
 * Node CJS: const GST = require("./gst-loader.js");
 * Node / bundler ESM: import { parseTiledMap, ... } from "./gst-loader.mjs";
 *
 * Known gaps: Tiled base64 tile data is only decoded when uncompressed
 * (no zlib / gzip / zstd); flipped Tiled GIDs are masked but not rendered
 * with transforms; WAV support is PCM only (format 1).
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  if (typeof root !== "undefined") {
    root.GSTLoader = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  var GID_MASK = 0x1fffffff;

  function isNode() {
    return typeof process !== "undefined" && process.versions && process.versions.node &&
      typeof document === "undefined";
  }

  function joinBase(base, path) {
    if (!base) return path;
    if (typeof path === "string" && (/^[a-z]+:/i.test(path) || path.charAt(0) === "/")) return path;
    if (typeof URL === "function" && /[a-z]+:/i.test(String(base))) {
      return new URL(path, base.endsWith("/") ? base : base + "/").href;
    }
    var b = String(base).replace(/\/+$/, "");
    return b + "/" + String(path).replace(/^\/+/, "");
  }

  function readText(path, options) {
    options = options || {};
    if (options.readText) return Promise.resolve(options.readText(path));
    var full = joinBase(options.base || "", path);
    if (isNode()) {
      return import("node:fs/promises").then(function (fs) {
        return import("node:path").then(function (pathMod) {
          var p = options.base ? pathMod.resolve(options.base, path) : path;
          return fs.readFile(p, "utf8");
        });
      });
    }
    return fetch(full).then(function (r) {
      if (!r.ok) throw new Error("GET " + full + " failed: " + r.status);
      return r.text();
    });
  }

  function readJSON(path, options) {
    return readText(path, options).then(function (t) { return JSON.parse(t); });
  }

  function readBytes(path, options) {
    options = options || {};
    if (options.readBytes) return Promise.resolve(options.readBytes(path));
    var full = joinBase(options.base || "", path);
    if (isNode()) {
      return import("node:fs/promises").then(function (fs) {
        return import("node:path").then(function (pathMod) {
          var p = options.base ? pathMod.resolve(options.base, path) : path;
          return fs.readFile(p).then(function (buf) { return new Uint8Array(buf); });
        });
      });
    }
    return fetch(full).then(function (r) {
      if (!r.ok) throw new Error("GET " + full + " failed: " + r.status);
      return r.arrayBuffer().then(function (b) { return new Uint8Array(b); });
    });
  }

  function decodeBase64U32LE(b64) {
    var bin;
    if (typeof atob === "function") {
      bin = atob(b64.replace(/\s+/g, ""));
      var bytes = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    } else if (typeof Buffer !== "undefined") {
      bytes = new Uint8Array(Buffer.from(b64.replace(/\s+/g, ""), "base64"));
    } else {
      throw new Error("no base64 decoder available");
    }
    if (bytes.length % 4 !== 0) throw new Error("base64 tile data length is not a multiple of 4");
    var view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    var out = new Array(bytes.length / 4);
    for (var j = 0; j < out.length; j++) out[j] = view.getUint32(j * 4, true);
    return out;
  }

  function decodeTileData(data, encoding, compression) {
    if (data == null) return [];
    if (compression && compression !== "" && compression !== "none") {
      throw new Error("compressed Tiled tile data (" + compression + ") is not supported");
    }
    if (encoding === "csv" || (typeof data === "string" && (!encoding || encoding === "csv"))) {
      var s = String(data).trim();
      if (!s) return [];
      return s.split(",").map(function (n) { return parseInt(n, 10) || 0; });
    }
    if (encoding === "base64" || (typeof data === "string" && encoding === "base64")) {
      return decodeBase64U32LE(data);
    }
    if (Array.isArray(data)) return data.slice();
    throw new Error("unsupported Tiled tile data encoding: " + (encoding || typeof data));
  }

  function parseTiledMap(data) {
    if (typeof data === "string") data = JSON.parse(data);
    if (!data || data.type !== "map") {
      // allow a raw object that looks like a map (width/height/layers)
      if (!data || data.width == null || !data.layers) {
        throw new Error("not a Tiled JSON map");
      }
    }
    var layers = (data.layers || []).map(function (l) {
      var out = {
        id: l.id,
        name: l.name || "",
        type: l.type,
        visible: l.visible !== false,
        opacity: l.opacity == null ? 1 : l.opacity,
        width: l.width,
        height: l.height,
        x: l.x || 0,
        y: l.y || 0
      };
      if (l.type === "tilelayer") {
        out.data = decodeTileData(l.data, l.encoding, l.compression);
      } else if (l.type === "objectgroup") {
        out.objects = (l.objects || []).map(function (o) {
          return {
            id: o.id,
            name: o.name || "",
            type: o.type || o.class || "",
            x: o.x || 0,
            y: o.y || 0,
            width: o.width || 0,
            height: o.height || 0,
            properties: o.properties || []
          };
        });
      }
      return out;
    });
    return {
      width: data.width,
      height: data.height,
      tilewidth: data.tilewidth,
      tileheight: data.tileheight,
      infinite: !!data.infinite,
      tilesets: (data.tilesets || []).map(function (ts) {
        return {
          name: ts.name || "",
          firstgid: ts.firstgid || 1,
          tilewidth: ts.tilewidth || data.tilewidth,
          tileheight: ts.tileheight || data.tileheight,
          tilecount: ts.tilecount,
          columns: ts.columns,
          image: ts.image,
          imagewidth: ts.imagewidth,
          imageheight: ts.imageheight
        };
      }),
      layers: layers
    };
  }

  function parseAtlas(data) {
    if (typeof data === "string") data = JSON.parse(data);
    if (!data || data.frames == null) throw new Error("atlas JSON has no frames");
    var frames = {};
    var order = [];
    function rec(name, fr) {
      var box = fr.frame || fr;
      var ss = fr.sourceSize || {};
      var sss = fr.spriteSourceSize || {};
      var w = box.w, h = box.h;
      frames[name] = {
        name: name,
        x: box.x | 0,
        y: box.y | 0,
        w: w | 0,
        h: h | 0,
        rotated: !!fr.rotated,
        trimmed: !!fr.trimmed,
        sourceSize: { w: ss.w != null ? ss.w : w, h: ss.h != null ? ss.h : h },
        spriteSourceSize: {
          x: sss.x || 0,
          y: sss.y || 0,
          w: sss.w != null ? sss.w : w,
          h: sss.h != null ? sss.h : h
        }
      };
      order.push(name);
    }
    if (Array.isArray(data.frames)) {
      data.frames.forEach(function (fr, i) {
        rec(fr.filename || fr.name || fr.id || String(i), fr);
      });
    } else {
      Object.keys(data.frames).forEach(function (k) { rec(k, data.frames[k]); });
    }
    var meta = data.meta || {};
    return {
      frames: frames,
      names: order,
      meta: {
        image: meta.image || meta.texture || null,
        size: meta.size || null,
        scale: meta.scale || "1"
      }
    };
  }

  function parseKV(line) {
    var out = {};
    var re = /(\w+)=(?:"([^"]*)"|(\S+))/g;
    var m;
    while ((m = re.exec(line))) out[m[1]] = m[2] != null ? m[2] : m[3];
    return out;
  }

  function parseBMFont(text) {
    var common = {}, pages = {}, chars = {}, kernings = [];
    String(text).split(/\r?\n/).forEach(function (line) {
      line = line.trim();
      if (!line) return;
      var kind = line.split(/\s+/, 1)[0];
      var kv = parseKV(line);
      if (kind === "common") {
        common = {
          lineHeight: +kv.lineHeight || 0,
          base: +kv.base || 0,
          scaleW: +kv.scaleW || 0,
          scaleH: +kv.scaleH || 0,
          pages: +kv.pages || 1
        };
      } else if (kind === "page") {
        pages[+kv.id || 0] = kv.file;
      } else if (kind === "char") {
        chars[+kv.id] = {
          id: +kv.id,
          x: +kv.x || 0,
          y: +kv.y || 0,
          width: +kv.width || 0,
          height: +kv.height || 0,
          xoffset: +kv.xoffset || 0,
          yoffset: +kv.yoffset || 0,
          xadvance: +kv.xadvance || 0,
          page: +kv.page || 0
        };
      } else if (kind === "kerning") {
        kernings.push({ first: +kv.first, second: +kv.second, amount: +kv.amount });
      }
    });
    return { common: common, pages: pages, chars: chars, kernings: kernings };
  }

  function readFourCC(view, off) {
    return String.fromCharCode(view.getUint8(off), view.getUint8(off + 1),
      view.getUint8(off + 2), view.getUint8(off + 3));
  }

  function parseWav(bytes) {
    var buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    var view = new DataView(buf);
    if (readFourCC(view, 0) !== "RIFF" || readFourCC(view, 8) !== "WAVE") {
      throw new Error("not a RIFF/WAVE file");
    }
    var off = 12, fmt = null, dataOff = 0, dataLen = 0;
    while (off + 8 <= view.byteLength) {
      var id = readFourCC(view, off);
      var size = view.getUint32(off + 4, true);
      var start = off + 8;
      if (id === "fmt ") {
        fmt = {
          format: view.getUint16(start, true),
          channels: view.getUint16(start + 2, true),
          sampleRate: view.getUint32(start + 4, true),
          bits: view.getUint16(start + 14, true)
        };
      } else if (id === "data") {
        dataOff = start;
        dataLen = size;
      }
      off = start + size + (size % 2);
    }
    if (!fmt) throw new Error("WAV is missing a fmt chunk");
    if (fmt.format !== 1) throw new Error("only PCM WAV is supported (format " + fmt.format + ")");
    var samples, frames;
    var ch = fmt.channels, bits = fmt.bits, sr = fmt.sampleRate;
    if (bits === 8) {
      frames = Math.floor(dataLen / ch);
      samples = new Float32Array(frames * ch);
      for (var i = 0; i < frames * ch; i++) samples[i] = (view.getUint8(dataOff + i) - 128) / 128;
    } else if (bits === 16) {
      frames = Math.floor(dataLen / (2 * ch));
      samples = new Float32Array(frames * ch);
      for (var j = 0; j < frames * ch; j++) samples[j] = view.getInt16(dataOff + j * 2, true) / 32768;
    } else if (bits === 24) {
      frames = Math.floor(dataLen / (3 * ch));
      samples = new Float32Array(frames * ch);
      for (var k = 0; k < frames * ch; k++) {
        var b0 = view.getUint8(dataOff + k * 3);
        var b1 = view.getUint8(dataOff + k * 3 + 1);
        var b2 = view.getUint8(dataOff + k * 3 + 2);
        var n = (b2 << 16) | (b1 << 8) | b0;
        if (n & 0x800000) n -= 0x1000000;
        samples[k] = n / 8388608;
      }
    } else if (bits === 32) {
      frames = Math.floor(dataLen / (4 * ch));
      samples = new Float32Array(frames * ch);
      for (var m = 0; m < frames * ch; m++) samples[m] = view.getInt32(dataOff + m * 4, true) / 2147483648;
    } else {
      throw new Error("unsupported PCM bit depth: " + bits);
    }
    return { sampleRate: sr, channels: ch, bits: bits, frames: frames, samples: samples };
  }

  function gidOf(data, i) {
    var raw = data[i];
    if (raw == null) return 0;
    return (raw >>> 0) & GID_MASK;
  }

  function drawTileLayer(ctx, layer, map, image, tileset, ox, oy) {
    if (!layer || layer.type !== "tilelayer" || layer.visible === false) return;
    var tw = map.tilewidth, th = map.tileheight;
    var first = (tileset && tileset.firstgid) || 1;
    var columns = (tileset && tileset.columns) || Math.floor((image.width) / tw) || 1;
    var w = layer.width || map.width, h = layer.height || map.height;
    var data = layer.data || [];
    var alpha = layer.opacity == null ? 1 : layer.opacity;
    if (alpha !== 1) ctx.globalAlpha = alpha;
    for (var ty = 0; ty < h; ty++) {
      for (var tx = 0; tx < w; tx++) {
        var gid = gidOf(data, ty * w + tx);
        if (!gid) continue;
        var local = gid - first;
        if (local < 0) continue;
        var sx = (local % columns) * tw;
        var sy = Math.floor(local / columns) * th;
        ctx.drawImage(image, sx, sy, tw, th, (ox || 0) + tx * tw, (oy || 0) + ty * th, tw, th);
      }
    }
    if (alpha !== 1) ctx.globalAlpha = 1;
  }

  function drawAtlasFrame(ctx, image, frame, dx, dy) {
    if (!frame) return;
    var ox = (frame.spriteSourceSize && frame.spriteSourceSize.x) || 0;
    var oy = (frame.spriteSourceSize && frame.spriteSourceSize.y) || 0;
    ctx.drawImage(image, frame.x, frame.y, frame.w, frame.h, dx + ox, dy + oy, frame.w, frame.h);
  }

  function drawBMFont(ctx, font, pageImages, text, x, y) {
    var cx = x, cy = y;
    var prev = null;
    for (var i = 0; i < text.length; i++) {
      var code = text.charCodeAt(i);
      if (code === 10) { cx = x; cy += (font.common && font.common.lineHeight) || 16; prev = null; continue; }
      var ch = font.chars[code] || font.chars[32];
      if (!ch) { prev = null; continue; }
      if (prev && font.kernings && font.kernings.length) {
        for (var k = 0; k < font.kernings.length; k++) {
          if (font.kernings[k].first === prev && font.kernings[k].second === code) {
            cx += font.kernings[k].amount;
            break;
          }
        }
      }
      var img = pageImages[ch.page] || pageImages[0];
      if (img && ch.width > 0 && ch.height > 0) {
        ctx.drawImage(img, ch.x, ch.y, ch.width, ch.height,
          cx + ch.xoffset, cy + ch.yoffset, ch.width, ch.height);
      }
      cx += ch.xadvance;
      prev = code;
    }
    return cx;
  }

  function measureBMFont(font, text) {
    var w = 0, line = 0, lines = 1, prev = null;
    var lh = (font.common && font.common.lineHeight) || 16;
    for (var i = 0; i < text.length; i++) {
      var code = text.charCodeAt(i);
      if (code === 10) { if (line > w) w = line; line = 0; lines++; prev = null; continue; }
      var ch = font.chars[code] || font.chars[32];
      if (!ch) { prev = null; continue; }
      if (prev && font.kernings) {
        for (var k = 0; k < font.kernings.length; k++) {
          if (font.kernings[k].first === prev && font.kernings[k].second === code) {
            line += font.kernings[k].amount;
            break;
          }
        }
      }
      line += ch.xadvance;
      prev = code;
    }
    if (line > w) w = line;
    return { width: w, height: lines * lh };
  }

  function wavToAudioBuffer(audioCtx, wav) {
    var buf = audioCtx.createBuffer(wav.channels, wav.frames, wav.sampleRate);
    for (var c = 0; c < wav.channels; c++) {
      var ch = buf.getChannelData(c);
      for (var i = 0; i < wav.frames; i++) ch[i] = wav.samples[i * wav.channels + c];
    }
    return buf;
  }

  function playWav(audioCtx, wav) {
    var buf = wavToAudioBuffer(audioCtx, wav);
    var src = audioCtx.createBufferSource();
    src.buffer = buf;
    src.connect(audioCtx.destination);
    src.start();
    return src;
  }

  return {
    readText: readText,
    readJSON: readJSON,
    readBytes: readBytes,
    parseTiledMap: parseTiledMap,
    parseAtlas: parseAtlas,
    parseBMFont: parseBMFont,
    parseWav: parseWav,
    gidOf: gidOf,
    GID_MASK: GID_MASK,
    drawTileLayer: drawTileLayer,
    drawAtlasFrame: drawAtlasFrame,
    drawBMFont: drawBMFont,
    measureBMFont: measureBMFont,
    wavToAudioBuffer: wavToAudioBuffer,
    playWav: playWav,
    isNode: isNode,
    joinBase: joinBase
  };
});
