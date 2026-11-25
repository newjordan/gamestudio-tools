extends CharacterBody2D
## Player: run/jump with gravity, Aseprite-tagged animations (ase-to-godot) and
## per-frame hurtboxes (hitbox-gen -> hitbox-to-godot). Autoplay drives the
## same controls for the scripted test and the movie capture.

signal hurt

const SPEED := 110.0
const JUMP_V := 320.0
const GRAVITY := 900.0

var invuln := 0.0
var knock := 0.0
var facing := 1.0
@onready var spr: AnimatedSprite2D = $Sprite
@onready var hitboxes: Node2D = $Hitboxes

func _ready() -> void:
	for a in hitboxes.get_children():
		if a is Area2D:
			a.collision_layer = 0
			a.collision_mask = 16
			a.area_entered.connect(_on_hit)
	spr.frame_changed.connect(_sync_hitbox)
	spr.animation_changed.connect(_sync_hitbox)
	spr.play("idle")
	_sync_hitbox()

func _physics_process(delta: float) -> void:
	invuln = maxf(0.0, invuln - delta)
	var dir := 0.0
	var jump := false
	if Game.autoplay:
		dir = 1.0
		jump = _auto_jump()
	else:
		dir = Input.get_axis("ui_left", "ui_right")
		jump = Input.is_action_just_pressed("ui_accept") or Input.is_action_just_pressed("ui_up")
	if knock > 0.0:
		knock -= delta
	else:
		velocity.x = dir * SPEED
	if dir != 0.0:
		facing = signf(dir)
	velocity.y = minf(velocity.y + GRAVITY * delta, 500.0)
	if jump and is_on_floor():
		velocity.y = -JUMP_V
		play_sfx("Jump")
	move_and_slide()
	_animate()
	spr.modulate.a = 0.4 if invuln > 0.0 and int(invuln * 20.0) % 2 == 0 else 1.0
	if global_position.y > 240.0:
		_take_hit(Vector2.ZERO, true)

func _animate() -> void:
	var want := "idle"
	if knock > 0.0:
		want = "hurt"
	elif not is_on_floor():
		want = "jump" if velocity.y < 0.0 else "fall"
	elif absf(velocity.x) > 1.0:
		want = "run"
	if spr.animation != want:
		spr.play(want)
	spr.flip_h = facing < 0.0
	hitboxes.scale.x = -1.0 if facing < 0.0 else 1.0
	hitboxes.position.x = 8.0 if facing < 0.0 else -8.0

func _sync_hitbox() -> void:
	var tex := spr.sprite_frames.get_frame_texture(spr.animation, spr.frame)
	var key := tex.resource_path.get_file().get_basename() if tex else ""
	for a in hitboxes.get_children():
		if a is Area2D:
			var on: bool = a.name == key
			a.monitoring = on
			a.get_node("Shape").disabled = not on

func _ray(from: Vector2, to: Vector2) -> Dictionary:
	var q := PhysicsRayQueryParameters2D.create(from, to, 1)
	return get_world_2d().direct_space_state.intersect_ray(q)

func _auto_jump() -> bool:
	if not is_on_floor():
		return false
	if is_on_wall():
		return true
	var p := global_position
	if _ray(p + Vector2(12, -2), p + Vector2(12, 30)).is_empty():
		return true                                   # gap ahead
	for e in get_tree().get_nodes_in_group("enemies"):
		var d: Vector2 = e.global_position - p
		if not e.dead and d.x > 0.0 and d.x < 46.0 and absf(d.y) < 20.0:
			return true                               # hop over / onto an enemy
	return false

func _on_hit(area: Area2D) -> void:
	var enemy := area.get_parent().get_parent()
	if enemy == null or not enemy.has_method("stomp") or enemy.dead:
		return
	if velocity.y > 0.0 and global_position.y < enemy.global_position.y - 6.0:
		velocity.y = -float(enemy.bounce)
		enemy.stomp()
		play_sfx("Hit")
		return
	_take_hit(enemy.global_position, false)

func _take_hit(from: Vector2, fell: bool) -> void:
	if invuln > 0.0 and not fell:
		return
	Game.hearts -= 1
	play_sfx("Hit")
	print("SAMPLE_GAME_HURT level=%d hearts=%d fell=%s" % [Game.level, Game.hearts, fell])
	hurt.emit()
	if Game.hearts <= 0:
		set_physics_process(false)
		Game.player_died()
		return
	invuln = 1.2
	if fell:
		global_position = Vector2(40, 150)
		velocity = Vector2.ZERO
	else:
		knock = 0.35
		velocity = Vector2(-90.0 if from.x > global_position.x else 90.0, -180.0)

func play_sfx(n: String) -> void:
	var p: AudioStreamPlayer = get_node_or_null(n)
	if p:
		p.play()
