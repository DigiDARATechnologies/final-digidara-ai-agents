---
title: Reading and writing files
summary: Read and write text files with java.nio.file, handle paths and exceptions, and work with CSV-like data.
takeaways:
- Files and Path in java.nio.file make reading and writing short
- Always handle IOException, and close resources
- Read very large files line by line instead of loading them whole
---
## Paths and files

The modern classes live in `java.nio.file`. A `Path` is the address of a file; `Files` has the actions.

```java
import java.io.IOException;
import java.nio.file.*;
import java.util.List;

public class FileDemo {
    public static void main(String[] args) throws IOException {
        Path file = Path.of("students.txt");

        Files.writeString(file, "Asha,92\nRavi,48\nMeena,85\n");     // create or overwrite

        String all = Files.readString(file);
        System.out.println(all);

        List<String> lines = Files.readAllLines(file);
        System.out.println(lines.size());
        System.out.println(lines.get(1));

        System.out.println(Files.exists(file));
        System.out.println(Files.size(file) > 0);
    }
}
```

```output
Asha,92
Ravi,48
Meena,85

3
Ravi,48
true
true
```

(The blank line after the first block is the file's final newline.) Run this on your laptop and look for `students.txt` in the folder you ran the program from.

`Files.readString` and `writeString` suit small text files. `main` declares `throws IOException` because a file operation can fail (missing file, no permission, disk full).

## Appending and listing

```java
Files.writeString(file, "Kiran,77\n", StandardOpenOption.APPEND);      // add to the end
Files.copy(file, Path.of("backup.txt"), StandardCopyOption.REPLACE_EXISTING);
Files.delete(Path.of("backup.txt"));

try (var names = Files.list(Path.of("."))) {                            // list a folder
    names.forEach(System.out::println);
}
```

| Method | Does |
| --- | --- |
| `Files.writeString(path, text)` | write text (replaces the file) |
| `Files.readString(path)` | read the whole file as one String |
| `Files.readAllLines(path)` | read into a `List<String>` |
| `Files.exists(path)` | does it exist |
| `Files.createDirectories(path)` | make a folder (and parents) |
| `Files.copy`, `Files.move`, `Files.delete` | copy, move, delete |
| `Files.list`, `Files.walk` | list a folder, or a whole tree |

## Processing the lines

```java
List<String> lines = List.of("Asha,92", "Ravi,48", "Meena,85");

int total = 0;
for (String line : lines) {
    String[] parts = line.split(",");
    String name = parts[0];
    int marks = Integer.parseInt(parts[1].trim());
    total += marks;
    System.out.println(name + " -> " + (marks >= 50 ? "Pass" : "Fail"));
}
System.out.println("Average: " + (double) total / lines.size());
```

```output
Asha -> Pass
Ravi -> Fail
Meena -> Pass
Average: 75.0
```

For real CSV files (with quoted commas and so on), use a library such as **OpenCSV** or **Apache Commons CSV** rather than `split`.

## Big files: read line by line

`readAllLines` loads everything into memory. For a very large file, use a buffered reader inside **try-with-resources**:

```java
import java.io.*;

try (BufferedReader reader = Files.newBufferedReader(Path.of("big.log"))) {
    String line;
    int errors = 0;
    while ((line = reader.readLine()) != null) {
        if (line.contains("ERROR")) {
            errors++;
        }
    }
    System.out.println("Errors: " + errors);
} catch (IOException e) {
    System.out.println("Could not read: " + e.getMessage());
}
```

Or lazily with a stream: `try (var lines = Files.lines(path)) { ... }`.

## Writing with a BufferedWriter

```java
try (BufferedWriter writer = Files.newBufferedWriter(Path.of("report.txt"))) {
    writer.write("Name,Marks");
    writer.newLine();
    writer.write("Asha,92");
    writer.newLine();
} catch (IOException e) {
    System.out.println("Could not write: " + e.getMessage());
}
```

## Serialization and JSON

To save **objects** rather than lines of text, the common choice today is JSON, using a library such as **Jackson** or **Gson**:

```java
// with the Jackson library
ObjectMapper mapper = new ObjectMapper();
String json = mapper.writeValueAsString(new Student("Asha", 92));       // {"name":"Asha","marks":92}
Student back = mapper.readValue(json, Student.class);
```

Java also has built-in serialization (`Serializable`), but it is fragile and has security problems; prefer JSON for data you store or send.

## Paths: be careful

| Habit | Why |
| --- | --- |
| use `Path.of("folder", "file.txt")` | handles `/` and `\` differences between systems |
| never build paths by joining user input | a name like `../../secret` can escape your folder (path traversal) |
| specify the encoding for text (UTF-8 is the default for these methods) | accented and Indian-language text stays correct |
| check `Files.exists` only for information | the file can still disappear before you open it; handle the exception |

:::interview
**Interviewers often ask:** "How do you read a file in Java?" With `Files.readAllLines` or `Files.readString` for small files, or `BufferedReader` (or `Files.lines`) inside try-with-resources for large ones, handling `IOException`. "Why try-with-resources?" It closes the file automatically, even when an exception occurs.
:::
