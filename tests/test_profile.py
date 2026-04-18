import pytest

from jarvis.core.profile import UserProfile, UserProfileStore


def test_render_notes_empty():
    p = UserProfile()
    notes = p.render_notes()
    assert "Preferred address: sir" in notes


def test_render_notes_with_jokes_and_notes():
    p = UserProfile(name="Varun")
    p.inside_jokes.append("Always picks the red pill")
    p.notes.append({"ts": 1, "tag": "x", "text": "prefers morning stand-ups"})
    text = p.render_notes()
    assert "Varun" in text
    assert "red pill" in text
    assert "morning stand-ups" in text


@pytest.mark.asyncio
async def test_store_update_and_note(tmp_path):
    store = UserProfileStore(tmp_path / "profile.json")
    p = await store.update(name="V", humor_level=3)
    assert p.name == "V"
    assert p.humor_level == 3

    await store.add_note("likes tight PRs")
    await store.add_inside_joke("boil the ocean")

    p2 = await UserProfileStore(tmp_path / "profile.json").load()
    assert "boil the ocean" in p2.inside_jokes
    assert any("tight PRs" in n["text"] for n in p2.notes)


@pytest.mark.asyncio
async def test_store_always_approved(tmp_path):
    store = UserProfileStore(tmp_path / "profile.json")
    await store.add_always_approved("fp1")
    await store.add_always_approved("fp1")  # dedupe
    p = await store.load()
    assert p.always_approved.count("fp1") == 1
