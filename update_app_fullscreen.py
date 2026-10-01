import sys

with open("js/app.js", "r", encoding="utf-8") as f:
    js = f.read()

find1 = """  btnLeft.addEventListener('click', () => {
    const active = panelLeft.classList.toggle('fullscreen');
    panelRight.style.display = active ? 'none' : '';
    handle.style.display     = active ? 'none' : '';
    btnLeft.title = active ? 'Exit fullscreen' : 'Expand globe';
  });"""

replace1 = """  btnLeft.addEventListener('click', () => {
    const active = panelLeft.classList.toggle('fullscreen');
    panelRight.style.display = active ? 'none' : '';
    // handle stays visible to allow dragging out of fullscreen
    btnLeft.title = active ? 'Exit fullscreen' : 'Expand globe';
  });"""

find2 = """  btnRight.addEventListener('click', () => {
    const active = panelRight.classList.toggle('fullscreen');
    panelLeft.style.display  = active ? 'none' : '';
    handle.style.display     = active ? 'none' : '';
    btnRight.title = active ? 'Exit fullscreen' : 'Expand info panel';
  });"""

replace2 = """  btnRight.addEventListener('click', () => {
    const active = panelRight.classList.toggle('fullscreen');
    panelLeft.style.display  = active ? 'none' : '';
    // handle stays visible to allow dragging out of fullscreen
    btnRight.title = active ? 'Exit fullscreen' : 'Expand info panel';
  });"""

js = js.replace(find1, replace1).replace(find2, replace2)

# Update dragStart to automatically exit fullscreen if dragging handle from the edge
find3 = """  const dragStart = (x, y) => {
    dragging    = true;
    isMobile    = window.innerWidth <= 768;
    startX      = x;
    startY      = y;
    const rect  = panelLeft.getBoundingClientRect();"""

replace3 = """  const dragStart = (x, y) => {
    dragging    = true;
    isMobile    = window.innerWidth <= 768;
    startX      = x;
    startY      = y;

    // Auto-exit fullscreen if user grabs the handle
    if (panelLeft.classList.contains('fullscreen')) {
      document.getElementById('fullscreenLeft').click();
      if (isMobile) panelLeft.style.height = `${window.innerHeight - 14}px`;
      else panelLeft.style.width = `${window.innerWidth - 5}px`;
    }
    if (panelRight.classList.contains('fullscreen')) {
      document.getElementById('fullscreenRight').click();
      if (isMobile) panelLeft.style.height = `0px`;
      else panelLeft.style.width = `0px`;
    }

    const rect  = panelLeft.getBoundingClientRect();"""

js = js.replace(find3, replace3)

with open("js/app.js", "w", encoding="utf-8") as f:
    f.write(js)
