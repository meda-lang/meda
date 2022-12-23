/*
 * ATTENTION: The "eval" devtool has been used (maybe by default in mode: "development").
 * This devtool is neither made for production nor for readable output files.
 * It uses "eval()" calls to create a separate source file in the browser devtools.
 * If you are trying to read the output file, select a different devtool (https://webpack.js.org/configuration/devtool/)
 * or disable the default devtool with "devtool: false".
 * If you are looking for production-ready output files, see mode: "production" (https://webpack.js.org/configuration/mode/).
 */
/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/******/ 	var __webpack_modules__ = ({

/***/ "./src/index.js":
/*!**********************!*\
  !*** ./src/index.js ***!
  \**********************/
/***/ ((__unused_webpack_module, __webpack_exports__, __webpack_require__) => {

eval("__webpack_require__.r(__webpack_exports__);\n/* harmony import */ var _meda_js__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! ./meda.js */ \"./src/meda.js\");\n\nnew _meda_js__WEBPACK_IMPORTED_MODULE_0__[\"default\"]();\n\n//# sourceURL=webpack://meda-lang/./src/index.js?");

/***/ }),

/***/ "./src/meda.js":
/*!*********************!*\
  !*** ./src/meda.js ***!
  \*********************/
/***/ ((__unused_webpack_module, __webpack_exports__, __webpack_require__) => {

eval("__webpack_require__.r(__webpack_exports__);\n/* harmony export */ __webpack_require__.d(__webpack_exports__, {\n/* harmony export */   \"default\": () => (/* binding */ Meda)\n/* harmony export */ });\n/* harmony import */ var os__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! os */ \"os\");\n/* harmony import */ var os__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(os__WEBPACK_IMPORTED_MODULE_0__);\n/* harmony import */ var fs__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! fs */ \"fs\");\n/* harmony import */ var fs__WEBPACK_IMPORTED_MODULE_1___default = /*#__PURE__*/__webpack_require__.n(fs__WEBPACK_IMPORTED_MODULE_1__);\n/* harmony import */ var path__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! path */ \"path\");\n/* harmony import */ var path__WEBPACK_IMPORTED_MODULE_2___default = /*#__PURE__*/__webpack_require__.n(path__WEBPACK_IMPORTED_MODULE_2__);\n/* harmony import */ var readline__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! readline */ \"readline\");\n/* harmony import */ var readline__WEBPACK_IMPORTED_MODULE_3___default = /*#__PURE__*/__webpack_require__.n(readline__WEBPACK_IMPORTED_MODULE_3__);\n/* harmony import */ var _shared_constants_js__WEBPACK_IMPORTED_MODULE_4__ = __webpack_require__(/*! ./shared/constants.js */ \"./src/shared/constants.js\");\n/* harmony import */ var _scanner_js__WEBPACK_IMPORTED_MODULE_5__ = __webpack_require__(/*! ./scanner.js */ \"./src/scanner.js\");\nfunction _typeof(obj) { \"@babel/helpers - typeof\"; return _typeof = \"function\" == typeof Symbol && \"symbol\" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && \"function\" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? \"symbol\" : typeof obj; }, _typeof(obj); }\nfunction _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError(\"Cannot call a class as a function\"); } }\nfunction _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if (\"value\" in descriptor) descriptor.writable = true; Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor); } }\nfunction _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); Object.defineProperty(Constructor, \"prototype\", { writable: false }); return Constructor; }\nfunction _toPropertyKey(arg) { var key = _toPrimitive(arg, \"string\"); return _typeof(key) === \"symbol\" ? key : String(key); }\nfunction _toPrimitive(input, hint) { if (_typeof(input) !== \"object\" || input === null) return input; var prim = input[Symbol.toPrimitive]; if (prim !== undefined) { var res = prim.call(input, hint || \"default\"); if (_typeof(res) !== \"object\") return res; throw new TypeError(\"@@toPrimitive must return a primitive value.\"); } return (hint === \"string\" ? String : Number)(input); }\nfunction _classStaticPrivateFieldSpecGet(receiver, classConstructor, descriptor) { _classCheckPrivateStaticAccess(receiver, classConstructor); _classCheckPrivateStaticFieldDescriptor(descriptor, \"get\"); return _classApplyDescriptorGet(receiver, descriptor); }\nfunction _classApplyDescriptorGet(receiver, descriptor) { if (descriptor.get) { return descriptor.get.call(receiver); } return descriptor.value; }\nfunction _classStaticPrivateMethodGet(receiver, classConstructor, method) { _classCheckPrivateStaticAccess(receiver, classConstructor); return method; }\nfunction _classStaticPrivateFieldSpecSet(receiver, classConstructor, descriptor, value) { _classCheckPrivateStaticAccess(receiver, classConstructor); _classCheckPrivateStaticFieldDescriptor(descriptor, \"set\"); _classApplyDescriptorSet(receiver, descriptor, value); return value; }\nfunction _classCheckPrivateStaticFieldDescriptor(descriptor, action) { if (descriptor === undefined) { throw new TypeError(\"attempted to \" + action + \" private static field before its declaration\"); } }\nfunction _classCheckPrivateStaticAccess(receiver, classConstructor) { if (receiver !== classConstructor) { throw new TypeError(\"Private static access of wrong provenance\"); } }\nfunction _classApplyDescriptorSet(receiver, descriptor, value) { if (descriptor.set) { descriptor.set.call(receiver, value); } else { if (!descriptor.writable) { throw new TypeError(\"attempted to set read only private field\"); } descriptor.value = value; } }\n\n\n\n\n\n\nvar Meda = /*#__PURE__*/function () {\n  function Meda() {\n    _classCallCheck(this, Meda);\n    Meda.main();\n  }\n  _createClass(Meda, null, [{\n    key: \"error\",\n    value: function error(line, message) {\n      _classStaticPrivateMethodGet(this, Meda, _report).call(this, line, '', message);\n    }\n  }, {\n    key: \"run\",\n    value: function run(source) {\n      // const tokens = source.split(' ');\n\n      // tokens.forEach((token) => {\n      //   console.log(token);\n      // });\n\n      // here for testing\n      var s = new _scanner_js__WEBPACK_IMPORTED_MODULE_5__[\"default\"](source);\n      console.log(s.scanTokens());\n    }\n  }, {\n    key: \"runPrompt\",\n    value: function runPrompt() {\n      var _this = this;\n      console.log(_shared_constants_js__WEBPACK_IMPORTED_MODULE_4__[\"default\"].Strings.Repl.WELCOME_MESSAGE);\n      var rl = readline__WEBPACK_IMPORTED_MODULE_3___default().createInterface({\n        input: process.stdin,\n        output: process.stdout\n      });\n      rl.setPrompt(_shared_constants_js__WEBPACK_IMPORTED_MODULE_4__[\"default\"].Strings.Repl.PROMPT);\n      rl.prompt();\n      rl.on('line', function (line) {\n        var isLineEmpty = line === null || line === '';\n        if (isLineEmpty) {\n          console.log(_shared_constants_js__WEBPACK_IMPORTED_MODULE_4__[\"default\"].Strings.Repl.EXIT_MESSAGE);\n          process.exit(_shared_constants_js__WEBPACK_IMPORTED_MODULE_4__[\"default\"].ExitCodes.NORMAL);\n        }\n        _this.run(line);\n        _classStaticPrivateFieldSpecSet(_this, Meda, _hadError, false);\n        rl.prompt();\n      }).on('close', function () {\n        console.log(_shared_constants_js__WEBPACK_IMPORTED_MODULE_4__[\"default\"].Strings.Repl.EXIT_MESSAGE);\n        process.exit(_shared_constants_js__WEBPACK_IMPORTED_MODULE_4__[\"default\"].ExitCodes.NORMAL);\n      });\n    }\n  }, {\n    key: \"runFile\",\n    value: function runFile(filePathStr) {\n      var filePath = path__WEBPACK_IMPORTED_MODULE_2___default().basename(filePathStr);\n      try {\n        var source = fs__WEBPACK_IMPORTED_MODULE_1___default().readFileSync(filePath, {\n          encoding: _shared_constants_js__WEBPACK_IMPORTED_MODULE_4__[\"default\"].DEFAULT_CHAR_SET,\n          flag: 'r'\n        });\n        if (_classStaticPrivateFieldSpecGet(this, Meda, _hadError)) process.exit((os__WEBPACK_IMPORTED_MODULE_0___default().constants.errno.ENOENT));\n        this.run(source);\n      } catch (err) {\n        console.error(err);\n        process.exit((os__WEBPACK_IMPORTED_MODULE_0___default().constants.errno.ENOENT));\n      }\n    }\n  }, {\n    key: \"main\",\n    value: function main() {\n      var isTooManyArgs = process.argv.length > 3;\n      var isFilenameInputted = process.argv.length === 3;\n      var filenameIndex = 2;\n      if (isTooManyArgs) {\n        console.log(_shared_constants_js__WEBPACK_IMPORTED_MODULE_4__[\"default\"].ErrorMessages.E2BIG);\n        process.exit((os__WEBPACK_IMPORTED_MODULE_0___default().constants.errno.E2BIG));\n      } else if (isFilenameInputted) {\n        var filePath = process.argv[filenameIndex];\n        this.runFile(filePath);\n      } else {\n        this.runPrompt();\n      }\n    }\n  }]);\n  return Meda;\n}();\nfunction _report(line, where, message) {\n  console.log(\"[line \".concat(line, \"] Error \").concat(where, \": \").concat(message));\n  _classStaticPrivateFieldSpecSet(this, Meda, _hadError, true);\n}\nvar _hadError = {\n  writable: true,\n  value: false\n};\n\n\n//# sourceURL=webpack://meda-lang/./src/meda.js?");

/***/ }),

/***/ "./src/scanner.js":
/*!************************!*\
  !*** ./src/scanner.js ***!
  \************************/
/***/ ((__unused_webpack_module, __webpack_exports__, __webpack_require__) => {

eval("__webpack_require__.r(__webpack_exports__);\n/* harmony export */ __webpack_require__.d(__webpack_exports__, {\n/* harmony export */   \"default\": () => (/* binding */ Scanner)\n/* harmony export */ });\n/* harmony import */ var _token_js__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! ./token.js */ \"./src/token.js\");\n/* harmony import */ var _token_type_js__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! ./token_type.js */ \"./src/token_type.js\");\n/* harmony import */ var _meda_js__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! ./meda.js */ \"./src/meda.js\");\nfunction _typeof(obj) { \"@babel/helpers - typeof\"; return _typeof = \"function\" == typeof Symbol && \"symbol\" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && \"function\" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? \"symbol\" : typeof obj; }, _typeof(obj); }\nfunction _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError(\"Cannot call a class as a function\"); } }\nfunction _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if (\"value\" in descriptor) descriptor.writable = true; Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor); } }\nfunction _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); Object.defineProperty(Constructor, \"prototype\", { writable: false }); return Constructor; }\nfunction _classPrivateMethodInitSpec(obj, privateSet) { _checkPrivateRedeclaration(obj, privateSet); privateSet.add(obj); }\nfunction _classPrivateFieldInitSpec(obj, privateMap, value) { _checkPrivateRedeclaration(obj, privateMap); privateMap.set(obj, value); }\nfunction _checkPrivateRedeclaration(obj, privateCollection) { if (privateCollection.has(obj)) { throw new TypeError(\"Cannot initialize the same private elements twice on an object\"); } }\nfunction _defineProperty(obj, key, value) { key = _toPropertyKey(key); if (key in obj) { Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true }); } else { obj[key] = value; } return obj; }\nfunction _toPropertyKey(arg) { var key = _toPrimitive(arg, \"string\"); return _typeof(key) === \"symbol\" ? key : String(key); }\nfunction _toPrimitive(input, hint) { if (_typeof(input) !== \"object\" || input === null) return input; var prim = input[Symbol.toPrimitive]; if (prim !== undefined) { var res = prim.call(input, hint || \"default\"); if (_typeof(res) !== \"object\") return res; throw new TypeError(\"@@toPrimitive must return a primitive value.\"); } return (hint === \"string\" ? String : Number)(input); }\nfunction _classPrivateMethodGet(receiver, privateSet, fn) { if (!privateSet.has(receiver)) { throw new TypeError(\"attempted to get private field on non-instance\"); } return fn; }\nfunction _classPrivateFieldSet(receiver, privateMap, value) { var descriptor = _classExtractFieldDescriptor(receiver, privateMap, \"set\"); _classApplyDescriptorSet(receiver, descriptor, value); return value; }\nfunction _classApplyDescriptorSet(receiver, descriptor, value) { if (descriptor.set) { descriptor.set.call(receiver, value); } else { if (!descriptor.writable) { throw new TypeError(\"attempted to set read only private field\"); } descriptor.value = value; } }\nfunction _classPrivateFieldGet(receiver, privateMap) { var descriptor = _classExtractFieldDescriptor(receiver, privateMap, \"get\"); return _classApplyDescriptorGet(receiver, descriptor); }\nfunction _classExtractFieldDescriptor(receiver, privateMap, action) { if (!privateMap.has(receiver)) { throw new TypeError(\"attempted to \" + action + \" private field on non-instance\"); } return privateMap.get(receiver); }\nfunction _classApplyDescriptorGet(receiver, descriptor) { if (descriptor.get) { return descriptor.get.call(receiver); } return descriptor.value; }\n\n\n\nvar _start = /*#__PURE__*/new WeakMap();\nvar _current = /*#__PURE__*/new WeakMap();\nvar _line = /*#__PURE__*/new WeakMap();\nvar _addToken = /*#__PURE__*/new WeakSet();\nvar _advance = /*#__PURE__*/new WeakSet();\nvar _peek = /*#__PURE__*/new WeakSet();\nvar _match = /*#__PURE__*/new WeakSet();\nvar _string = /*#__PURE__*/new WeakSet();\nvar _isAtEnd = /*#__PURE__*/new WeakSet();\nvar Scanner = /*#__PURE__*/function () {\n  function Scanner(source) {\n    _classCallCheck(this, Scanner);\n    _classPrivateMethodInitSpec(this, _isAtEnd);\n    _classPrivateMethodInitSpec(this, _string);\n    _classPrivateMethodInitSpec(this, _match);\n    _classPrivateMethodInitSpec(this, _peek);\n    _classPrivateMethodInitSpec(this, _advance);\n    _classPrivateMethodInitSpec(this, _addToken);\n    _defineProperty(this, \"source\", '');\n    _defineProperty(this, \"tokens\", []);\n    _classPrivateFieldInitSpec(this, _start, {\n      writable: true,\n      value: 0\n    });\n    _classPrivateFieldInitSpec(this, _current, {\n      writable: true,\n      value: 0\n    });\n    _classPrivateFieldInitSpec(this, _line, {\n      writable: true,\n      value: 1\n    });\n    this.source = source;\n  }\n  _createClass(Scanner, [{\n    key: \"scanToken\",\n    value: function scanToken() {\n      var currentChar = _classPrivateMethodGet(this, _advance, _advance2).call(this);\n      switch (currentChar) {\n        case '(':\n          {\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.LEFT_PAREN);\n            break;\n          }\n        case ')':\n          {\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.RIGHT_PAREN);\n            break;\n          }\n        case '{':\n          {\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.LEFT_BRACE);\n            break;\n          }\n        case '}':\n          {\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.RIGHT_BRACE);\n            break;\n          }\n        case ',':\n          {\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.COMMA);\n            break;\n          }\n        case '.':\n          {\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.DOT);\n            break;\n          }\n        case '-':\n          {\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.MINUS);\n            break;\n          }\n        case '+':\n          {\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.PLUS);\n            break;\n          }\n        case ';':\n          {\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.SEMICOLON);\n            break;\n          }\n        case '*':\n          {\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.STAR);\n            break;\n          }\n        case '!':\n          {\n            var newToken = _classPrivateMethodGet(this, _match, _match2).call(this, '=') ? _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.BANG_EQUAL : _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.BANG;\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, newToken);\n            break;\n          }\n        case '=':\n          {\n            var _newToken = _classPrivateMethodGet(this, _match, _match2).call(this, '=') ? _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.EQUAL_EQUAL : _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.EQUAL;\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _newToken);\n            break;\n          }\n        case '<':\n          {\n            var _newToken2 = _classPrivateMethodGet(this, _match, _match2).call(this, '=') ? _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.LESS_EQUAL : _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.LESS;\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _newToken2);\n            break;\n          }\n        case '>':\n          {\n            var _newToken3 = _classPrivateMethodGet(this, _match, _match2).call(this, '=') ? _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.GREATER_EQUAL : _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.GREATER;\n            _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _newToken3);\n            break;\n          }\n        case '/':\n          {\n            if (_classPrivateMethodGet(this, _match, _match2).call(this, '/')) {\n              while (_classPrivateMethodGet(this, _peek, _peek2).call(this) != '\\n' && !_classPrivateMethodGet(this, _isAtEnd, _isAtEnd2).call(this)) _classPrivateMethodGet(this, _advance, _advance2).call(this);\n            } else {\n              _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.SLASH);\n            }\n            break;\n          }\n        case ' ':\n          {\n            break;\n          }\n        case '\\r':\n          {\n            break;\n          }\n        case '\\t':\n          {\n            break;\n          }\n        case '\\n':\n          {\n            var _this$line, _this$line2;\n            _classPrivateFieldSet(this, _line, (_this$line = _classPrivateFieldGet(this, _line), _this$line2 = _this$line++, _this$line)), _this$line2;\n            break;\n          }\n        case '\\'':\n          {\n            _classPrivateMethodGet(this, _string, _string2).call(this);\n            break;\n          }\n        default:\n          {\n            _meda_js__WEBPACK_IMPORTED_MODULE_2__[\"default\"].error(_classPrivateFieldGet(this, _line), 'Unexpected string.');\n            break;\n          }\n      }\n    }\n  }, {\n    key: \"scanTokens\",\n    value: function scanTokens() {\n      while (!_classPrivateMethodGet(this, _isAtEnd, _isAtEnd2).call(this)) {\n        _classPrivateFieldSet(this, _start, _classPrivateFieldGet(this, _current));\n        this.scanToken();\n      }\n      this.tokens.push(new _token_js__WEBPACK_IMPORTED_MODULE_0__.Token(_token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.EOF, '', null, _classPrivateFieldGet(this, _line)));\n      return this.tokens;\n    }\n  }]);\n  return Scanner;\n}();\nfunction _addToken2(type) {\n  var literal = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : null;\n  var text = this.source.substring(_classPrivateFieldGet(this, _start), _classPrivateFieldGet(this, _current));\n  this.tokens.push(new _token_js__WEBPACK_IMPORTED_MODULE_0__.Token(type, text, literal, _classPrivateFieldGet(this, _line)));\n}\nfunction _advance2() {\n  var _this$current, _this$current2;\n  return this.source[(_classPrivateFieldSet(this, _current, (_this$current = _classPrivateFieldGet(this, _current), _this$current2 = _this$current++, _this$current)), _this$current2)];\n}\nfunction _peek2() {\n  if (_classPrivateMethodGet(this, _isAtEnd, _isAtEnd2).call(this)) return '\\0';\n  return this.source.charAt(_classPrivateFieldGet(this, _current));\n}\nfunction _match2(expected) {\n  var _this$current3, _this$current4;\n  if (_classPrivateMethodGet(this, _isAtEnd, _isAtEnd2).call(this)) return false;\n  if (_classPrivateMethodGet(this, _peek, _peek2).call(this) != expected) return false;\n  _classPrivateFieldSet(this, _current, (_this$current3 = _classPrivateFieldGet(this, _current), _this$current4 = _this$current3++, _this$current3)), _this$current4;\n  return true;\n}\nfunction _string2() {\n  while (_classPrivateMethodGet(this, _peek, _peek2).call(this) !== '\\'' && !_classPrivateMethodGet(this, _isAtEnd, _isAtEnd2).call(this)) {\n    if (_classPrivateMethodGet(this, _peek, _peek2).call(this) === '\\n') this.line++;\n    _classPrivateMethodGet(this, _advance, _advance2).call(this);\n  }\n  if (_classPrivateMethodGet(this, _isAtEnd, _isAtEnd2).call(this)) {\n    _meda_js__WEBPACK_IMPORTED_MODULE_2__[\"default\"].error(_classPrivateFieldGet(this, _line), 'Unterminated string.');\n    return;\n  }\n  _classPrivateMethodGet(this, _advance, _advance2).call(this);\n  var value = this.source.substring(_classPrivateFieldGet(this, _start) + 1, _classPrivateFieldGet(this, _current) - 1);\n  _classPrivateMethodGet(this, _addToken, _addToken2).call(this, _token_type_js__WEBPACK_IMPORTED_MODULE_1__.TokenType.STRING, value);\n}\nfunction _isAtEnd2() {\n  return _classPrivateFieldGet(this, _current) >= this.source.length;\n}\n\n\n//# sourceURL=webpack://meda-lang/./src/scanner.js?");

/***/ }),

/***/ "./src/shared/constants.js":
/*!*********************************!*\
  !*** ./src/shared/constants.js ***!
  \*********************************/
/***/ ((__unused_webpack_module, __webpack_exports__, __webpack_require__) => {

eval("__webpack_require__.r(__webpack_exports__);\n/* harmony export */ __webpack_require__.d(__webpack_exports__, {\n/* harmony export */   \"default\": () => (__WEBPACK_DEFAULT_EXPORT__)\n/* harmony export */ });\nvar constants = {\n  ExitCodes: {\n    NORMAL: 0\n  },\n  Strings: {\n    Repl: {\n      WELCOME_MESSAGE: 'Meda 0.1.0 (December 22, 2022)',\n      PROMPT: '>>> ',\n      EXIT_MESSAGE: 'Have a great day :)'\n    }\n  },\n  ErrorMessages: {\n    E2BIG: 'Usage: meda [script]'\n  },\n  DEFAULT_CHAR_SET: 'utf-8'\n};\n/* harmony default export */ const __WEBPACK_DEFAULT_EXPORT__ = (constants);\n\n//# sourceURL=webpack://meda-lang/./src/shared/constants.js?");

/***/ }),

/***/ "./src/token.js":
/*!**********************!*\
  !*** ./src/token.js ***!
  \**********************/
/***/ ((__unused_webpack_module, __webpack_exports__, __webpack_require__) => {

eval("__webpack_require__.r(__webpack_exports__);\n/* harmony export */ __webpack_require__.d(__webpack_exports__, {\n/* harmony export */   \"Token\": () => (/* binding */ Token)\n/* harmony export */ });\nfunction _typeof(obj) { \"@babel/helpers - typeof\"; return _typeof = \"function\" == typeof Symbol && \"symbol\" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && \"function\" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? \"symbol\" : typeof obj; }, _typeof(obj); }\nfunction _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError(\"Cannot call a class as a function\"); } }\nfunction _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if (\"value\" in descriptor) descriptor.writable = true; Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor); } }\nfunction _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); Object.defineProperty(Constructor, \"prototype\", { writable: false }); return Constructor; }\nfunction _defineProperty(obj, key, value) { key = _toPropertyKey(key); if (key in obj) { Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true }); } else { obj[key] = value; } return obj; }\nfunction _toPropertyKey(arg) { var key = _toPrimitive(arg, \"string\"); return _typeof(key) === \"symbol\" ? key : String(key); }\nfunction _toPrimitive(input, hint) { if (_typeof(input) !== \"object\" || input === null) return input; var prim = input[Symbol.toPrimitive]; if (prim !== undefined) { var res = prim.call(input, hint || \"default\"); if (_typeof(res) !== \"object\") return res; throw new TypeError(\"@@toPrimitive must return a primitive value.\"); } return (hint === \"string\" ? String : Number)(input); }\nvar Token = /*#__PURE__*/function () {\n  function Token(type, lexeme, literal, line) {\n    _classCallCheck(this, Token);\n    _defineProperty(this, \"type\", null);\n    _defineProperty(this, \"lexeme\", '');\n    _defineProperty(this, \"literal\", null);\n    _defineProperty(this, \"line\", null);\n    this.type = type;\n    this.lexeme = lexeme;\n    this.literal = literal;\n    this.line = line;\n  }\n  _createClass(Token, [{\n    key: \"toString\",\n    value: function toString() {\n      return this.type + ' ' + this.lexeme + ' ' + this.literal;\n    }\n  }]);\n  return Token;\n}();\n\n//# sourceURL=webpack://meda-lang/./src/token.js?");

/***/ }),

/***/ "./src/token_type.js":
/*!***************************!*\
  !*** ./src/token_type.js ***!
  \***************************/
/***/ ((__unused_webpack_module, __webpack_exports__, __webpack_require__) => {

eval("__webpack_require__.r(__webpack_exports__);\n/* harmony export */ __webpack_require__.d(__webpack_exports__, {\n/* harmony export */   \"TokenType\": () => (/* binding */ TokenType)\n/* harmony export */ });\nvar TokenType = Object.freeze({\n  // Single-character tokens.\n  LEFT_PAREN: Symbol('LEFT_PAREN'),\n  RIGHT_PAREN: Symbol('RIGHT_PAREN'),\n  LEFT_BRACE: Symbol('LEFT_BRACE'),\n  RIGHT_BRACE: Symbol('RIGHT_BRACE'),\n  LEFT_BRACKET: Symbol('LEFT_BRACKET'),\n  RIGHT_BRACKET: Symbol('RIGHT_BRACKET'),\n  COMMA: Symbol('COMMA'),\n  DOT: Symbol('DOT'),\n  MINUS: Symbol('MINUS'),\n  PLUS: Symbol('PLUS'),\n  SEMICOLON: Symbol('SEMICOLON'),\n  SLASH: Symbol('SLASH'),\n  STAR: Symbol('STAR'),\n  // One or two character tokens.\n  BANG: Symbol('BANG'),\n  BANG_EQUAL: Symbol('BANG_EQUAL'),\n  EQUAL: Symbol('EQUAL'),\n  EQUAL_EQUAL: Symbol('EQUAL_EQUAL'),\n  GREATER: Symbol('GREATER'),\n  GREATER_EQUAL: Symbol('GREATER_EQUAL'),\n  LESS: Symbol('LESS'),\n  LESS_EQUAL: Symbol('LESS_EQUAL'),\n  // Literals\n  INDENTIFIER: Symbol('INDENTIFIER'),\n  STRING: Symbol('STRING'),\n  NUMBER: Symbol('NUMBER'),\n  // Keywords\n  AND: Symbol('AND'),\n  CLASS: Symbol('CLASS'),\n  CONSTRUCTOR: Symbol('CONSTRUCTOR'),\n  ELSE: Symbol('ELSE'),\n  FALSE: Symbol('FALSE'),\n  FN: Symbol('FN'),\n  FOR: Symbol('FOR'),\n  IF: Symbol('IF'),\n  IS: Symbol('IS'),\n  NIL: Symbol('NIL'),\n  OR: Symbol('OR'),\n  PRINT: Symbol('PRINT'),\n  EOF: Symbol('EOF')\n});\n\n//# sourceURL=webpack://meda-lang/./src/token_type.js?");

/***/ }),

/***/ "fs":
/*!*********************!*\
  !*** external "fs" ***!
  \*********************/
/***/ ((module) => {

module.exports = require("fs");

/***/ }),

/***/ "os":
/*!*********************!*\
  !*** external "os" ***!
  \*********************/
/***/ ((module) => {

module.exports = require("os");

/***/ }),

/***/ "path":
/*!***********************!*\
  !*** external "path" ***!
  \***********************/
/***/ ((module) => {

module.exports = require("path");

/***/ }),

/***/ "readline":
/*!***************************!*\
  !*** external "readline" ***!
  \***************************/
/***/ ((module) => {

module.exports = require("readline");

/***/ })

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	var __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/ 		// Check if module is in cache
/******/ 		var cachedModule = __webpack_module_cache__[moduleId];
/******/ 		if (cachedModule !== undefined) {
/******/ 			return cachedModule.exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = __webpack_module_cache__[moduleId] = {
/******/ 			// no module.id needed
/******/ 			// no module.loaded needed
/******/ 			exports: {}
/******/ 		};
/******/ 	
/******/ 		// Execute the module function
/******/ 		__webpack_modules__[moduleId](module, module.exports, __webpack_require__);
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/************************************************************************/
/******/ 	/* webpack/runtime/compat get default export */
/******/ 	(() => {
/******/ 		// getDefaultExport function for compatibility with non-harmony modules
/******/ 		__webpack_require__.n = (module) => {
/******/ 			var getter = module && module.__esModule ?
/******/ 				() => (module['default']) :
/******/ 				() => (module);
/******/ 			__webpack_require__.d(getter, { a: getter });
/******/ 			return getter;
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/define property getters */
/******/ 	(() => {
/******/ 		// define getter functions for harmony exports
/******/ 		__webpack_require__.d = (exports, definition) => {
/******/ 			for(var key in definition) {
/******/ 				if(__webpack_require__.o(definition, key) && !__webpack_require__.o(exports, key)) {
/******/ 					Object.defineProperty(exports, key, { enumerable: true, get: definition[key] });
/******/ 				}
/******/ 			}
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/hasOwnProperty shorthand */
/******/ 	(() => {
/******/ 		__webpack_require__.o = (obj, prop) => (Object.prototype.hasOwnProperty.call(obj, prop))
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/make namespace object */
/******/ 	(() => {
/******/ 		// define __esModule on exports
/******/ 		__webpack_require__.r = (exports) => {
/******/ 			if(typeof Symbol !== 'undefined' && Symbol.toStringTag) {
/******/ 				Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });
/******/ 			}
/******/ 			Object.defineProperty(exports, '__esModule', { value: true });
/******/ 		};
/******/ 	})();
/******/ 	
/************************************************************************/
/******/ 	
/******/ 	// startup
/******/ 	// Load entry module and return exports
/******/ 	// This entry module can't be inlined because the eval devtool is used.
/******/ 	var __webpack_exports__ = __webpack_require__("./src/index.js");
/******/ 	
/******/ })()
;