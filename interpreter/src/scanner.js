import {Token} from './token.js';
import {TokenType} from './token_type.js';
import Meda from './meda.js';

export default class Scanner {
  source = '';
  tokens = [];

  #start = 0;
  #current = 0;
  #line = 1;

  #keywords = new Map();

  constructor(source) {
    this.source = source;
    this.#keywords.set('and', TokenType.AND);
    this.#keywords.set('class', TokenType.CLASS);
    this.#keywords.set('colon', TokenType.COLON);
    this.#keywords.set('const', TokenType.CONST);
    this.#keywords.set('constructor', TokenType.CONSTRUCTOR);
    this.#keywords.set('else', TokenType.ELSE);
    this.#keywords.set('enum', TokenType.ENUM);
    this.#keywords.set('false', TokenType.FALSE);
    this.#keywords.set('float', TokenType.FLOAT);
    this.#keywords.set('for', TokenType.FOR);
    this.#keywords.set('func', TokenType.FUNC);
    this.#keywords.set('if', TokenType.IF);
    this.#keywords.set('import', TokenType.IMPORT);
    this.#keywords.set('method', TokenType.METHOD);
    this.#keywords.set('null', TokenType.NULL);
    this.#keywords.set('or', TokenType.OR);
    this.#keywords.set('print', TokenType.PRINT);
    this.#keywords.set('return', TokenType.RETURN);
    this.#keywords.set('super', TokenType.SUPER);
    this.#keywords.set('this', TokenType.THIS);
    this.#keywords.set('true', TokenType.TRUE);
    this.#keywords.set('var', TokenType.VAR);
    this.#keywords.set('while', TokenType.WHILE);
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

  #isDigit(char) {
    return char >= '0' && char <= '9';
  }

  #peekNext() {
    const nextCharPosition = this.#current + 1;

    if (nextCharPosition >= this.source.length) {
      return '\0';
    }

    return this.source.charAt(nextCharPosition);
  }

  #number() {
    let currentChar = this.#peek();

    while (this.#isDigit(currentChar)) {
      this.#advance();
      currentChar = this.#peek();
    }

    const isFloatingPointNumber = this.#peek() === '.' &&
                                      this.#isDigit(this.#peekNext());

    if (isFloatingPointNumber) {
      this.#advance();
      currentChar = this.#peek();

      while (this.#isDigit(currentChar)) {
        this.#advance();
        currentChar = this.#peek();
      }
    }

    const numberStr = this.source.substring(this.#start, this.#current);
    this.#addToken(TokenType.NUMBER, parseFloat(numberStr));
  }

  #isAlpha(char) {
    const isLowerCaseChar = char >= 'a' && char <= 'z';
    const isUpperCaseChar = char >= 'A' && char <= 'Z';
    const isUnderscore = char === '_';

    return (isLowerCaseChar || isUpperCaseChar || isUnderscore);
  }

  #isAlphaNumeric(char) {
    return this.#isAlpha(char) || this.#isDigit(char);
  }

  #identifier() {
    while (this.#isAlphaNumeric(this.#peek())) {
      this.#advance();
    }

    const string = this.source.substring(this.#start, this.#current);

    if (this.#keywords.has(string)) {
      const type = this.#keywords.get(string);
      this.#addToken(type);
    } else {
      this.#addToken(TokenType.INDENTIFIER);
    }
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

      case ':': {
        this.#addToken(TokenType.COLON);
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
        if (this.#isDigit(currentChar)) {
          this.#number();
        } else if (this.#isAlpha(currentChar)) {
          this.#identifier();
        } else {
          Meda.error(this.#line, 'Unexpected string.');
        }
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
