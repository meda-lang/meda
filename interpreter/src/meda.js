import os from 'os';
import fs from 'fs';
import readline from 'readline';

import constants from './shared/constants.js';
import Scanner from './scanner.js';

export default class Meda {
  static #hadError = false;

  constructor() {
    Meda.main();
  }

  static #report(line, where, message) {
    console.log(`[line ${line}] Error ${where}: ${message}`);
    this.#hadError = true;
  }

  static error(line, message) {
    this.#report(line, '', message);
  }

  static run(source) {
    // here for testing
    const s = new Scanner(source);
    const tokens = s.scanTokens();

    tokens.forEach((token) => {
      console.log(token);
    });
  }

  static runPrompt() {
    console.log(constants.Strings.Repl.WELCOME_MESSAGE);

    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });

    rl.setPrompt(constants.Strings.Repl.PROMPT);
    rl.prompt();

    rl.on('line', (line) => {
      const isLineEmpty = line === null || line === '';

      if (isLineEmpty) {
        console.log(constants.Strings.Repl.EXIT_MESSAGE);
        process.exit(constants.ExitCodes.NORMAL);
      }

      this.run(line);
      this.#hadError = false;
      rl.prompt();
    }).on('close', () => {
      console.log(constants.Strings.Repl.EXIT_MESSAGE);
      process.exit(constants.ExitCodes.NORMAL);
    });
  }

  static runFile(filePath) {
    try {
      const source = fs.readFileSync(filePath, {
        encoding: constants.DEFAULT_CHAR_SET,
        flag: 'r'});

      if (this.#hadError) process.exit(os.constants.errno.ENOENT);
      this.run(source);
    } catch (err) {
      console.error(err);
      process.exit(os.constants.errno.ENOENT);
    }
  }

  static main() {
    const isTooManyArgs = process.argv.length > 3;
    const isFilenameInputted = process.argv.length === 3;
    const filenameIndex = 2;

    if (isTooManyArgs) {
      console.log(constants.ErrorMessages.E2BIG);
      process.exit(os.constants.errno.E2BIG);
    } else if (isFilenameInputted) {
      const filePath = process.argv[filenameIndex];
      this.runFile(filePath);
    } else {
      this.runPrompt();
    }
  }
}
