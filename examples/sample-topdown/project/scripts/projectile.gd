extends Node2D
## Enemy orb: straight line, dies on walls (physics layer 1 point query) or on the player.

var velocity := Vector2.ZERO
var damage := 1
var _life := 3.0
var _spr: AnimatedSprite2D


func _ready() -> void:
	_spr = AnimatedSprite2D.new()
	_spr.sprite_frames = load("res://art/actors_frames.tres")
	_spr.play("orb-spin")
	add_child(_spr)


func _physics_process(delta: float) -> void:
	position += velocity * delta
	_life -= delta
	var q := PhysicsPointQueryParameters2D.new()
	q.position = global_position
	q.collision_mask = 1
	if _life <= 0.0 or not get_world_2d().direct_space_state.intersect_point(q, 1).is_empty():
		queue_free()
		return
	for p in get_tree().get_nodes_in_group("player"):
		if p.global_position.distance_to(global_position) < p.hurt_radius + 2.0:
			p.take_damage(damage, global_position - velocity)
			queue_free()
