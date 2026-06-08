# Search

<input type="search" id="search-box" placeholder="Search the knowledge base…"
       aria-label="Search" autocomplete="off"
       style="width:100%;padding:0.6em;font-size:1em;box-sizing:border-box;">
<p id="search-status"></p>
<ul id="search-results"></ul>

<!--
  Client-side search. lunr.js is loaded from a pinned CDN; add an SRI integrity
  hash to harden if you wish. The index (assets/search-index.json) is generated
  by scripts/build_search_index.py and kept fresh by CI. All paths here are
  plain and relative to this page (the site root), so they resolve correctly
  whether or not the site is served under a baseurl prefix.
-->
<script src="https://cdn.jsdelivr.net/npm/lunr@2.3.9/lunr.min.js"></script>
<script>
(function () {
  var INDEX_URL = "assets/search-index.json";
  var idx = null, docs = [];
  var box = document.getElementById("search-box");
  var statusEl = document.getElementById("search-status");
  var out = document.getElementById("search-results");

  fetch(INDEX_URL).then(function (r) { return r.json(); }).then(function (data) {
    docs = data;
    idx = lunr(function () {
      this.ref("id");
      this.field("title", { boost: 10 });
      this.field("body");
      data.forEach(function (d, i) { d.id = i; this.add(d); }, this);
    });
    var q = new URLSearchParams(location.search).get("q");
    if (q) { box.value = q; run(); }
  }).catch(function () {
    statusEl.textContent = "Could not load the search index.";
  });

  function snippet(body, q) {
    var i = body.toLowerCase().indexOf(q.toLowerCase());
    if (i < 0) return body.slice(0, 160) + "…";
    var start = Math.max(0, i - 60);
    return (start > 0 ? "…" : "") + body.slice(start, start + 160) + "…";
  }

  function run() {
    var q = box.value.trim();
    out.innerHTML = "";
    if (!q || !idx) { statusEl.textContent = ""; return; }
    var results;
    try { results = idx.search(q); }
    catch (e) { results = idx.search(q.replace(/[~^:*+\-]/g, " ")); }
    statusEl.textContent = results.length + " result(s) for “" + q + "”";
    results.slice(0, 40).forEach(function (r) {
      var d = docs[r.ref];
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = d.url;            // relative to site root -> baseurl-independent
      a.textContent = d.title;
      li.appendChild(a);
      var p = document.createElement("div");
      p.style.color = "#555";
      p.style.fontSize = "0.9em";
      p.textContent = snippet(d.body, q);
      li.appendChild(p);
      out.appendChild(li);
    });
  }

  box.addEventListener("input", run);
})();
</script>
