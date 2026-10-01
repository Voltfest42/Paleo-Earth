import sys

with open("js/app.js", "r", encoding="utf-8") as f:
    js = f.read()

find = """      // Snap to fullscreen if dragged near the edges
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
      }"""

replace = """      // Snap to fullscreen if dragged near the edges
      if (targetY < 80) { // Dragged to the top (Text Fullscreen)
        panelLeft.style.height = '45vh'; // Reset for when they exit fullscreen
        const btn = document.getElementById('fullscreenRight');
        if (btn && !document.getElementById('panelRight').classList.contains('fullscreen')) btn.click();
        dragEnd();
        return;
      }
      if (targetY > container.clientHeight - 120) { // Dragged to the bottom (Globe Fullscreen)
        panelLeft.style.height = '45vh'; // Reset for when they exit fullscreen
        const btn = document.getElementById('fullscreenLeft');
        if (btn && !document.getElementById('panelLeft').classList.contains('fullscreen')) btn.click();
        dragEnd();
        return;
      }"""

js = js.replace(find, replace)

with open("js/app.js", "w", encoding="utf-8") as f:
    f.write(js)
