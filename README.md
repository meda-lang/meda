
# Meda

Meda is a procedural, general purpose programming language that is influenced by
TypeScript, Go, and Rust, with a dash of Python.

Everything that is in this repo is very much experimental. You have been
 warned :-)

## Language Design

### Design Prinicpals

1. The programming language should be a joy to use. It should be predictable,
intuitive, and clear.
2. Related to the above bullet, the programming lanuage adhears to the
"Don't Make Me Think" design prinicpal. The tradeoff is that the language will be
more verbose, but that is an acceptable tradeoff.
3. The language is opinionated. Developers should spend less time worrying about
whether or not to use a semi-colon or type and more time on being productive.
4. The codebase, libraries, tools, language, etc. need to be extensible and
flexible to accomediate future changes.
5. All code is open-sourced and the community is encouraged to contribute to the
evolution of the language.

### Design Ideas

1. Types are required. Why? Safety, debugging, and scalability.
2. All programs need to have a main method. Why? Having a main method makes it
easier to figure out where a program starts.
3. Formatter will be included and code that does not conform to the style guide
will not compile.

### Syntax

#### Constants

Constants are declared using the `const` keyword.

```rust
const planet: str = 'Mars'
```

#### Variables

Variables are declared using the `var` keyword.

```rust
var x: int = 4
```

#### Types

All variables require types. No exceptions.

```rust
var name: str = 'Sammy'
```

These are the primitive data types that Meda supports:

* `bool`
* `char`
* `float`
* `float8`
* `int`
* `uint`
* `str`

#### Loops

##### loop

```rust

loop (0 to 10, x) {
  print(x)
}

```

##### while

```rust

while (!stack.isEmpty()) {
  const name: str = stack.pop()
  print(name)
}

```

## History

### The Name

What's the deal with the name? Well I live in Alameda, CA and thought that meda
sounded kinda cool.

### And the seal as a logo?

Haha, glad you noticed. Well, you see, the first day I moved to Alameda, I was
on a walking with my family by the SF Bay near my home and I saw a seal! So yeah,
since there are seals near my house I'm going with a seal as a logo. And I'm
calling him Sammy. Don't @ me :-)
