---
title: Templates with Jinja
summary: Build HTML pages with Jinja2: variables, loops, conditions, inheritance and automatic escaping.
takeaways:
- Jinja puts Python-like logic inside HTML: {{ }} prints, {% %} controls
- Template inheritance gives every page the same layout
- Jinja escapes values by default, which prevents most XSS
---
## Why templates

Building HTML with string concatenation gets messy fast. A **template** is an HTML file with placeholders. Flask uses **Jinja2**.

By default, templates live in a folder called `templates/` next to your app:

```py
myapp/
  app.py
  templates/
    base.html
    index.html
```

and you render one with `render_template("index.html", title="Home")`. The examples here use `render_template_string` (same engine, but the template is written inline) so you can run them anywhere.

## Printing and logic

```python
from flask import Flask, render_template_string

app = Flask(__name__)

PAGE = """
<h1>{{ title }}</h1>
<ul>
{% for course in courses %}
  <li>{{ loop.index }}. {{ course.name|upper }}{% if course.free %} (free){% endif %}</li>
{% else %}
  <li>No courses yet</li>
{% endfor %}
</ul>
<p>Total: {{ courses|length }}</p>
"""

@app.route("/")
def home():
    courses = [{"name": "python", "free": True}, {"name": "sql", "free": False}]
    return render_template_string(PAGE, title="Courses", courses=courses)

html = app.test_client().get("/").data.decode()
print(html.strip())
```

```output
<h1>Courses</h1>
<ul>

  <li>1. PYTHON (free)</li>

  <li>2. SQL</li>

</ul>
<p>Total: 2</p>
```

| Syntax | Meaning |
| --- | --- |
| `{{ value }}` | print a value |
| `{% for x in items %} ... {% endfor %}` | a loop (`{% else %}` runs when it is empty) |
| `{% if cond %} ... {% elif %} ... {% else %} ... {% endif %}` | a condition |
| `{{ value\|filter }}` | transform a value (`upper`, `length`, `default`, `round`) |
| `{# a comment #}` | a comment, not sent to the browser |

## Escaping: your protection against XSS

Jinja turns `<` into `&lt;` automatically, so text typed by a user cannot become HTML or a script:

```python
@app.route("/hello/<name>")
def hello(name):
    return render_template_string("<p>Hello, {{ name }}!</p>", name=name)

print(app.test_client().get("/hello/<script>alert(1)").data.decode())
```

```output
<p>Hello, &lt;script&gt;alert(1)!</p>
```

The `<script>` tag is shown as harmless text. This is called **autoescaping**.

:::warning
Only use the `|safe` filter (or `Markup`) on text **you** wrote, never on text from a user. `{{ comment|safe }}` switches the protection off and opens the door to cross-site scripting.
:::

## Template inheritance

Every page shares a header and footer. Write them once in a **base** template and let pages fill in the blanks:

```python
from jinja2 import DictLoader

app.jinja_loader = DictLoader({
    "base.html": "<header>SkillDARA</header>\n{% block content %}{% endblock %}\n<footer>(c) 2026</footer>",
    "about.html": '{% extends "base.html" %}{% block content %}<h2>About us</h2>{% endblock %}',
})

@app.route("/about")
def about():
    from flask import render_template
    return render_template("about.html")

print(app.test_client().get("/about").data.decode())
```

```output
<header>SkillDARA</header>
<h2>About us</h2>
<footer>(c) 2026</footer>
```

`{% extends %}` pulls in the base. Each `{% block %}` in the page replaces the matching block in the base.

## Useful filters and extras

| Tool | Example |
| --- | --- |
| default value | `{{ nickname\|default("friend") }}` |
| formatting | `{{ "%.1f"\|format(avg) }}` |
| including a piece | `{% include "nav.html" %}` |
| links | `<a href="{{ url_for('about') }}">About</a>` |
| macros (reusable snippets) | `{% macro card(title) %}...{% endmacro %}` |

:::tip
Keep logic out of templates. A template should **display** data your view has already prepared. If a template needs a long calculation, do it in Python first and pass the result in.
:::
