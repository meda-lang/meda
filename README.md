
# Meda

## Current design experiment

Start with the [research handoff](docs/research-handoff.md) for the complete
design/code/results index, current decision, and [tracked next steps](docs/issues/README.md).

[Draft 2.1](docs/design-draft-2.1.md) explores Meda for AI-authored and
AI-maintained software, including programs that use LLMs. The
[Gate A corpus and Gate B prototype](experiments/gates/README.md) provide a
runnable pure-language subset, guarded edits, and a maintenance experiment.
The legacy language ideas below describe the original prototype; they are not
the current proposed specification. No stable language edition is released.

The [shared runtime comparison](docs/runtime-comparison.md) runs actual Meda and
strict TypeScript clients over the same host/adapters. Both pass the implemented
screen; language-specific value remains unproven. See its
[reproduction instructions](experiments/interop_compare/README.md).

The [bounded MCP and A2A workflow](docs/interop-workflow.md) now has a
[real-SDK TypeScript reference candidate](docs/interop-reference-results.md),
governed by the [design amendment](docs/interop-design-amendment.md),
[comparison plan](docs/interop-evaluation.md) and [work packets](docs/interop-roadmap.md).
Its common host, adapters and reference client run; full acceptance remains open.
The new effectful Meda arm and controlled maintenance study are not implemented.
See the [candidate's reproduction instructions](experiments/interop_d0/README.md).

```sh
python3 -m unittest discover -s experiments/gates/tests -v
python3 experiments/gates/benchmark.py --smoke --output /tmp/meda-smoke.json
```

## Original prototype

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
