const path = require('path');
// test_heal_nest.js — NEST-1 healCrossedLine 单元测试（node 直接提取 editor.html HEAL 段）
const fs = require('fs');
const s = fs.readFileSync(path.join(__dirname, '..', 'src', 'editor.html'), 'utf8');
const a = s.indexOf('var HEAL_TOKENS');
const b = s.indexOf('/* 整块自愈');
if (a < 0 || b < 0 || b <= a) { console.log('EXTRACT FAIL'); process.exit(1); }
const code = s.slice(a, b);
eval(code);

let pass = 0, fail = 0;
function eq(name, input, expect) {
  const out = healCrossedLine(input);
  if (out === expect) { pass++; console.log('PASS ' + name); }
  else { fail++; console.log('FAIL ' + name + '\n  in: ' + JSON.stringify(input) + '\n  got: ' + JSON.stringify(out) + '\n  exp: ' + JSON.stringify(expect)); }
}
// 交叉态重排
eq('cross-u-empty', '==<u>x==</u>', '==<u>x</u>==');
eq('cross-u-tail', '==<u>ab==cd</u>', '==<u>ab</u>==<u>cd</u>');
eq('cross-strong-mark', '==**x==**', '==**x**==');
eq('cross-mark-strong-tail', '==**ab==cd**', '==**ab**==**cd**');
eq('cross-fmt7case', '**~~已加粗**和普通~~', '**~~已加粗~~**~~和普通~~');
eq('cross-u-strong', '<u>**x</u>**', '<u>**x**</u>');
eq('cross-ins', '==<ins>x==</ins>', '==<ins>x</ins>==');
// 合法嵌套 / 普通内容不动
eq('valid-nest', '==<u>x</u>==', '==<u>x</u>==');
eq('valid-plain', '==ab==', '==ab==');
eq('valid-plain2', '**a** ~~b~~ ==c==', '**a** ~~b~~ ==c==');
eq('valid-unclosed', '==abc', '==abc');
eq('valid-single-char', '3*4*5 snake_case a~b', '3*4*5 snake_case a~b');
eq('valid-u', '<u>a</u>', '<u>a</u>');
eq('valid-ins', '<ins>x</ins>', '<ins>x</ins>');
eq('valid-run4', '====', '====');
eq('valid-run6', '******', '******');
eq('valid-code-mask', '`==<u>x==</u>`', '`==<u>x==</u>`');
eq('valid-nested-deep', '**a ~~b ==c== ~~**', '**a ~~b ==c== ~~**');
eq('empty', '', '');
eq('dangling-close', 'a== b', 'a== b');
eq('dangling-uclose', 'x</u>y', 'x</u>y');
// 级联交叉（重开按后继闭合符位置降序，紧邻残对剪枝）
eq('cascade', '==<u>**x==</u>**', '==<u>**x**</u>==');
console.log('---');
console.log('PASS=' + pass + ' FAIL=' + fail);
process.exit(fail ? 1 : 0);
