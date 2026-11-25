/* Tiny top-down room: load a Tiled map, atlas, BMFont and WAV via GSTLoader. */
(function () {
  "use strict";
  var L = window.GSTLoader;
  if (!L) throw new Error("GSTLoader is not loaded");

  var W = 320, H = 180, TILE = 16, HUD = 20;
  var SPEED = 120;
  var DT = 1 / 30;
  var WALK = ["walk_01", "walk_02", "walk_03", "walk_02"];

  var canvas = document.getElementById("game");
  var ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;

  var keys = Object.create(null);
  window.addEventListener("keydown", function (e) {
    keys[e.key] = true;
    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", " "].indexOf(e.key) >= 0) e.preventDefault();
  });
  window.addEventListener("keyup", function (e) { keys[e.key] = false; });

  function loadImage(src) {
    return new Promise(function (resolve, reject) {
      var img = new Image();
      img.onload = function () { resolve(img); };
      img.onerror = function () { reject(new Error("failed to load image " + src)); };
      img.src = src;
    });
  }

  function findObject(map, names) {
    var want = names.split(",").map(function (s) { return s.trim().toLowerCase(); });
    for (var i = 0; i < map.layers.length; i++) {
      var l = map.layers[i];
      if (l.type !== "objectgroup" || !l.objects) continue;
      for (var j = 0; j < l.objects.length; j++) {
        var o = l.objects[j];
        var n = (o.name || "").toLowerCase();
        var t = (o.type || "").toLowerCase();
        if (want.indexOf(n) >= 0 || want.indexOf(t) >= 0) return o;
      }
    }
    return null;
  }

  function isSolid(map, walls, px, py) {
    var tx = Math.floor(px / map.tilewidth);
    var ty = Math.floor(py / map.tileheight);
    if (tx < 0 || ty < 0 || tx >= map.width || ty >= map.height) return true;
    return L.gidOf(walls.data, ty * map.width + tx) !== 0;
  }

  function blocked(map, walls, x, y, hw, hh) {
    // 12x12 hitbox inset from a 16x16 sprite
    return isSolid(map, walls, x + 2, y + 4) ||
      isSolid(map, walls, x + hw - 3, y + 4) ||
      isSolid(map, walls, x + 2, y + hh - 2) ||
      isSolid(map, walls, x + hw - 3, y + hh - 2);
  }

  function overlaps(ax, ay, aw, ah, o) {
    return ax < o.x + o.width && ax + aw > o.x && ay < o.y + o.height && ay + ah > o.y;
  }

  function params() {
    return new URLSearchParams(window.location.search);
  }

  function hideChrome() {
    document.body.classList.add("preview");
    var help = document.getElementById("help");
    if (help) help.style.display = "none";
    var wrap = document.getElementById("wrap");
    if (wrap) wrap.style.padding = "0";
  }

  function boot(assets) {
    var map = assets.map, atlas = assets.atlas, font = assets.font;
    var tilesImg = assets.tilesImg, playerImg = assets.playerImg, fontImg = assets.fontImg;
    var wav = assets.wav;
    var ground = map.layers.filter(function (l) { return l.type === "tilelayer" && l.name === "ground"; })[0];
    var walls = map.layers.filter(function (l) { return l.type === "tilelayer" && l.name === "walls"; })[0];
    var tileset = map.tilesets[0];
    var spawn = findObject(map, "spawn,start,player_start");
    var coin = findObject(map, "coin");
    if (!spawn) throw new Error("map is missing a spawn object");

    var state = {
      x: spawn.x,
      y: spawn.y,
      vx: 0,
      vy: 0,
      coins: 0,
      coinTaken: false,
      facing: 1,
      moving: false,
      time: 0,
      frames: 0
    };

    var audioCtx = null;
    function ensureAudio() {
      if (audioCtx || typeof AudioContext === "undefined" && typeof webkitAudioContext === "undefined") return audioCtx;
      var Ctor = window.AudioContext || window.webkitAudioContext;
      try { audioCtx = new Ctor(); } catch (e) { audioCtx = null; }
      return audioCtx;
    }

    function playCoin() {
      var ctxA = ensureAudio();
      if (ctxA && wav) {
        try { L.playWav(ctxA, wav); } catch (e) { /* autoplay / missing audio is fine */ }
      }
    }

    function autoInput() {
      if (state.coinTaken) { keys.ArrowRight = keys.ArrowLeft = keys.ArrowUp = keys.ArrowDown = false; return; }
      var tx = coin ? coin.x : state.x;
      var ty = coin ? coin.y : state.y;
      var dx = tx - state.x, dy = ty - state.y;
      keys.ArrowRight = dx > 1;
      keys.ArrowLeft = dx < -1;
      keys.ArrowDown = dy > 1;
      keys.ArrowUp = dy < -1;
    }

    function inputVector() {
      var ix = 0, iy = 0;
      if (keys.ArrowLeft || keys.a || keys.A) ix -= 1;
      if (keys.ArrowRight || keys.d || keys.D) ix += 1;
      if (keys.ArrowUp || keys.w || keys.W) iy -= 1;
      if (keys.ArrowDown || keys.s || keys.S) iy += 1;
      if (ix && iy) { ix *= Math.SQRT1_2; iy *= Math.SQRT1_2; }
      return { x: ix, y: iy };
    }

    function tick() {
      var iv = inputVector();
      state.vx = iv.x * SPEED;
      state.vy = iv.y * SPEED;
      state.moving = !!(iv.x || iv.y);
      if (iv.x) state.facing = iv.x < 0 ? -1 : 1;
      var nx = state.x + state.vx * DT;
      var ny = state.y + state.vy * DT;
      if (!blocked(map, walls, nx, state.y, TILE, TILE)) state.x = nx;
      if (!blocked(map, walls, state.x, ny, TILE, TILE)) state.y = ny;
      if (!state.coinTaken && coin && overlaps(state.x + 2, state.y + 2, 12, 12, coin)) {
        state.coinTaken = true;
        state.coins = 1;
        playCoin();
      }
      state.time += DT;
      state.frames += 1;
    }

    function walkFrame() {
      if (!state.moving) return atlas.frames.walk_01;
      var i = Math.floor(state.time * 8) % WALK.length;
      return atlas.frames[WALK[i]] || atlas.frames.walk_01;
    }

    function render() {
      ctx.fillStyle = "#1a1a2e";
      ctx.fillRect(0, 0, W, H);
      var ox = 0, oy = HUD;
      if (ground) L.drawTileLayer(ctx, ground, map, tilesImg, tileset, ox, oy);
      if (walls) L.drawTileLayer(ctx, walls, map, tilesImg, tileset, ox, oy);
      if (!state.coinTaken && coin && atlas.frames.coin) {
        L.drawAtlasFrame(ctx, playerImg, atlas.frames.coin, ox + coin.x, oy + coin.y);
      }
      var fr = walkFrame();
      ctx.save();
      if (state.facing < 0) {
        ctx.translate(ox + state.x + TILE, oy + state.y);
        ctx.scale(-1, 1);
        L.drawAtlasFrame(ctx, playerImg, fr, 0, 0);
      } else {
        L.drawAtlasFrame(ctx, playerImg, fr, ox + state.x, oy + state.y);
      }
      ctx.restore();
      ctx.fillStyle = "#0e1116";
      ctx.fillRect(0, 0, W, HUD);
      L.drawBMFont(ctx, font, [fontImg], "COINS " + state.coins, 6, 2);
    }

    function markOk() {
      window.__GST_WEB_OK = {
        frame: true,
        frames: state.frames,
        map: { width: map.width, height: map.height },
        atlas: { names: atlas.names },
        font: { chars: Object.keys(font.chars).length },
        wav: { sampleRate: wav.sampleRate, frames: wav.frames },
        coins: state.coins,
        pos: { x: Math.round(state.x * 10) / 10, y: Math.round(state.y * 10) / 10 }
      };
    }

    var q = params();
    var preview = q.has("preview") || q.has("step") || q.has("t");
    if (preview) hideChrome();
    if (q.has("muted")) audioCtx = "off";

    var stepN = q.get("step");
    if (stepN != null && stepN !== "") {
      var n = parseInt(stepN, 10) || 0;
      for (var i = 0; i < n; i++) {
        if (preview) autoInput();
        tick();
      }
      render();
      markOk();
      return;
    }

    render();
    markOk();
    var acc = 0, last = performance.now();
    function loop(now) {
      var dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      acc += dt;
      if (preview) autoInput();
      while (acc >= DT) { tick(); acc -= DT; }
      render();
      markOk();
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
  }

  Promise.all([
    L.readJSON("art/level.json").then(L.parseTiledMap),
    L.readJSON("art/player.json").then(L.parseAtlas),
    L.readText("font/label.fnt").then(L.parseBMFont),
    L.readBytes("sfx/coin.wav").then(L.parseWav),
    loadImage("art/tiles.png"),
    loadImage("art/player.png"),
    loadImage("font/label.png")
  ]).then(function (parts) {
    boot({
      map: parts[0], atlas: parts[1], font: parts[2], wav: parts[3],
      tilesImg: parts[4], playerImg: parts[5], fontImg: parts[6]
    });
  }).catch(function (err) {
    window.__GST_WEB_OK = { frame: false, error: String(err && err.message ? err.message : err) };
    ctx.fillStyle = "#1a1a2e";
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "#e88";
    ctx.font = "10px monospace";
    ctx.fillText(String(err && err.message ? err.message : err), 8, 24);
    throw err;
  });
})();
