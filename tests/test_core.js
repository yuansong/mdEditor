// editor core smoke tests (run with node)
const fs = require('fs');
const html = fs.readFileSync(__dirname + '/../src/editor.html', 'utf8');
// v3.44.10：editor.html 现含多个内联 script（dual 模式小段 + 内核主 IIFE），
// 旧贪婪正则 /<script>[\s\S]*<\/script>/ 会把中间的 HTML 一并 eval 而语法报错；
// 改为提取所有无属性 script 块、取最长者（内核主块 ~64 万字符）。
const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const code = blocks.sort((a, b) => b.length - a.length)[0];
if (!code) { console.error('FAIL: script tag not found'); process.exit(1); }

// minimal DOM stubs so the IIFE can load
function fakeEl() {
  var el = { className: '', innerHTML: '', textContent: '', children: [],
    appendChild() {}, removeChild() {}, replaceChild() {},
    addEventListener() {}, setAttribute() {}, querySelector: () => null,
    querySelectorAll: () => [] };   // v3.32：欢迎内容含列表/引用，块增强会遍历子元素
  el.classList = {
    add: function (c) { if (el.className.split(/\s+/).indexOf(c) === -1) el.className += ' ' + c; },
    remove: function (c) { el.className = el.className.split(/\s+/).filter(function (x) { return x !== c; }).join(' '); },
    contains: function (c) { return el.className.split(/\s+/).indexOf(c) !== -1; },
    toggle: function (c, on) { if (on) el.classList.add(c); else el.classList.remove(c); }
  };
  return el;
}
global.document = {
  getElementById: () => fakeEl(),
  createElement: () => fakeEl(),
  addEventListener: () => {},
};
global.window = global;
global.NodeFilter = { SHOW_TEXT: 1, SHOW_ELEMENT: 2 };
global.getSelection = () => ({ rangeCount: 0 });

eval(code);
const core = window.__core;

let fails = 0;
function eq(actual, expected, name) {
  const a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a === e) console.log('ok  -', name);
  else { fails++; console.log('FAIL-', name, '\n  expected:', e, '\n  actual  :', a); }
}

// ---- splitBlocks ----
eq(core.splitBlocks('# a\n\nb\n\nc'), ['# a', 'b', 'c'], 'split: paragraphs by blank line');
eq(core.splitBlocks('# a\n- x\n- y'), ['# a', '- x\n- y'], 'split: heading then list');
eq(core.splitBlocks('```\nline1\n\nline2\n```'), ['```\nline1\n\nline2\n```'], 'split: fence keeps blank line');
eq(core.splitBlocks('> q1\n> q2\n\ntext'), ['> q1\n> q2', 'text'], 'split: quote block');
eq(core.splitBlocks('| a | b |\n| --- | --- |\n| 1 | 2 |\n\nnext'), ['| a | b |\n| --- | --- |\n| 1 | 2 |', 'next'], 'split: table');
eq(core.splitBlocks(''), [''], 'split: empty');
eq(core.splitBlocks('a\r\n\r\nb'), ['a', 'b'], 'split: CRLF');

// ---- blockInfo ----
eq(core.blockInfo('# t').type, 'h1', 'info: h1');
eq(core.blockInfo('###### t').type, 'h6', 'info: h6');
eq(core.blockInfo('- item').type, 'list', 'info: list');
eq(core.blockInfo('1. item').type, 'list', 'info: ordered list');
eq(core.blockInfo('```js\ncode\n```').type, 'fence', 'info: fence');
eq(core.blockInfo('---').type, 'hr', 'info: hr');
eq(core.blockInfo('> q').type, 'quote', 'info: quote');
eq(core.blockInfo('| a |\n| - |').type, 'table', 'info: table');
eq(core.blockInfo('plain').type, 'p', 'info: paragraph');

// ---- blockHTML ----
eq(core.blockHTML('# 你好'), '<h1>你好</h1>', 'html: h1');
eq(core.blockHTML('**b** *i*'), '<p><strong>b</strong> <em>i</em></p>', 'html: bold+italic');
eq(core.blockHTML('~~del~~ `c`'), '<p><del>del</del> <code>c</code></p>', 'html: del+code');
eq(core.blockHTML('[x](https://a.b)'), '<p><a href="https://a.b" target="_blank" rel="noopener">x</a></p>', 'html: link');
eq(core.blockHTML('![alt](img.png)'), '<p><img src="img.png" alt="alt"></p>', 'html: image');
eq(core.blockHTML('<b>&x</b>'), '<p>&lt;b&gt;&amp;x&lt;/b&gt;</p>', 'html: escaping');
eq(core.blockHTML('```py\nprint(1)\n```'), '<pre class="fence" data-lang="py"><code>print(1)\n</code></pre>', 'html: fence');
eq(core.blockHTML('- a\n- b'), '<ul><li>a</li><li>b</li></ul>', 'html: list');
eq(core.blockHTML('- [x] done\n- [ ] todo'), '<ul><li><input type="checkbox" checked>done</li><li><input type="checkbox">todo</li></ul>', 'html: task list');
eq(core.blockHTML('1. one\n2. two'), '<ol><li>one</li><li>two</li></ol>', 'html: ordered list');
eq(core.blockHTML('- a\n  - nested'), '<ul><li>a<ul><li>nested</li></ul></li></ul>', 'html: nested list');
eq(core.blockHTML('> hi'), '<blockquote>hi</blockquote>', 'html: quote');
eq(core.blockHTML('| a | b |\n| --- | :---: |\n| 1 | 2 |'),
   '<table><thead><tr><th>a</th><th style="text-align:center">b</th></tr></thead><tbody><tr><td>1</td><td style="text-align:center">2</td></tr></tbody></table>',
   'html: table');
