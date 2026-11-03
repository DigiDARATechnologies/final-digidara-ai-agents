"""A correct answer must pass: every Hard Python problem, solved the plain way a
learner would, against all its public and hidden tests."""
import subprocess
import sys

import pytest

from lms_api.catalog import topic_difficulty
from lms_api.problem_catalog import PROBLEMS

NUMBERS = "n = int(input())\nvalues = list(map(int, input().split()))\n"
TWO = "a, b = map(int, input().split())\n"
LINES = "n = int(input())\nlines = [input() for _ in range(n)]\n"

SOLUTIONS = {
    "square-with-lambda": "square = lambda x: x * x\nprint(square(int(input())))",
    "sort-with-lambda-key": "words = input().split()\nwords.sort(key=lambda w: len(w))\nprint(' '.join(words))",
    "filter-even-numbers": NUMBERS + "print(' '.join(map(str, filter(lambda x: x % 2 == 0, values))))",
    "map-doubling": NUMBERS + "print(' '.join(map(str, map(lambda x: x * 2, values))))",
    "reduce-product": "from functools import reduce\n" + NUMBERS + "print(reduce(lambda a, b: a * b, values))",
    "write-and-read-back": "text = input()\nopen('f.txt', 'w').write(text)\nprint(open('f.txt').read())",
    "count-lines-in-a-file": LINES + "open('f.txt', 'w').write('\\n'.join(lines) + '\\n')\nprint(len(open('f.txt').readlines()))",
    "word-count-from-file": "text = input()\nopen('f.txt', 'w').write(text)\nprint(len(open('f.txt').read().split()))",
    "append-lines-to-a-file": "open('f.txt', 'w').close()\n" + LINES + "for line in lines:\n    open('f.txt', 'a').write(line + '\\n')\nprint(', '.join(open('f.txt').read().split('\\n')[:-1]))",
    "copy-file-content-reversed": "text = input()\nopen('a.txt', 'w').write(text)\nopen('b.txt', 'w').write(open('a.txt').read()[::-1])\nprint(open('b.txt').read())",
    "safe-division": TWO + "try:\n    print(a // b)\nexcept ZeroDivisionError:\n    print('Cannot divide by zero')",
    "safe-integer-conversion": "try:\n    print(int(input()) * 2)\nexcept ValueError:\n    print('Invalid number')",
    "safe-list-index-access": NUMBERS + "i = int(input())\ntry:\n    print(values[i])\nexcept IndexError:\n    print('Index out of range')",
    "custom-exception-message": "import math\nn = int(input())\nprint('Negative not allowed' if n < 0 else math.isqrt(n))",
    "finally-block-behavior": TWO + "try:\n    print(a // b)\nexcept ZeroDivisionError:\n    print('Error')\nfinally:\n    print('Done')",
    "simple-class-and-method": "import math\nclass Circle:\n    def __init__(self, r):\n        self.r = r\n    def area(self):\n        return math.pi * self.r ** 2\nprint(f'{Circle(int(input())).area():.2f}')",
    "class-with-constructor": "class Rectangle:\n    def __init__(self, w, h):\n        self.w, self.h = w, h\n    def perimeter(self):\n        return 2 * (self.w + self.h)\nprint(Rectangle(*map(int, input().split())).perimeter())",
    "inheritance-basics": "class Animal:\n    def speak(self):\n        return '...'\nclass Dog(Animal):\n    def speak(self):\n        return 'Woof'\nfor _ in range(int(input())):\n    print(Dog().speak())",
    "class-attribute-counter": "class Counter:\n    count = 0\n    def __init__(self):\n        Counter.count += 1\nfor _ in range(int(input())):\n    Counter()\nprint(Counter.count)",
    "string-representation": "class Point:\n    def __init__(self, x, y):\n        self.x, self.y = x, y\n    def __str__(self):\n        return f'({self.x}, {self.y})'\nprint(Point(*input().split()))",
    "square-root-using-math": "import math\nprint(math.isqrt(int(input())))",
    "greatest-common-divisor": "import math\nprint(math.gcd(*map(int, input().split())))",
    "factorial-using-math": "import math\nprint(math.factorial(int(input())))",
    "ceiling-and-floor": "import math\nx = float(input())\nprint(math.floor(x), math.ceil(x))",
    "counting-combinations": "import math\nprint(math.comb(*map(int, input().split())))",
    "fix-the-off-by-one-loop": "n = int(input())\ntotal = 0\nfor i in range(1, n + 1):\n    total += i\nprint(total)",
    "fix-the-wrong-comparison": "n = int(input())\nif n > 0:\n    print('Positive')\nelse:\n    print('Non-positive')",
    "fix-the-string-concatenation-bug": "a, b = input().split()\nprint(a + ' ' + b)",
    "fix-the-index-error": "n = int(input())\nvalues = list(map(int, input().split()))\nprint(values[n - 1])",
    "fix-the-return-value": "def double(x):\n    return x * 2\n\nn = int(input())\nprint(double(n))",
}
HARD = [p for p in PROBLEMS if p["technology"] == "python" and topic_difficulty("python", p["topic"]) == "Hard"]


def test_every_hard_problem_has_a_solution_here():
    assert {p["slug"] for p in HARD} == set(SOLUTIONS)


@pytest.mark.parametrize("problem", HARD, ids=lambda p: p["slug"])
def test_the_correct_answer_passes_every_test(problem, tmp_path):
    source = tmp_path / "solution.py"
    source.write_text(SOLUTIONS[problem["slug"]])
    for test in problem["tests"]:
        run = subprocess.run([sys.executable, str(source)], input=test[0], capture_output=True, text=True, timeout=20, cwd=tmp_path)
        assert run.returncode == 0, (test[0], run.stderr)
        assert run.stdout.strip() == test[1].strip(), test[0]
