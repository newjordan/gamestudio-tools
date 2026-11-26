extends Node2D
## Assembles one generated floor from the gst-made scenes in res://levels and spawns actors
## at the Tiled objects (map-objects-to-godot markers carry tiled_type/kind metadata).

const Player := preload("res://scripts/player.gd")
const Enemy := preload("res://scripts/enemy.gd")
const Pickup := preload("res://scripts/pickup.gd")
const Hud := preload("res://scripts/hud.gd")

var player: CharacterBody2D
var hud: CanvasLayer
var stairs: Sprite2D
var portal: Sprite2D
var portal_open := false
var nav_map: RID
var map_rect := Rect2()
var enemies_total := 0
var _locked_toast := false
var _done := false


func _ready() -> void:
	name = "Level"
	var lv: String = Game.level_name()
	var tiles: Node = load("res://levels/%s_tiles.tscn" % lv).instantiate()
	add_child(tiles)
	add_child(load("res://levels/%s_solid.tscn" % lv).instantiate())
	var nav: Node = load("res://levels/%s_nav.tscn" % lv).instantiate()
	add_child(nav)
	var objs: Node = load("res://levels/%s_objects.tscn" % lv).instantiate()
	add_child(objs)
	nav_map = get_world_2d().navigation_map
	for c in tiles.get_children():
		if c is TileMapLayer:
			var r: Rect2i = c.get_used_rect()
			map_rect = map_rect.merge(Rect2(r.position * 16, r.size * 16)) if map_rect.has_area() else Rect2(r.position * 16, r.size * 16)
	hud = Hud.new()
	add_child(hud)
	var spawn := Vector2(32, 32)
	var counts := {}
	for o in _all(objs):
		var typ := String(o.get_meta("tiled_type", ""))
		if o is Sprite2D:
			if typ == "stairs" or o.name.begins_with("stairs"):
				stairs = o
			continue
		match typ:
			"spawn":
				spawn = o.global_position
			"enemy":
				_spawn_enemy(String(o.get_meta("kind")), o.global_position)
			"key", "coin", "heart":
				spawn_pickup(typ, o.global_position)
			"portal":
				_make_portal(o.global_position)
		counts[typ] = counts.get(typ, 0) + 1
	player = Player.new()
	player.position = spawn
	player.level = self
	add_child(player)
	var cam := Camera2D.new()
	cam.limit_left = int(map_rect.position.x)
	cam.limit_top = int(map_rect.position.y) - 24
	cam.limit_right = int(map_rect.end.x)
	cam.limit_bottom = int(map_rect.end.y)
	cam.position_smoothing_enabled = true
	cam.position_smoothing_speed = 8.0
	player.add_child(cam)
	cam.make_current()
	hud.refresh()
	hud.toast(tr("hud_boss") if lv == "boss" else tr("hud_floor").format({"n": Game.floor}))
	print("LEVEL %s floor=%d size=%dx%d enemies=%d objects=%s stairs=%s" % [lv, Game.floor,
		int(map_rect.size.x), int(map_rect.size.y), enemies_total, counts, stairs != null])
	for i in 4:
		await get_tree().physics_frame
	var probe := NavigationServer2D.map_get_path(nav_map, spawn, stairs_center() if stairs else spawn + Vector2(0, -160), true)
	print("NAV_OK points=%d to=%s" % [probe.size(), stairs_center() if stairs else Vector2.ZERO])


func stairs_center() -> Vector2:
	return stairs.to_global(stairs.get_rect().get_center())


func _all(n: Node) -> Array:
	var out := []
	for c in n.get_children():
		out.append(c)
		out.append_array(_all(c))
	return out


func _spawn_enemy(kind: String, pos: Vector2) -> void:
	var e := Enemy.new()
	e.kind = kind
	e.level = self
	e.position = pos
	add_child(e)
	enemies_total += 1


func spawn_pickup(kind: String, pos: Vector2) -> void:
	var p := Pickup.new()
	p.kind = kind
	p.position = pos
	call_deferred("add_child", p)


func _make_portal(pos: Vector2) -> void:
	portal = Sprite2D.new()
	portal.texture = load("res://art/portal.png")
	portal.position = pos
	portal.visible = false
	add_child(portal)


func boss_dead() -> void:
	if portal:
		portal.visible = true
		portal_open = true
		hud.toast(tr("hud_portal"))


func path_to(from: Vector2, to: Vector2) -> PackedVector2Array:
	## The navmesh is the walkable tiles, so path corners sit on wall corners; move each
	## interior corner to the centre of a walkable neighbouring tile so bodies don't snag.
	var raw := NavigationServer2D.map_get_path(nav_map, from, to, true)
	for i in range(1, raw.size() - 1):
		var p := raw[i]
		var walls := Vector2.ZERO
		for off in [Vector2(-8, -8), Vector2(8, -8), Vector2(-8, 8), Vector2(8, 8)]:
			var c: Vector2 = p + off
			if NavigationServer2D.map_get_closest_point(nav_map, c).distance_to(c) > 0.5:
				walls += off
		var q := p - walls.sign() * 6.0
		if walls != Vector2.ZERO and NavigationServer2D.map_get_closest_point(nav_map, q).distance_to(q) < 0.5:
			raw[i] = q
	return raw


func goal() -> Vector2:
	## Where the run goes next once the room is safe: key (if any), stairs, or the open portal.
	if portal:
		return portal.global_position if portal_open else Vector2.INF
	if stairs:
		return stairs_center()
	return Vector2.INF


func _physics_process(_d: float) -> void:
	if _done or player == null:
		return
	if stairs:
		var near := player.global_position.distance_to(stairs_center()) < 10.0
		if near and Game.has_key:
			_leave()
		elif near and not _locked_toast:
			_locked_toast = true
			hud.toast(tr("hud_locked"))
			Game.play("blip")
		elif not near:
			_locked_toast = false
	if portal_open and player.global_position.distance_to(portal.global_position) < 10.0:
		_leave()


func _leave() -> void:
	_done = true
	Game.play("stairs")
	print("FLOOR_CLEAR floor=%d hp=%d coins=%d t=%.1f" % [Game.floor, Game.hp, Game.coins, Game.run_time])
	Game.call_deferred("floor_cleared")

