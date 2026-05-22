from jinja2 import Environment, BaseLoader

class TemplateRenderer:
    def __init__(self):
        self.env = Environment(
            loader=BaseLoader(),
            block_start_string='<!--%',
            block_end_string='%-->',
            variable_start_string='<!--$',
            variable_end_string='$-->',
            comment_start_string='<!--#',
            comment_end_string='#-->',
        )

    def render_string(self, source: str, context: dict) -> str:
        template = self.env.from_string(source)
        return template.render(**context)
