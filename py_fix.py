import sys

with open('js/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

find = '''    for (const section of article.sections) {
      html += `<h3 class="wiki-heading">${section.heading}</h3>`;
      html += `<p class="wiki-body">${section.body}</p>`;
      textForTTS += section.heading + '. ' + section.body + ' ';
    }'''

replace = '''    for (const section of article.sections) {
      html += `<h3 class="wiki-heading">${section.heading}</h3>`;
      textForTTS += section.heading + '. ';

      const paragraphs = section.body.split('\\n\\n');
      for (const p of paragraphs) {
        if (!p.trim()) continue;
        html += `<p class="wiki-body">${p.trim()}</p>`;
        textForTTS += p.trim() + ' ';
      }
    }'''

content = content.replace(find, replace)

with open('js/app.js', 'w', encoding='utf-8') as f:
    f.write(content)
