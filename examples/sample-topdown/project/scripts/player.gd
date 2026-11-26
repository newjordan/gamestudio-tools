extends CharacterBody2D
## Player: keyboard/gamepad movement through the input map, 8-way slash, i-frames.
## In --autoplay the same actions are driven with Input.action_press by a small AI.

const SPEED := 72.0
const ATTACK_CD := 0.3
const REACH := 13.0

var level: Node
var facing := Vector2.DOWN
var sprite: AnimatedSprite2D
var slash: AnimatedSprite2D
var hurt_radius := 5.0
var _cd := 0.0
var _iframes := 0.0
var _slash_t := 0.0
var _knock := Vector2.ZERO
# autoplay state
var _path := PackedVector2Array()
var _path_t := 0.0
var _path_goal := Vector2.INF
var _last_pos := Vector2.ZERO
var _stuck_t := 0.0
var _unstick := 0.0
var _unstick_dir := Vector2.ZERO
var _pressed := {}
var _dbg_t := 0.0
var _face := Vector2.ZERO
var _lock: Node2D = null


func _ready() -> void:
	add_to_group("player")
	collision_layer = 2
	collision_mask = 1
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	var shape := CircleShape2D.new()
	shape.radius = 4.0
	var cs := CollisionShape2D.new()
	cs.shape = shape
	cs.position = Vector2(0, 3)
	add_child(cs)
	sprite = AnimatedSprite2D.new()
	sprite.sprite_frames = load("res://art/actors_frames.tres")
	sprite.play("player-idle-down")
	add_child(sprite)
	slash = AnimatedSprite2D.new()
	slash.sprite_frames = load("res://art/slash_frames.tres")
	slash.visible = false
	slash.z_index = 2
	add_child(slash)
	# hurt radius from the gst hitbox (hitbox-gen -> hitbox-to-godot) for the first walk frame
	var hb: Node = load("res://art/actors_hitboxes.tscn").instantiate()
	var area := hb.get_node_or_null("player-walk-down_0")
	if area:
		var r: RectangleShape2D = area.get_node("Shape").shape
		hurt_radius = minf(r.size.x, r.size.y) * 0.5
	hb.free()


func _physics_process(delta: float) -> void:
	if Game.autoplay:
		_autopilot(delta)
	var dir := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	if _face != Vector2.ZERO:
		facing = _face  # autoplay aims the swing at its target
		_face = Vector2.ZERO
	elif dir.length() > 0.1:
		facing = dir.normalized()
	velocity = dir * SPEED + _knock
	_knock = _knock.move_toward(Vector2.ZERO, 600.0 * delta)
	move_and_slide()
	_cd -= delta
	_iframes -= delta
	if Input.is_action_just_pressed("attack") and _cd <= 0.0:
		_attack()
	_slash_t -= delta
	slash.visible = _slash_t > 0.0
	sprite.modulate = Color(1, 1, 1, 0.4 if _iframes > 0.0 and int(_iframes * 20.0) % 2 == 0 else 1.0)
	_animate(dir)


func _animate(dir: Vector2) -> void:
	var side := "side" if absf(facing.x) > absf(facing.y) else ("down" if facing.y >= 0.0 else "up")
	sprite.flip_h = side == "side" and facing.x < 0.0
	var clip := ("player-walk-" if dir.length() > 0.1 else "player-idle-") + side
	if sprite.animation != clip:
		sprite.play(clip)


func _attack() -> void:
	_cd = ATTACK_CD
	_slash_t = 0.16
	# slash_000 points up and the 8 angles go clockwise (gst sprite-angles)
	var idx := int(round(fposmod(atan2(facing.x, -facing.y), TAU) / (TAU / 8.0))) % 8
	slash.animation = "slash_%03d" % idx
	slash.position = facing * 10.0
	slash.play()
	Game.play("swing", 0.9 + Game.rng.randf() * 0.2)
	if OS.has_environment("TD_DEBUG"):
		print("SWING facing=%s n=%d" % [facing, get_tree().get_nodes_in_group("enemies").size()])
	var hit_at := global_position + facing * REACH
	for e in get_tree().get_nodes_in_group("enemies"):
		if e.global_position.distance_to(hit_at) < e.radius + 9.0:
			e.take_hit(1, facing)


func take_damage(amount: int, from: Vector2) -> void:
	if _iframes > 0.0 or Game.hp <= 0:
		return
	Game.hp -= amount
	_iframes = 0.9
	_knock = (global_position - from).normalized() * 140.0
	Game.play("hurt")
	print("HURT hp=%d" % Game.hp)
	level.hud.refresh()
	if Game.hp <= 0:
		Game.call_deferred("player_died")


