---
title: Templates
summary: Render HTML with the Django template language: variables, tags, filters, inheritance and automatic escaping.
takeaways:
- {{ }} prints values, {% %} runs logic, {# #} is a comment
- Template inheritance keeps one layout for every page
- Django escapes output automatically, which blocks most XSS
---
## From view to page

A view collects the data; a **template** turns it into HTML. Django looks for templates in each app's `templates/` folder:

```py
courses/
  templates/
    courses/
      list.html
```

and the view renders one with `render(request, "courses/list.html", {"courses": courses})`. (Putting a second `courses/` folder inside `templates/` avoids name clashes between apps.) The examples below build templates from strings so they run anywhere.

## Variables, tags and filters

```python
from django.template import Engine, Context

engine = Engine()
template = engine.from_string("""
<h1>{{ title|upper }}</h1>
<ul>
{% for c in courses %}
  <li>{{ forloop.counter }}. {{ c.name }}{% if c.free %} (free){% endif %}</li>
{% empty %}
  <li>No courses yet</li>
{% endfor %}
</ul>
<p>{{ courses|length }} courses · {{ nickname|default:"guest" }} · {{ price|floatformat:2 }}</p>
""")

html = template.render(Context({
    "title": "Courses",
    "courses": [{"name": "Python", "free": True}, {"name": "SQL", "free": False}],
    "price": 499,
}))
print(html.strip())
```

```output
<h1>COURSES</h1>
<ul>

  <li>1. Python (free)</li>

  <li>2. SQL</li>

</ul>
<p>2 courses · guest · 499.00</p>
```

| Syntax | Meaning |
| --- | --- |
| `{{ value }}` | print a value (dots reach attributes, keys and methods) |
| `{% for x in items %} ... {% empty %} ... {% endfor %}` | a loop, with a fallback when empty |
| `{% if cond %} ... {% elif %} ... {% else %} ... {% endif %}` | a condition |
| `{{ value\|filter:arg }}` | transform a value (`upper`, `length`, `default`, `date`, `floatformat`) |
| `{# a comment #}` | not sent to the browser |
| `{% url 'name' %}` | build a link from a URL name |
| `{% csrf_token %}` | add the CSRF protection field to a form |

## Automatic escaping

Django turns `<` into `&lt;` for you, so text typed by a user cannot become HTML or script:

```python
page = engine.from_string("<p>{{ comment }}</p>")
print(page.render(Context({"comment": "<script>alert(1)</script>"})))
```

```output
<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>
```

:::warning
`{{ value|safe }}` and `{% autoescape off %}` switch the protection off. Use them only on text **you** wrote, never on user input.
:::

## Template inheritance

Write the page frame once in a **base** template; each page fills in the blocks:

```python
engine = Engine(loaders=[("django.template.loaders.locmem.Loader", {
    "base.html": "<header>SkillDARA</header>\n<title>{% block title %}Home{% endblock %}</title>\n{% block content %}{% endblock %}\n<footer>(c) 2026</footer>",
    "about.html": "{% extends 'base.html' %}{% block title %}About{% endblock %}{% block content %}<h2>About us</h2>{% include 'team.html' %}{% endblock %}",
    "team.html": "<p>Team of {{ size }}</p>",
})])

print(engine.get_template("about.html").render(Context({"size": 12})))
```

```output
<header>SkillDARA</header>
<title>About</title>
<h2>About us</h2><p>Team of 12</p>
<footer>(c) 2026</footer>
```

`{% extends %}` must be the first tag. Each `{% block %}` in the child replaces the same block in the base. `{% include %}` drops in a smaller reusable piece.

## Custom filters and tags

When you need your own formatting, write a filter:

```py
# courses/templatetags/course_extras.py
from django import template
register = template.Library()

@register.filter
def minutes(value):
    hours, mins = divmod(int(value), 60)
    return f"{hours}h {mins}m" if hours else f"{mins}m"
```

```py
{% load course_extras %}
<p>Length: {{ lesson.length|minutes }}</p>
```

## Static files

CSS, JavaScript and images live in each app's `static/` folder:

```py
{% load static %}
<link rel="stylesheet" href="{% static 'courses/site.css' %}">
```

:::tip
Keep logic out of templates. Calculate things in the view or the model and pass the result in. A template that needs a long `if` chain is a sign the view should prepare better data.
:::
