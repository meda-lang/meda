# meda

Meda is a general purpose programming language that is influenced by TypeScript,
Go, and Rust.

Everything that is in this repo is very much experimental. You have been
 warned :-)

## Design Ideas

1. Types are required. Why? Safety, debugging, and scalability.
2. Semis are required. Why? I don't want people to waste time thinking about
 whether they are required or not.
3. All programs need to have a main method. Why? Having a main method makes it 
easier to figure out where a program starts.

## Syntax

### Variables

Variables are declared using the `var` keyword.

```
var x: int = 4;
```

### Types

All variables require types. No exceptions.

```
var name: string = 'Sammy';
```

These are the primitive types that Meda supports:

* `bool`
* `string`
* `char`
* `int`

### Semi-colons

Semi-colons are required at the end of statements.

```
var isTested: bool = false;
```
