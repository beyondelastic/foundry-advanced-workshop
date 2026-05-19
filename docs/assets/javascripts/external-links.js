/* Open external links in a new tab */
document.addEventListener("DOMContentLoaded", function () {
  var links = document.querySelectorAll("a[href^='http']");
  links.forEach(function (link) {
    if (!link.href.startsWith(window.location.origin)) {
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
    }
  });
});
