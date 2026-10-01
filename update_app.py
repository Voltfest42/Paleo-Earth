import sys

with open("js/app.js", "r", encoding="utf-8") as f:
    js = f.read()

find = """    if (isMobile) {
      const delta     = y - startY;
      const newHeight = Math.max(200, Math.min(startHeight + delta, container.clientHeight - 200));
      panelLeft.style.height = `${newHeight}px`;
    } else {"""

replace = """    if (isMobile) {
      const delta     = y - startY;
      const targetY   = startHeight + delta;

      // Snap to fullscreen if dragged near the edges
      if (targetY < 80) { // Dragged to the top (Text Fullscreen)
        const btn = document.getElementById('fullscreenRight');
        if (btn && !document.getElementById('panelRight').classList.contains('fullscreen')) btn.click();
        dragEnd();
        return;
      }
      if (targetY > container.clientHeight - 120) { // Dragged to the bottom (Globe Fullscreen)
        const btn = document.getElementById('fullscreenLeft');
        if (btn && !document.getElementById('panelLeft').classList.contains('fullscreen')) btn.click();
        dragEnd();
        return;
      }

      const newHeight = Math.max(80, Math.min(targetY, container.clientHeight - 120));
      panelLeft.style.height = `${newHeight}px`;
    } else {"""

js = js.replace(find, replace)

with open("js/app.js", "w", encoding="utf-8") as f:
    f.write(js)