eq(core.blockHTML('**a `c` b**'), '<p><strong>a <code>c</code> b</strong></p>', 'html: nested code in strong');
// v3.26：***粗斜体***（原先只匹配 **，留下孤立 * 渲染错误）
eq(core.blockHTML('***bi***'), '<p><strong><em>bi</em></strong></p>', 'html: bold+italic ***');
eq(core.blockHTML('as***==fddfa==***dfsf'),
   '<p>as<strong><em><mark>fddfa</mark></em></strong>dfsf</p>', 'html: ***==mark==*** 嵌套');

// ---- caret mapping (plain -> raw) ----
eq(core.mapPlainToRaw('# hello', 5), 7, 'map: heading plain->raw (marker offset)');
eq(core.mapPlainToRaw('abc', 2), 2, 'map: paragraph identity');
eq(core.mapPlainToRaw('```py\ncode', 0), 6, 'map: fence line offset');
eq(core.mapPlainToRaw('> quote', 1), 3, 'map: quote stripped offset');
eq(core.mapPlainToRaw('- item', 0), 2, 'map: list marker offset');

// inline map: bold text plain 'bold' idx 2 -> raw '**bold**' idx 4
eq(core.inlineMap('**bold**', 2), 4, 'map: inside strong skips markers');

// ---- new features ----
eq(core.blockHTML('==高亮=='), '<p><mark>高亮</mark></p>', 'html: mark ==xx==');
eq(core.inlineMap('==ab==', 1), 3, 'map: mark caret offset');
eq(core.blockInfo('---\ntitle: x\n---').type, 'yaml', 'info: yaml front matter');
eq(core.blockInfo('---\ntitle: x\n---\nmore').type, 'yaml', 'info: yaml with trailing');
eq(core.blockInfo('[TOC]').type, 'toc', 'info: toc');
eq(core.splitBlocks('---\ntitle: x\n---\n\n# h'), ['---\ntitle: x\n---', '# h'], 'split: yaml front matter');
eq(core.splitBlocks('[TOC]\n\n# a'), ['[TOC]', '# a'], 'split: toc own block');
eq(core.blockInfo('- a\n---\ntitle: y\n---').type, 'list', 'info: --- not yaml mid-block?');
// hr still works when first line of doc is --- followed by blank (no closing)
eq(core.splitBlocks('---\n\n# h'), ['---', '# h'], 'split: hr at doc start stays hr');

// ---- v3.8 mermaid charts ----
eq(core.blockInfo('```mermaid\nflowchart TD\n A-->B\n```').type, 'fence', 'mmd: fence type');
eq(core.blockInfo('```mermaid\nflowchart TD\n A-->B\n```').lang, 'mermaid', 'mmd: fence lang');
eq(core.blockHTML('```mermaid\nflowchart TD\n A[开始] --> B{判断}\n```'),
  '<div class="mmd-wrap"><div class="mermaidblock" data-src="flowchart TD\n A[开始] --&gt; B{判断}"></div></div>',
  'mmd: rendered as data-src placeholder');
eq(core.blockHTML('```mermaid\n  \n```'),
  '<div class="mmd-wrap"><div class="mermaidblock" data-src="  "></div></div>', 'mmd: empty source still placeholder');
eq(core.splitBlocks('```mermaid\na\n\nb\n```'), ['```mermaid\na\n\nb\n```'],
  'mmd: fence keeps blank line');
eq(core.blockHTML('```mermaid\nx --> y\n```\n').startsWith('<div class="mmd-wrap"><div class="mermaidblock"'), true,
  'mmd: block html prefix');
eq(core.blockHTML('```math\nE=mc^2\n```'), '<div class="mathblock" data-tex="E=mc^2"></div>',
  'mmd: math block unchanged');

// ---- v3.22 围栏属性（图表尺寸 / 图注）----
eq(core.blockInfo('```mermaid w=520 cap="流程图" captop\nx\n```').lang, 'mermaid',
  'v322: 围栏属性不影响 lang 识别');
