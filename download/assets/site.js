/* NutriScan website behaviour: menu, scroll reveals, loading screen, release info, download gate.
   Everything degrades gracefully: with JavaScript off the page is fully readable. */
(function () {
  var doc = document.documentElement;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Loading screen: first visit of a session only, like the app's splash.
  var loader = document.querySelector(".loader");
  if (loader && doc.classList.contains("show-loader")) {
    var shown = Date.now();
    var hide = function () {
      var wait = Math.max(0, 1250 - (Date.now() - shown));
      setTimeout(function () {
        loader.classList.add("done");
        setTimeout(function () { loader.remove(); }, 700);
      }, wait);
    };
    if (document.readyState === "complete") hide(); else window.addEventListener("load", hide);
    try { sessionStorage.setItem("ns-seen", "1"); } catch (e) {}
  }

  // Mobile menu.
  var btn = document.querySelector(".menu-btn");
  var links = document.querySelector(".nav-links");
  if (btn && links) {
    btn.addEventListener("click", function () {
      var open = links.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    links.addEventListener("click", function (e) {
      if (e.target.tagName === "A") { links.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { links.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); }
    });
  }

  // Calm reveal on scroll.
  var items = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window) || reduce) {
    items.forEach(function (el) { el.classList.add("in"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    items.forEach(function (el) { io.observe(el); });
  }

  // Release details come from release.json, written by publish.sh, so the page never guesses.
  var rel = document.querySelectorAll("[data-release]");
  if (rel.length && window.fetch) {
    fetch("release.json", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (d) {
      rel.forEach(function (el) {
        var k = el.getAttribute("data-release");
        var v = d[k];
        if (k === "size_mb" && v) v = v + " MB";
        if (v) el.textContent = v;
      });
    }).catch(function () {});
  }

  // Download gate: the button unlocks once the person confirms they've read the essentials.
  var gate = document.getElementById("consent");
  var dl = document.getElementById("dl-btn");
  if (gate && dl) {
    var sync = function () {
      dl.setAttribute("aria-disabled", gate.checked ? "false" : "true");
      dl.tabIndex = gate.checked ? 0 : -1;
    };
    gate.addEventListener("change", sync); sync();
  }

  var year = document.querySelector("[data-year]");
  if (year) year.textContent = new Date().getFullYear();
})();
