import {Token} from './token.js';
import {TokenType} from './token_type.js';
import Meda from './meda.js';

export default class Scanner {
  source = '';
  tokens = [];

  #start = 0;
  #current = 0;
  #line = 1;

  constructor(source) {
    this.source = source;
  }

  #addToken(type, literal = null) {
    const text = this.source.substring(this.#start, this.#current);
    this.tokens.push(new Token(type, text, literal, this.#line));
  }

  #advance() {
    return this.source[this.#current++];
  }

  #peek() {
    if (this.#isAtEnd()) return '\0';
    return this.source.charAt(this.#current);
  }

  #match(expected) {
    if (this.#isAtEnd()) return false;
    if (this.#peek() != expected) return false;

    this.#current++;
    return true;
  }

  #string() {
    while (this.#peek() !== '\'' && !this.#isAtEnd()) {
      if (this.#peek() === '\n') this.line++;
      this.#advance();
    }

    if (this.#isAtEnd()) {
      Meda.error(this.#line, 'Unterminated string.');
      return;
    }

    this.#advance();

    const value = this.source.substring(this.#start + 1, this.#current - 1);
    this.#addToken(TokenType.STRING, value);
  }

  scanToken() {
    const currentChar = this.#advance();

    switch (currentChar) {
      case '(': {
        this.#addToken(TokenType.LEFT_PAREN);
        break;
      }

      case ')': {
        this.#addToken(TokenType.RIGHT_PAREN);
        break;
      }

      case '{': {
        this.#addToken(TokenType.LEFT_BRACE);
        break;
      }

      case '}': {
        this.#addToken(TokenType.RIGHT_BRACE);
        break;
      }

      case ',': {
        this.#addToken(TokenType.COMMA);
        break;
      }

      case '.': {
        this.#addToken(TokenType.DOT);
        break;
      }

      case '-': {
        this.#addToken(TokenType.MINUS);
        break;
      }

      case '+': {
        this.#addToken(TokenType.PLUS);
        break;
      }

      case ';': {
        this.#addToken(TokenType.SEMICOLON);
        break;
      }

      case '*': {
        this.#addToken(TokenType.STAR);
        break;
      }

      case '!': {
        const newToken = this.#match('=') ?
            TokenType.BANG_EQUAL : TokenType.BANG;
        this.#addToken(newToken);
        break;
      }

      case '=': {
        const newToken = this.#match('=') ?
            TokenType.EQUAL_EQUAL : TokenType.EQUAL;
        this.#addToken(newToken);
        break;
      }

      case '<': {
        const newToken = this.#match('=') ?
            TokenType.LESS_EQUAL : TokenType.LESS;
        this.#addToken(newToken);
        break;
      }

      case '>': {
        const newToken = this.#match('=') ?
            TokenType.GREATER_EQUAL : TokenType.GREATER;
        this.#addToken(newToken);
        break;
      }

      case '/': {
        if (this.#match('/')) {
          while (this.#peek() != '\n' && !this.#isAtEnd()) this.#advance();
        } else {
          this.#addToken(TokenType.SLASH);
        }
        break;
      }

      case ' ': {
        break;
      }

      case '\r': {
        break;
      }

      case '\t': {
        break;
      }

      case '\n': {
        this.#line++;
        break;
      }

      case '\'': {
        this.#string();
        break;
      }

      default: {
        Meda.error(this.#line, 'Unexpected string.');
        break;
      }
    }
  }

  #isAtEnd() {
    return this.#current >= this.source.length;
  }

  scanTokens() {
    while (!this.#isAtEnd()) {
      this.#start = this.#current;
      this.scanToken();
    }

    this.tokens.push(new Token(TokenType.EOF, '', null, this.#line));

    return this.tokens;
  }
}
