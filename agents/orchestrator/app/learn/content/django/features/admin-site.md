---
title: The admin site
summary: Get a complete data-management interface for free, then customise lists, filters, search and forms.
takeaways:
- Register a model and Django gives you create, read, update and delete pages
- ModelAdmin controls list columns, filters, search and form layout
- The admin is for trusted staff, not for end users
---
## A free back office

Many projects need staff to add courses, fix a student's email or check orders. In most frameworks that means building screens. In Django you **register the model** and the screens exist.

```py
python manage.py createsuperuser        # make a staff login
python manage.py runserver              # then open http://127.0.0.1:8000/admin/
```

```py
# courses/admin.py
from django.contrib import admin
from .models import Course, Student

admin.site.register(Course)
```

That one line gives you list, add, edit and delete pages, with validation taken from your model.

## Customising with ModelAdmin

```py
from django.contrib import admin
from .models import Student

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "marks", "active")       # columns in the list
    list_filter = ("department", "active")                          # a filter sidebar
    search_fields = ("name", "email")                               # a search box
    list_editable = ("marks",)                                      # edit right in the list
    ordering = ("-marks",)
    list_per_page = 25
    readonly_fields = ("joined",)
    autocomplete_fields = ("department",)                           # a search box instead of a huge dropdown
    fieldsets = (
        ("Who", {"fields": ("name", "email")}),
        ("Study", {"fields": ("department", "courses", "marks")}),
    )
```

| Option | Effect |
| --- | --- |
| `list_display` | which columns the list page shows (can include methods) |
| `list_filter` | filter links on the right |
| `search_fields` | what the search box looks in (`"department__name"` works too) |
| `list_editable` | edit those fields directly in the list |
| `readonly_fields` | visible but not editable |
| `fieldsets` | group the edit form into sections |
| `inlines` | edit related rows on the parent's page |

## Inlines and custom actions

```py
class EnrolmentInline(admin.TabularInline):
    model = Enrolment
    extra = 1                                       # one empty row ready to fill

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    inlines = [EnrolmentInline]
    actions = ["deactivate"]

    @admin.action(description="Deactivate selected students")
    def deactivate(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f"{updated} students deactivated.")

    @admin.display(description="Result", ordering="marks")
    def result(self, obj):
        return "Pass" if obj.marks >= 50 else "Fail"        # a computed column; add "result" to list_display
```

## Permissions in the admin

Only users with `is_staff=True` can log in. A staff user sees only the models they have **permissions** for (add, change, delete, view), set per user or per **group** in the admin itself. Create groups such as "Support" (can view and change students) and "Editors" (can change courses), and put people in them.

:::warning
The admin is powerful and is meant for **trusted staff**. Do not build your public product on it, put it behind a hard-to-guess URL or a VPN where you can, require strong passwords and use two-factor authentication on real systems.
:::

:::tip
Define `__str__` on every model. The admin uses it for names in lists and dropdowns, and "Student object (3)" everywhere is a poor experience for the people who use the site daily.
:::
