import pytest
from harness.minting_engine import TemplateRenderer

def test_template_renderer():
    renderer = TemplateRenderer()
    template = "## Agent\n<!--% if active %-->Hello <!--$ name $--><!--% endif %-->"
    context = {"active": True, "name": "World"}
    result = renderer.render_string(template, context)
    assert result == "## Agent\nHello World"
