extends Control

func _ready() -> void:
	$Panel/VBox/Win.text = tr("WIN")
	$Panel/VBox/Thanks.text = tr("THANKS")
	$Panel/VBox/Gems.text = "%s: %d / %d" % [tr("GEMS"), Game.gems, Game.LEVELS]
	if Game.autoplay:
		await get_tree().create_timer(2.5).timeout
		print("SAMPLE_GAME_DONE")
		OS.delay_msec(250)   # let the audio thread release finished playbacks (fast --fixed-fps runs)
		get_tree().quit(0)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode in [KEY_ENTER, KEY_SPACE]:
		get_tree().change_scene_to_file("res://scenes/title.tscn")
