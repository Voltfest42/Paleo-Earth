const fs = require('fs');
let content = fs.readFileSync('js/app.js', 'utf8');

const badBlock = /  \/\/ --- Wiki Tab Renderer -----------------------------------------------------\r?\n  let currentWikiText = '';\r?\n  const wikiHeader = document\.querySelector\('\.wiki-header'\);\r?\n  const wikiSubtitle = document\.getElementById\('wikiSubtitle'\);\r?\n  const wikiTtsBtn = document\.getElementById\('wikiTtsBtn'\);\r?\n\r?\n  if \(wikiTtsBtn\) \{\r?\n    wikiTtsBtn\.addEventListener\('click', \(\) => \{\r?\n      if \(currentWikiText\) \{\r?\n        speak\(currentWikiText, wikiTtsBtn\);\r?\n      \}\r?\n    \}\);\r?\n  \}/;

content = content.replace(badBlock, '  // --- Wiki Tab Renderer -----------------------------------------------------');

const topAnchor = /  \/\/ Panel layout\r?\n  initFullscreen\(\);\r?\n  initResize\(\);/;
const goodBlock = "  // Panel layout\n  initFullscreen();\n  initResize();\n\n  // Wiki DOM and TTS initialization\n  let currentWikiText = '';\n  const wikiHeader = document.querySelector('.wiki-header');\n  const wikiSubtitle = document.getElementById('wikiSubtitle');\n  const wikiTtsBtn = document.getElementById('wikiTtsBtn');\n\n  if (wikiTtsBtn) {\n    wikiTtsBtn.addEventListener('click', () => {\n      if (currentWikiText) {\n        speak(currentWikiText, wikiTtsBtn);\n      }\n    });\n  }";

content = content.replace(topAnchor, goodBlock);
fs.writeFileSync('js/app.js', content);