func heal(n: int) -> void:
	Game.hp = mini(Game.hp + n, Game.max_hp)


# --- autoplay -----------------------------------------------------------------------------

func _press(action: String, strength := 1.0) -> void:
	if strength > 0.05:
		Input.action_press(action, clampf(strength, 0.0, 1.0))
		_pressed[action] = true
	elif _pressed.get(action, false):
		Input.action_release(action)
		_pressed[action] = false


func _steer(v: Vector2) -> void:
	var d := v.normalized() if v.length() > 0.01 else Vector2.ZERO
	_press("move_right", d.x)
	_press("move_left", -d.x)
	_press("move_down", d.y)
	_press("move_up", -d.y)


func _path_len(to: Vector2) -> float:
	var pts: PackedVector2Array = level.path_to(global_position, to)
	var d := 0.0
	var prev := global_position
	for q in pts:
		d += prev.distance_to(q)
		prev = q
	return d if pts.size() > 0 else INF


func _target() -> Dictionary:
	## Fight enemies that are close by walking distance (boss always), then loose pickups,
	## then the key, then the stairs/portal. A locked enemy is kept until it is far away.
	if is_instance_valid(_lock) and _lock.is_in_group("enemies") and \
			(_lock.kind == "boss" or _path_len(_lock.global_position) < 220.0):
		return {"node": _lock, "pos": _lock.global_position, "enemy": true}
	_lock = null
	var best: Node2D = null
	var bd := 140.0
	for e in get_tree().get_nodes_in_group("enemies"):
		if e.global_position.distance_to(global_position) > 160.0 and e.kind != "boss":
			continue
		var d := 0.0 if e.kind == "boss" else _path_len(e.global_position)
		if d < bd:
			bd = d
			best = e
	if best:
		_lock = best
		return {"node": best, "pos": best.global_position, "enemy": true}
	var pk: Node2D = null
	bd = 1e9
	for p in get_tree().get_nodes_in_group("pickups"):
		var d: float = p.global_position.distance_to(global_position)
		if p.kind == "heart" and Game.hp >= Game.max_hp:
			continue
		if d < bd:
			bd = d
			pk = p
	if pk and (pk.kind == "key" or bd < 200.0):
		return {"node": pk, "pos": pk.global_position, "enemy": false}
	var keys := get_tree().get_nodes_in_group("pickups").filter(func(p): return p.kind == "key")
	if not keys.is_empty():
		return {"node": keys[0], "pos": keys[0].global_position, "enemy": false}
	return {"node": null, "pos": level.goal(), "enemy": false}


func _autopilot(delta: float) -> void:
	# tap the attack button: press one physics frame, release the next
	var tapped := Input.is_action_pressed("attack")
	if tapped:
		Input.action_release("attack")
	var t := _target()
	var goal: Vector2 = t["pos"]
	_dbg_t -= delta
	if _dbg_t <= 0.0 and OS.has_environment("TD_DEBUG"):
		_dbg_t = 1.0
		print("AP pos=%s goal=%s enemy=%s path=%s hp=%d v=%s unstick=%.2f" % [global_position.round(), goal.round() if goal != Vector2.INF else goal, t["enemy"], _path, Game.hp, velocity.round(), _unstick])
	if goal == Vector2.INF:
		_steer(Vector2.ZERO)
		return
	var to_goal := goal - global_position
	if t["enemy"]:
		var e: Node2D = t["node"]
		if to_goal.length() < e.radius + REACH + 3.0:
			_steer(Vector2.ZERO)
			_face = to_goal.normalized()
			if _cd <= 0.0 and not tapped:
				Input.action_press("attack")
			return
	_path_t -= delta
	if _path_t <= 0.0 or _path_goal.distance_to(goal) > 12.0 or _path.is_empty():
		_path = level.path_to(global_position, goal)
		_path_goal = goal
		_path_t = 0.35
	while _path.size() > 1 and _path[0].distance_to(global_position) < 4.0:
		_path.remove_at(0)
	var aim := goal if _path.is_empty() else _path[0]
	# stuck on a corner: sidestep perpendicular for a moment
	_stuck_t = _stuck_t + delta if global_position.distance_to(_last_pos) < 0.3 else 0.0
	_last_pos = global_position
	if _stuck_t > 0.4:
		_stuck_t = 0.0
		_unstick = 0.25
		var a := (aim - global_position).normalized()
		_unstick_dir = Vector2(-a.y, a.x) * (1.0 if Game.rng.randf() < 0.5 else -1.0)
	if _unstick > 0.0:
		_unstick -= delta
		_steer(_unstick_dir)
		return
	_steer(aim - global_position)
