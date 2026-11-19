---
title: Arrays and objects
summary: Store lists with arrays and records with objects; use map, filter and destructuring.
takeaways:
- An array is an ordered list; an object is a set of named values
- map, filter and find work on every item without a loop
- Destructuring pulls values out neatly
---
## Arrays

```javascript
const marks = [72, 85, 90];
console.log(marks[0]);        // 72
console.log(marks.length);    // 3

marks.push(66);               // add at the end
marks.pop();                  // remove the last
```

## The three most useful array methods

```javascript
const nums = [1, 2, 3, 4, 5];

const doubled = nums.map((n) => n * 2);        // [2, 4, 6, 8, 10]
const evens = nums.filter((n) => n % 2 === 0); // [2, 4]
const firstBig = nums.find((n) => n > 3);      // 4
const total = nums.reduce((sum, n) => sum + n, 0); // 15
```

| Method | Gives you |
| --- | --- |
| `map` | a new array, each item changed |
| `filter` | a new array with only the items that pass |
| `find` | the first item that passes |
| `reduce` | one value built from all items |

## Objects

An object holds named values:

```javascript
const student = {
  name: "Asha",
  age: 21,
  skills: ["HTML", "CSS"],
};

console.log(student.name);       // dot notation
console.log(student["age"]);     // bracket notation
student.city = "Chennai";        // add a property
```

## Arrays of objects

The shape of most real data:

```javascript
const students = [
  { name: "Asha", marks: 92 },
  { name: "Ravi", marks: 78 },
];
const toppers = students.filter((s) => s.marks >= 90);
console.log(toppers);   // [{ name: "Asha", marks: 92 }]
```

## Destructuring and spread

```javascript
const { name, age } = student;     // pull properties out
const [first, second] = marks;     // pull items out

const copy = { ...student, age: 22 };  // copy and change one thing
const more = [...marks, 100];          // copy and add
```

## JSON

Objects turn to text and back with `JSON.stringify` and `JSON.parse`. This is how data travels to and from servers.

```javascript
const text = JSON.stringify({ a: 1 });   // '{"a":1}'
const back = JSON.parse(text);           // { a: 1 }
```

:::tip
`const` stops you reassigning the name, but you can still change what is inside an array or object it points to.
:::