eq(core.blockInfo('```mermaid w=520 h=300\nx\n```').attrs.w, '520', 'v322: 围栏属性 w');
eq(core.blockInfo('```mermaid w=520 h=300\nx\n```').attrs.h, '300', 'v322: 围栏属性 h');
eq(core.blockInfo('```mermaid cap="含 空格 与 引号"\nx\n```').attrs.cap, '含 空格 与 引号',
  'v322: 围栏属性 cap 支持带空格（引号包裹）');
eq(core.blockInfo('```mermaid w=520 captop\nx\n```').attrs.captop, true, 'v322: 围栏布尔属性 captop');
eq(core.blockInfo('```python\nx\n```').lang, 'python', 'v322: 普通围栏 lang 仍取第一个词');
eq(core.blockHTML('```mermaid w=400 cap="说明"\nx --> y\n```'),
  '<div class="mmd-wrap"><div class="mermaidblock sized" data-src="x --&gt; y" data-mmd-w="400" style="width:400px;"></div>' +
  '<div class="mmd-cap">说明</div></div>', 'v322: 图表宽度 + 下方图注');
eq(core.blockHTML('```mermaid cap="上注" captop\nx --> y\n```')
    .indexOf('<div class="mmd-cap">上注</div><div class="mermaidblock"') !== -1, true, 'v322: 图注渲染在图表上方');
eq(core.fenceInfoLine('mermaid', { w: '520', cap: '说明', captop: true }),
  '```mermaid w=520 cap="说明" captop', 'v322: fenceInfoLine 回写');
eq(core.fenceInfoLine('mermaid', {}), '```mermaid', 'v322: 无属性时围栏首行干净');

// ---- v3.22 HTML 块存储（表格尺寸 / 合并、图片图注）----
const HTBL = '<table class="md-tbl">\n  <thead>\n    <tr><th>a</th></tr>\n  </thead>\n  <tbody>\n    <tr><td>1</td></tr>\n  </tbody>\n</table>';
eq(core.blockInfo(HTBL).type, 'htable', 'v322: HTML 表格块类型识别');
eq(core.blockHTML(HTBL), HTBL, 'v322: HTML 表格原样输出（不做二次转义）');
eq(core.splitBlocks(HTBL), [HTBL], 'v322: HTML 表格整块往返');
const HFIG = '<figure class="md-fig">\n<img src="a.assets/x.png" style="width:320px">\n<figcaption>说明</figcaption>\n</figure>';
eq(core.blockInfo(HFIG).type, 'hfigure', 'v322: figure 块类型识别');
eq(core.splitBlocks('段落一\n\n' + HFIG + '\n\n段落二'), ['段落一', HFIG, '段落二'],
  'v322: HTML 块与段落混排往返');
eq(core.splitBlocks(HFIG), [HFIG], 'v322: figure 内部不因空行被拆');
eq(core.blockInfo('<img src="x.png">').type, 'html', 'v322: 单行 img 归为 HTML 块');
eq(core.blockInfo('| a | b |\n| --- | --- |\n| 1 | 2 |').type, 'table', 'v322: 管道表格类型不受影响');

// ---- v3.23 P1-4 语法扩展：上标 / 下标 / 脚注 / 定义列表 ----
eq(core.blockHTML('x^2^'), '<p>x<sup>2</sup></p>', 'v323: 上标 ^x^');
eq(core.blockHTML('H~2~O'), '<p>H<sub>2</sub>O</p>', 'v323: 下标 ~x~');
eq(core.blockHTML('~~del~~'), '<p><del>del</del></p>', 'v323: 删除线优先于下标');
eq(core.blockInfo('[^1]: 说明文字').type, 'fndef', 'v323: 脚注定义块类型');
eq(core.blockHTML('[^1]: 说明文字'),
  '<div class="fnbody"><div class="fnitem" id="fn-1"><span class="fnmark">[1]</span><span class="fnedit">说明文字</span></div></div>',
  'v323: 脚注定义渲染（带 id 锚点；v3.31.3 正文包进 .fnedit 支持渲染态编辑）');
eq(core.blockHTML('见[^1]').indexOf('<sup class="fnref"><a href="#fn-1" data-fn="1">[1]</a></sup>') !== -1,
  true, 'v323: 脚注引用渲染为上标链接');
eq(core.blockInfo('术语\n: 定义内容').type, 'deflist', 'v323: 定义列表块类型');
eq(core.blockHTML('术语\n: 定义内容'), '<dl class="deflist"><dt>术语</dt><dd>定义内容</dd></dl>',
  'v323: 定义列表渲染');
eq(core.splitBlocks('正文\n\n[^1]: 说明'), ['正文', '[^1]: 说明'], 'v323: 脚注定义独立成块');

console.log(fails ? `\n${fails} test(s) FAILED` : '\nALL TESTS PASSED');
process.exit(fails ? 1 : 0);
