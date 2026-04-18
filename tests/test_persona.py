from jarvis.core.persona import Persona


def test_render_system_basic():
    p = Persona()
    rendered = p.render_system(profile_notes="Name: Varun", tool_summary="- web_search: ...")
    assert "sir" in rendered
    assert "Varun" in rendered
    assert "web_search" in rendered


def test_humor_levels():
    for level, keyword in [(0, "suppressed"), (1, "mild"), (2, "default"), (3, "cheeky")]:
        r = Persona(humor_level=level).render_system()
        assert keyword.lower() in r.lower()


def test_custom_address():
    p = Persona(address="boss")
    assert "'boss'" in p.render_system()
