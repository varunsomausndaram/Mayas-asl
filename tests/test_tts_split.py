from jarvis.voice.tts import split_for_speech


def test_split_plain():
    chunks = split_for_speech("Hello. World! How are you?")
    assert chunks == ["Hello.", "World!", "How are you?"]


def test_split_strips_markdown():
    text = "Here is `code` and **bold** and a [link](http://x). Another line."
    chunks = split_for_speech(text)
    joined = " ".join(chunks)
    assert "code" in joined
    assert "bold" in joined
    assert "link" in joined
    assert "[" not in joined
    assert "**" not in joined


def test_split_removes_code_blocks():
    chunks = split_for_speech("Before.\n```\nx = 1\n```\nAfter.")
    joined = " ".join(chunks)
    assert "Before" in joined
    assert "After" in joined
    assert "x = 1" not in joined


def test_long_sentence_capped():
    text = "word " * 200
    chunks = split_for_speech(text)
    assert all(len(c) <= 240 for c in chunks)
