import {strictEqual} from 'assert';
import Meda from '../src/meda.js';

describe(`Meda class test suite`, () => {
  it(`should create an instance`, () => {
    strictEqual(typeof new Meda, 'object');
  });
});
