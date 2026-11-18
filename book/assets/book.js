/* ==========================================================================
   Mastering Apache Spark — book behaviour
   Dependency-free: navigation, scroll spy, copy buttons, reading progress.
   ========================================================================== */

(function () {
  "use strict";

  var TOPBAR_OFFSET = 80;

  /* ---------------------------------------------------------------- nav --- */

  var sidebar = document.getElementById("sidebar");
  var navToggle = document.getElementById("navToggle");

  if (navToggle && sidebar) {
    navToggle.addEventListener("click", function () {
      sidebar.classList.toggle("open");
    });
  }

  if (sidebar) {
    sidebar.addEventListener("click", function (event) {
      var link = event.target.closest("a");
      if (link && window.innerWidth <= 900) {
        sidebar.classList.remove("open");
      }
    });
  }

  /* --------------------------------------------------------- scroll spy --- */

  var links = {};
  Array.prototype.forEach.call(
    document.querySelectorAll(".nav-list a[href^='#']"),
    function (anchor) {
      links[anchor.getAttribute("href").slice(1)] = anchor;
    }
  );

  var headings = Array.prototype.slice.call(
    document.querySelectorAll("article h1[id], article h2[id], article h3[id]")
  );

  var activeId = null;

  function setActive(id) {
    if (id === activeId || !links[id]) {
      return;
    }
    var previous = activeId && links[activeId];
    if (previous) {
      previous.classList.remove("active");
    }
    links[id].classList.add("active");
    activeId = id;

    var item = links[id];
    var box = sidebar.getBoundingClientRect();
    var rect = item.getBoundingClientRect();
    if (rect.top < box.top + 40 || rect.bottom > box.bottom - 40) {
      item.scrollIntoView({ block: "nearest" });
    }
  }

  var ticking = false;

  function onScroll() {
    if (ticking) {
      return;
    }
    ticking = true;
    window.requestAnimationFrame(function () {
      ticking = false;

      /* reading progress */
      var bar = document.getElementById("progress");
      if (bar) {
        var doc = document.documentElement;
        var max = doc.scrollHeight - doc.clientHeight;
        var ratio = max > 0 ? doc.scrollTop / max : 0;
        bar.style.width = (ratio * 100).toFixed(2) + "%";
      }

      /* active section */
      if (headings.length) {
        var current = null;
        for (var i = 0; i < headings.length; i += 1) {
          var top = headings[i].getBoundingClientRect().top;
          if (top - TOPBAR_OFFSET <= 0) {
            current = headings[i].id;
          } else {
            break;
          }
        }
        if (!current) {
          current = headings[0].id;
        }
        setActive(current);
      }
    });
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  onScroll();

  /* ---------------------------------------------------------- copy code --- */

  function attachCopyButtons() {
    var blocks = document.querySelectorAll("article pre, .book-cover pre");

    Array.prototype.forEach.call(blocks, function (pre) {
      if (pre.dataset.copyReady === "1") {
        return;
      }
      pre.dataset.copyReady = "1";

      var text = pre.innerText.replace(/\n+$/, "");

      var button = document.createElement("button");
      button.type = "button";
      button.className = "copy-btn";
      button.textContent = "Copy";
      button.setAttribute("aria-label", "Copy code to clipboard");

      button.addEventListener("click", function () {
        function done() {
          button.textContent = "Copied";
          button.classList.add("copied");
          window.setTimeout(function () {
            button.textContent = "Copy";
            button.classList.remove("copied");
          }, 1600);
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () {
            fallbackCopy(text, done);
          });
        } else {
          fallbackCopy(text, done);
        }
      });

      pre.appendChild(button);
    });
  }

  function fallbackCopy(text, done) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "-1000px";
    document.body.appendChild(area);
    area.select();
    try {
      document.execCommand("copy");
      done();
    } catch (error) {
      /* Clipboard unavailable (e.g. file:// in some browsers). */
    }
    document.body.removeChild(area);
  }

  /* ------------------------------------------------------ external links -- */

  Array.prototype.forEach.call(document.querySelectorAll("article a[href^='http']"), function (a) {
    a.setAttribute("target", "_blank");
    a.setAttribute("rel", "noopener noreferrer");
  });

  /* ---------------------------------------------------------------- boot -- */

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attachCopyButtons);
  } else {
    attachCopyButtons();
  }
})();
