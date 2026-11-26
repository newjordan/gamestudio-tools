extends CharacterBody2D
## Enemies with three behaviours from res://data/enemies.tres (data-to-godot of enemies.csv):
##   chase - follows a NavigationServer2D path to the player (bats)
##   shoot - keeps its distance and fires orbs when it has line of sight (wizards)
##   boss  - chase -> telegraph -> charge -> 8-way burst, repeating

const Projectile := preload("res://scripts/projectile.gd")

var kind := "bat"
var level: Node
var radius := 6.0
var hp := 2
var speed := 40.0
var damage := 1
var aggro := 120.0
var fire_cd := 2.0
var shot_speed := 80.0
var behaviour := "chase"
var drop := "common"
var anim := "bat-fly"
var sprite: AnimatedSprite2D
var _fire := 1.0
var _path := PackedVector2Array()
var _path_t := 0.0
var _flash := 0.0
var _knock := Vector2.ZERO
var _state := "chase"
var _state_t := 2.0
var _charge_dir := Vector2.ZERO
var _awake := false


func _ready() -> void:
	add_to_group("enemies")
	var row: Dictionary = Game.stats[kind]
	hp = int(row["hp"])
	speed = float(row["speed"])
	damage = int(row["damage"])
	aggro = float(row["aggro"])
	fire_cd = float(row["fire_cd"]) if str(row["fire_cd"]) != "" else 0.0
	shot_speed = float(row["shot_speed"]) if str(row["shot_speed"]) != "" else 0.0
	behaviour = String(row["behaviour"])
	drop = String(row["drop"])
	anim = String(row["anim"])
	collision_layer = 4
	collision_mask = 1
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	radius = 13.0 if behaviour == "boss" else 6.0
	var shape := CircleShape2D.new()
	shape.radius = radius - 1.0
	var cs := CollisionShape2D.new()
	cs.shape = shape
	add_child(cs)
	sprite = AnimatedSprite2D.new()
	sprite.sprite_frames = load("res://art/actors_frames.tres")
	sprite.play(_clip("idle"))
	add_child(sprite)
	_fire = fire_cd * (0.5 + Game.rng.randf() * 0.5)


func _clip(state: String) -> String:
	var c := anim
	if behaviour == "shoot":
		c = anim + ("-cast" if state == "cast" else "-idle")
	elif behaviour == "boss":
		c = anim + ("-charge" if state in ["telegraph", "charge"] else "-walk")
	return c if sprite.sprite_frames.has_animation(c) else sprite.sprite_frames.get_animation_names()[0]


func _player() -> Node2D:
	return level.player if level and is_instance_valid(level.player) else null


func _los(to: Vector2) -> bool:
	var q := PhysicsRayQueryParameters2D.create(global_position, to, 1)
	return get_world_2d().direct_space_state.intersect_ray(q).is_empty()


func _physics_process(delta: float) -> void:
	var p := _player()
	if p == null:
		return
	var to_p := p.global_position - global_position
	var dist := to_p.length()
	if not _awake:
		_awake = dist < aggro and _los(p.global_position)
		_bob(delta)
		return
	var v := Vector2.ZERO
	match behaviour:
		"chase":
			v = _follow(p.global_position, delta) * speed
		"shoot":
			v = _shoot(p, to_p, dist, delta)
		"boss":
			v = _boss(p, to_p, delta)
	velocity = v + _knock
	_knock = _knock.move_toward(Vector2.ZERO, 500.0 * delta)
	move_and_slide()
	sprite.flip_h = to_p.x < 0.0
	_flash -= delta
	sprite.modulate = Color(3, 3, 3) if _flash > 0.0 else Color.WHITE
	if dist < radius + p.hurt_radius:
		p.take_damage(damage, global_position)


func _bob(delta: float) -> void:
	sprite.position.y = sin(Game.elapsed() * 4.0 + position.x) * 1.5
	_flash -= delta


func _follow(target: Vector2, delta: float) -> Vector2:
	_path_t -= delta
	if _path_t <= 0.0 or _path.is_empty():
		_path = level.path_to(global_position, target)
		_path_t = 0.4
	while _path.size() > 1 and _path[0].distance_to(global_position) < 4.0:
		_path.remove_at(0)
	var aim := target if _path.size() < 2 else _path[0]
	return (aim - global_position).normalized()


func _shoot(p: Node2D, to_p: Vector2, dist: float, delta: float) -> Vector2:
	_fire -= delta
	var see := _los(p.global_position)
	if _fire <= 0.0 and see and dist < aggro:
		_fire = fire_cd
		sprite.play(_clip("cast"))
		_spawn_orb(to_p.normalized())
		get_tree().create_timer(0.3).timeout.connect(func(): if is_instance_valid(self): sprite.play(_clip("idle")))
	if dist < 44.0:
		return -to_p.normalized() * speed
	if dist > 90.0 or not see:
		return _follow(p.global_position, delta) * speed
	return Vector2.ZERO


func _boss(p: Node2D, to_p: Vector2, delta: float) -> Vector2:
	_state_t -= delta
	match _state:
		"chase":
			if _state_t <= 0.0:
				_set_state("telegraph", 0.55)
				Game.play("roar")
			return _follow(p.global_position, delta) * speed
		"telegraph":
			sprite.position = Vector2(sin(Game.elapsed() * 60.0), 0.0)
			if _state_t <= 0.0:
				sprite.position = Vector2.ZERO
				_charge_dir = to_p.normalized()
				_set_state("charge", 0.5)
			return Vector2.ZERO
		"charge":
			if _state_t <= 0.0 or get_slide_collision_count() > 0:
				_set_state("burst", 0.35)
				for i in 8:
					_spawn_orb(Vector2.RIGHT.rotated(TAU * i / 8.0 + Game.rng.randf() * 0.2))
			return _charge_dir * speed * 3.6
		"burst":
			if _state_t <= 0.0:
				_set_state("chase", fire_cd)
	return Vector2.ZERO


func _set_state(s: String, t: float) -> void:
	_state = s
	_state_t = t
	sprite.play(_clip(s))


func _spawn_orb(dir: Vector2) -> void:
	var o := Projectile.new()
	o.position = global_position + dir * (radius + 2.0)
	o.velocity = dir * shot_speed
	o.damage = damage
	level.add_child(o)
	Game.play("shoot", 1.2 if behaviour == "boss" else 1.0)


func take_hit(n: int, dir: Vector2) -> void:
	hp -= n
	_awake = true
	_flash = 0.1
	_knock = dir * (40.0 if behaviour == "boss" else 160.0)
	Game.play("hit_%d" % Game.rng.randi_range(0, 2))
	if hp <= 0:
		_die()


func _die() -> void:
	Game.play("death")
	var drops: Dictionary = Game.roll_drop(drop)
	var i := 0
	for item in drops:
		for n in mini(int(drops[item]), 4):
			level.spawn_pickup(item, global_position + Vector2(8, 0).rotated(i * 1.7) * (1.0 if i else 0.0))
			i += 1
	print("KILL %s drops=%s" % [kind, drops])
	if behaviour == "boss":
		print("BOSS_DEAD t=%.1f" % Game.run_time)
		level.boss_dead()
	remove_from_group("enemies")
	queue_free()
