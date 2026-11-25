---
title: Forms and validation
summary: Build forms from classes, validate on the server with built-in and custom rules, and turn a model into a form with ModelForm.
takeaways:
- A Form class declares fields, validation and rendering in one place
- is_valid() runs all checks; cleaned_data holds safe values
- ModelForm builds a form from a model and can save it
---
## A form class

```python
from django import forms

class ContactForm(forms.Form):
    name = forms.CharField(min_length=2, max_length=60)
    email = forms.EmailField()
    age = forms.IntegerField(min_value=16, max_value=100, required=False)
    message = forms.CharField(widget=forms.Textarea, min_length=10)

good = ContactForm({"name": "  Asha  ", "email": "asha@example.com", "age": "21", "message": "I would like a demo."})
print(good.is_valid())
print(good.cleaned_data)

bad = ContactForm({"name": "A", "email": "nope", "age": "12", "message": "short"})
print(bad.is_valid())
for field, errors in bad.errors.items():
    print(field, "->", errors[0])
```

```output
True
{'name': 'Asha', 'email': 'asha@example.com', 'age': 21, 'message': 'I would like a demo.'}
False
name -> Ensure this value has at least 2 characters (it has 1).
email -> Enter a valid email address.
age -> Ensure this value is greater than or equal to 16.
message -> Ensure this value has at least 10 characters (it has 5).
```

`cleaned_data` is **converted and cleaned**: spaces are trimmed and the age became a real `int`. Always use `cleaned_data`, never `request.POST`, after validation.

## Custom validation

```python
from django.core.exceptions import ValidationError

class SignupForm(forms.Form):
    username = forms.CharField(min_length=3)
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    confirm = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):                                  # one field
        value = self.cleaned_data["username"].lower()
        if value in {"admin", "root"}:
            raise ValidationError("That username is reserved.")
        return value

    def clean(self):                                           # several fields together
        data = super().clean()
        if data.get("password") and data.get("password") != data.get("confirm"):
            self.add_error("confirm", "The passwords do not match.")
        return data

form = SignupForm({"username": "Admin", "password": "longenough1", "confirm": "different1"})
print(form.is_valid())
print({field: errors[0] for field, errors in form.errors.items()})

ok = SignupForm({"username": "Asha", "password": "longenough1", "confirm": "longenough1"})
print(ok.is_valid(), ok.cleaned_data["username"])
```

```output
False
{'username': 'That username is reserved.', 'confirm': 'The passwords do not match.'}
True asha
```

| Method | Checks |
| --- | --- |
| `clean_<field>()` | one field (and may change its value) |
| `clean()` | rules that involve more than one field |
| field options (`min_length`, `max_value`, `required`) | the basics, with no code |

## ModelForm: a form from a model

```python
from django.db import models, connection

class Feedback(models.Model):
    name = models.CharField(max_length=60)
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)

with connection.schema_editor() as editor:
    editor.create_model(Feedback)

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ["name", "rating", "comment"]               # always list fields explicitly

    def clean_rating(self):
        rating = self.cleaned_data["rating"]
        if not 1 <= rating <= 5:
            raise ValidationError("Rating must be from 1 to 5.")
        return rating

print(FeedbackForm({"name": "Asha", "rating": "9"}).errors["rating"][0])

form = FeedbackForm({"name": "Asha", "rating": "5", "comment": "Great course"})
saved = form.save()                                          # validates, then creates the row
print(saved.pk, Feedback.objects.count())
```

```output
Rating must be from 1 to 5.
1 1
```

:::warning
Always set `fields = [...]` (or `exclude`) explicitly. `fields = "__all__"` would expose every column of the model, including ones users must never set, such as `is_staff` or `price`.
:::

## The view pattern

```py
from django.shortcuts import render, redirect

def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            send_message(form.cleaned_data)
            return redirect("thanks")              # Post/Redirect/Get: refresh will not resubmit
    else:
        form = ContactForm()
    return render(request, "contact.html", {"form": form})
```

```py
<form method="post">
  {% csrf_token %}
  {{ form.as_p }}
  <button type="submit">Send</button>
</form>
```

If validation fails, the same form is re-rendered **with the user's values and the error messages**, for free. `{% csrf_token %}` is required for every POST form (see the security lesson).

:::interview
**Interviewers often ask:** "Where should validation happen?" On the server, always. Browser checks are a convenience. In Django, put rules in the form (`clean_<field>`, `clean`) or in model validators so every entry path uses the same rules.
:::
