const fs = require('fs');
let c = fs.readFileSync('js/app.js', 'utf8');

const findStr = \  // --- Wiki Tab Renderer -----------------------------------------------------
  function renderWiki(keyframeId) {
    const el = document.getElementById('wikiContent');
    if (!el) return;

    const article = wikiArticles && wikiArticles[keyframeId];
    if (!article) {
      el.innerHTML = '<p style="padding:24px;color:var(--text-muted);text-align:center;font-style:italic;">No detailed article available for this period yet.<br>Check back soon!</p>';
      return;
    }

    let html = '';
    if (article.subtitle) {
      html += \\\<p class="wiki-subtitle">\\\</p>\\\;
    }
    for (const section of article.sections) {
      html += \\\<h3 class="wiki-heading">\\\</h3>\\\;
      html += \\\<p class="wiki-body">\\\</p>\\\;
    }
    el.innerHTML = html;
    el.scrollTop = 0; // scroll back to top on keyframe change
  }\;

const replaceStr = \  // --- Wiki Tab Renderer -----------------------------------------------------
  let currentWikiText = '';
  const wikiHeader = document.querySelector('.wiki-header');
  const wikiSubtitle = document.getElementById('wikiSubtitle');
  const wikiTtsBtn = document.getElementById('wikiTtsBtn');

  if (wikiTtsBtn) {
    wikiTtsBtn.addEventListener('click', () => {
      if (currentWikiText) {
        speak(currentWikiText, wikiTtsBtn);
      }
    });
  }

  function renderWiki(keyframeId) {
    const el = document.getElementById('wikiContent');
    if (!el) return;

    const article = wikiArticles && wikiArticles[keyframeId];
    if (!article) {
      if (wikiHeader) wikiHeader.style.display = 'none';
      currentWikiText = '';
      el.innerHTML = '<p style="padding:24px;color:var(--text-muted);text-align:center;font-style:italic;">No detailed article available for this period yet.<br>Check back soon!</p>';
      return;
    }

    if (wikiHeader) {
      wikiHeader.style.display = 'flex';
      if (wikiSubtitle) wikiSubtitle.textContent = article.subtitle || '';
    }

    let html = '';
    let textForTTS = article.title + '. ' + (article.subtitle ? article.subtitle + '. ' : '');

    for (const section of article.sections) {
      html += \\\<h3 class="wiki-heading">\\\</h3>\\\;
      html += \\\<p class="wiki-body">\\\</p>\\\;
      textForTTS += section.heading + '. ' + section.body + ' ';
    }
    el.innerHTML = html;
    el.scrollTop = 0; // scroll back to top on keyframe change
    currentWikiText = textForTTS.trim();
  }\;

c = c.replace(findStr, replaceStr);
fs.writeFileSync('js/app.js', c);
