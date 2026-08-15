"""Foundation tests for the distributable service package."""

from weather_story_bot.handler import publisher_handler


def test_publisher_handler_is_importable() -> None:
    assert callable(publisher_handler)
