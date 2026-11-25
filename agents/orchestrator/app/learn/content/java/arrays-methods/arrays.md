---
title: Arrays
summary: Store many values of one type in an array, loop through it, use the Arrays helper class and work with two-dimensional arrays.
takeaways:
- An array has a fixed size and zero-based positions
- Reading outside the bounds throws ArrayIndexOutOfBoundsException
- java.util.Arrays gives you toString, sort, fill, copyOf and binarySearch
---
## Creating arrays

An array holds a **fixed number** of values of the **same type**:

```java
int[] marks = {92, 48, 85, 71};           // size 4, values given right away
double[] prices = new double[3];          // size 3, every item starts as 0.0
String[] names = new String[2];           // every item starts as null

System.out.println(marks.length);
System.out.println(marks[0]);
System.out.println(marks[3]);
System.out.println(prices[1]);
System.out.println(names[0]);
```

```output
4
92
71
0.0
null
```

Positions start at **0**, so an array of size 4 has positions 0, 1, 2 and 3. `length` (without brackets) is the size. New arrays are filled with default values: `0`, `0.0`, `false` or `null`.

:::warning
Reading `marks[4]` or `marks[-1]` throws `ArrayIndexOutOfBoundsException` when the program runs. The loop `i <= marks.length` is the classic off-by-one mistake; use `i < marks.length`.
:::

## Looping and changing

```java
int[] marks = {92, 48, 85, 71};

int total = 0;
for (int i = 0; i < marks.length; i++) {
    total += marks[i];
}
System.out.println("Total: " + total);
System.out.println("Average: " + (double) total / marks.length);

int highest = marks[0];
for (int m : marks) {
    if (m > highest) {
        highest = m;
    }
}
System.out.println("Highest: " + highest);

marks[1] = 58;                             // change one value
System.out.println(marks[1]);
```

```output
Total: 296
Average: 74.0
Highest: 92
58
```

## The Arrays helper class

`import java.util.Arrays;` gives you tools for printing, sorting and copying:

```java
import java.util.Arrays;

public class Demo {
    public static void main(String[] args) {
        int[] marks = {92, 48, 85, 71};

        System.out.println(marks);                          // prints a memory-like code, not the values
        System.out.println(Arrays.toString(marks));         // prints the values

        Arrays.sort(marks);
        System.out.println(Arrays.toString(marks));
        System.out.println(Arrays.binarySearch(marks, 85)); // the array must be sorted first

        int[] copy = Arrays.copyOf(marks, 6);               // a longer copy; extra spots are 0
        System.out.println(Arrays.toString(copy));

        int[] zeros = new int[4];
        Arrays.fill(zeros, 7);
        System.out.println(Arrays.toString(zeros));
        System.out.println(Arrays.equals(marks, new int[]{48, 71, 85, 92}));
    }
}
```

```output
[I@1b6d3586
[92, 48, 85, 71]
[48, 71, 85, 92]
2
[48, 71, 85, 92, 0, 0]
[7, 7, 7, 7]
true
```

The first line is a code like `[I@1b6d3586` (the exact text differs from run to run): printing an array directly shows its type and address, not its values. Always use `Arrays.toString()`.

## Arrays are references

An array variable holds a **reference** to the array, not the array itself. Assigning it copies the reference, so both names point to the **same** array:

```java
int[] a = {1, 2, 3};
int[] b = a;                // b is another name for the same array
b[0] = 99;
System.out.println(a[0]);

int[] c = a.clone();        // a real, separate copy
c[0] = 5;
System.out.println(a[0]);
```

```output
99
99
```

Changing `b[0]` also changed `a[0]`. Use `clone()` or `Arrays.copyOf` to get an independent copy.

## Two-dimensional arrays

An array of arrays, like a table:

```java
int[][] grid = {
    {1, 2, 3},
    {4, 5, 6}
};

System.out.println(grid.length);          // number of rows
System.out.println(grid[0].length);       // number of columns in the first row
System.out.println(grid[1][2]);           // row 1, column 2

for (int[] row : grid) {
    for (int value : row) {
        System.out.print(value + " ");
    }
    System.out.println();
}
```

```output
2
3
6
1 2 3
4 5 6
```

## Arrays versus lists

| Array | `ArrayList` |
| --- | --- |
| fixed size | grows and shrinks |
| holds primitives (`int[]`) or objects | holds objects only (`ArrayList<Integer>`) |
| fast and memory-light | has helpful methods (`add`, `remove`, `contains`) |

Use an array when the size is known and fixed. Use an `ArrayList` (the collections lesson) for most everyday work.

:::interview
**Interviewers often ask:** "Can you change the size of an array after it is created?" No. The size is fixed. To get a bigger one, create a new array and copy the values (`Arrays.copyOf`), or use an `ArrayList`, which does that for you.
:::
