const fs = require('fs');
let c = fs.readFileSync('js/app.js', 'utf8');

const findBlock =     for (const section of article.sections) {\n      html += \\\<h3 class="wiki-heading">\\\</h3>\\\;\n      html += \\\<p class="wiki-body">\\\</p>\\\;\n      textForTTS += section.heading + '. ' + section.body + ' ';\n    };

const replaceBlock =     for (const section of article.sections) {\n      html += \\\<h3 class="wiki-heading">\\\</h3>\\\;\n      textForTTS += section.heading + '. ';\n\n      const paragraphs = section.body.split('\\\\n\\\\n');\n      for (const p of paragraphs) {\n        if (!p.trim()) continue;\n        html += \\\<p class="wiki-body">\\\</p>\\\;\n        textForTTS += p.trim() + ' ';\n      }\n    };

c = c.replace(findBlock, replaceBlock);
fs.writeFileSync('js/app.js', c);
