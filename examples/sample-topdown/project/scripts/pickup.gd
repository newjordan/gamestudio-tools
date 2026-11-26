extends Node2D
## Coin / heart / key pickup (pickups atlas from atlas-pack + atlas-to-godot).

var kind := "coin"
var _t := 0.0
var _spr: AnimatedSprite2D


func _ready() -> void:
	add_to_group("pickups")
	_spr = AnimatedSprite2D.new()
	_spr.sprite_frames = load("res://art/pickups_frames.tres")
	_spr.play({"coin": "coin-spin", "heart": "heart-idle", "key": "key-idle"}[kind])
	add_child(_spr)


func _physics_process(delta: float) -> void:
	_t += delta
	_spr.position.y = sin(_t * 5.0) * 1.0
	if _t < 0.25:
		return
	for p in get_tree().get_nodes_in_group("player"):
		if p.global_position.distance_to(global_position) < 10.0:
			_collect(p)


func _collect(p: Node) -> void:
	match kind:
		"coin":
			Game.coins += 1
			Game.play("coin")
		"heart":
			p.heal(2)
			Game.play("pickup")
		"key":
			Game.has_key = true
			Game.play("pickup")
			p.level.hud.toast(tr("hud_key"))
	print("PICKUP %s coins=%d hp=%d" % [kind, Game.coins, Game.hp])
	p.level.hud.refresh()
	remove_from_group("pickups")
	queue_free()
