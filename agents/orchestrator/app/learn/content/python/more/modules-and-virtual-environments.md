---
title: Modules, packages and virtual environments
summary: Reuse code with import, organise a project into modules, install libraries with pip, and keep each project separate with a virtual environment.
takeaways:
- A module is a Python file; a package is a folder of modules
- pip installs libraries; requirements.txt records them
- A virtual environment gives every project its own set of libraries
---
## Modules: reuse code

A **module** is just a Python file. `import` lets you use what is inside it. Python comes with a large **standard library**:

```python
import math
import statistics
from collections import Counter
from datetime import date

print(math.sqrt(144), math.pi)
print(statistics.mean([92, 48, 85, 71]))
print(Counter("banana").most_common(2))
print(date(2026, 3, 14).strftime("%d %B %Y"))
```

```output
12.0 3.141592653589793
74
[('a', 3), ('n', 2)]
14 March 2026
```

| Way to import | Use |
| --- | --- |
| `import math` | then write `math.sqrt(...)` |
| `from math import sqrt` | then write `sqrt(...)` directly |
| `import numpy as np` | a short nickname (the standard one for NumPy) |
| `from collections import Counter` | take one tool from a module |

## Your own module

Save this as `shapes.py`:

```py
PI = 3.14159

def circle_area(radius):
    return PI * radius ** 2

if __name__ == "__main__":
    print(circle_area(2))        # runs only when you run this file directly
```

Use it from another file in the same folder:

```py
import shapes
print(shapes.circle_area(3))
```

The `if __name__ == "__main__":` block stops test code from running when the file is imported.

## Packages: folders of modules

```py
myproject/
  main.py
  tools/
    __init__.py          # makes the folder a package (may be empty)
    cleaning.py
    stats.py
```

```py
from tools.cleaning import remove_duplicates
from tools import stats
```

## pip: installing libraries

**pip** downloads libraries from the Python Package Index (PyPI):

```py
pip install pandas
pip install pandas==2.2.2        # an exact version
pip install -r requirements.txt  # everything a project needs
pip list                         # what is installed
pip freeze > requirements.txt    # record the exact versions
```

## Virtual environments: one box per project

Project A may need an old version of a library and project B a new one. Installing everything globally causes clashes. A **virtual environment** is a private folder of libraries for one project.

```py
python -m venv .venv                 # create it, once per project
.venv\Scripts\activate               # Windows: switch it on
source .venv/bin/activate            # macOS and Linux
pip install numpy pandas scikit-learn
deactivate                           # switch it off
```

When it is active, the terminal shows `(.venv)` and `pip install` goes only into this project.

| Do | Do not |
| --- | --- |
| make one environment per project | install every library globally |
| keep `requirements.txt` in the project | commit the `.venv` folder to Git |
| add `.venv/` to `.gitignore` | forget to activate it before running |

## Check where code is running

```python
import sys
print("Python version:", sys.version_info.major, sys.version_info.minor)
print("running inside a virtual environment:", sys.prefix != sys.base_prefix)
```

```output
Python version: 3 10
running inside a virtual environment: True
```

The last line prints `True` when a virtual environment is active and `False` when you are using the global Python. Your version number and this answer will depend on your own computer.

## Notebooks and tools for AI work

| Tool | Use |
| --- | --- |
| **Jupyter Notebook / JupyterLab** | code, charts and notes in one page (`pip install notebook`) |
| **Google Colab** | free notebooks in the browser, with a GPU, nothing to install |
| **VS Code** | a good editor for scripts and notebooks |
| **conda** | an alternative to pip and venv, popular in data science |

:::tip
Start every project with `python -m venv .venv`, activate it, then install what you need. You will avoid most "it works on my laptop" problems.
:::
