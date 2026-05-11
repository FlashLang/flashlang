# FlashLang Documentation
## Version 1.3.3

FlashLang is an interpreted programming language with support for:

- Variables
- Arithmetic
- Functions
- Classes
- Python blocks
- Imports
- JSON
- Arrays
- if / else if / else

---

# Quick start

```flashlang
print("Hello World");
```

---

# Variables

```flashlang
var name = "Alice";
var age = 25;

print(name);
print(age);
```

---

# Arithmetic

```flashlang
var a = 10;
var b = 3;

var sum = a + b;
var diff = a - b;
var product = a * b;
var quotient = a / b;

print(sum);
print(diff);
print(product);
print(quotient);
```

Supported:

- `+`
- `-`
- `*`
- `/`
- `()`

---

# Strings

```flashlang
var text = "Hello" + " World";
print(text);
```

Mixed concatenation:

```flashlang
var value = "Result: " + (10 + 20);
print(value);
```

---

# Terms

```flashlang
var score = 85;

if (score >= 90) {
    print("Grade A");
} else if (score >= 80) {
    print("Grade B");
} else {
    print("Grade C");
}
```

Supported:

- `==`
- `>`
- `<`
- `>=`
- `<=`

---

# Arrays

Creation:

```flashlang
var arr = [10, 20, 30];
```

Change:

```flashlang
arr[1] = 99;
```

Usage:

```flashlang
print(arr);
```

---

# Cycles

```flashlang
for item in [1, 2, 3] {
    print(item);
}
```

---

# Functions

```flashlang
func add(a, b) {
    return a + b;
}

var result = add(5, 10);
print(result);
```

---

# Classes

## Creating a class

```flashlang
class Person {
    var name = "";
    var age = 0;

    constructor(name, age) {
        this.name = name;
        this.age = age;
    }

    func introduce() {
        print("I'm " + this.name);
    }
}
```

## Creating an Object

```flashlang
var person = new Person("Alice", 25);
```

## Calling a Method

```flashlang
person.introduce();
```

---

# this

`this` is used inside the class:

```flashlang
this.name = name;
```

---

# Python blocks

FlashLang supports built-in Python.

```flashlang
python {
def greet(name):
    return f"Hello, {name}"
}
```

Usage:

```flashlang
var msg = greet("FlashLang");
print(msg);
```

---

# Importing modules

```flashlang
import math;
import random;
```

Import FlashLang modules:

```flashlang
import mymodule;
```

---

# JSON

## Parsing

```flashlang
var obj = json_parse('{"name":"Alice"}');
```

## Serialization

```flashlang
var text = json_stringify(obj);
```

---

# Built-in functions

## print

```flashlang
print("Hello");
```

## input

```flashlang
var name = input("Name: ");
```

## len

```flashlang
var size = len([1,2,3]);
```

## range

```flashlang
range(5)
range(1, 10)
```

---

# Data Types

Supported:

- String
- Integer
- Float
- Boolean
-Array
- Object
-null

---

# Boolean values

```flashlang
true
false
null
```

---

# Logging

The interpreter uses Python logging.

Debug mode:

```bash
python flashlang.py --debug
```

---

# Running a file

```bash
python flashlang.py program.flang
```

---

# Project structure

```text
flashlang.py
lib/
```

---

# Example of a complete program

```flashlang
python {
def greet_py(name):
    return f"Hello from Python, {name}!"
}

class Person {
    var name = "";
    var age = 0;

    constructor(name, age) {
        this.name = name;
        this.age = age;
    }

    func introduce() {
        print("I'm " + this.name + ", " + this.age + " years old");
    }
}

var person = new Person("Alice", 25);
person.introduce();

var result = 10 + 20;
print(result);

var msg = greet_py("FlashLang");
print(msg);
```

---

# Features of version 1.3.3

- Fixed arithmetic via `eval`
- Fixed Python functions
- Completely working classes
- `new` support
- `this` support
- Arrays
- JSON
- Import modules
- Python blocks
- if / else if / else
