// Sidebar toggle (mobile), toast auto-dismiss, save/unsave AJAX buttons
document.addEventListener("DOMContentLoaded", function () {
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  window.CSRF_TOKEN = csrfMeta ? csrfMeta.getAttribute("content") : "";

  var toggleBtn = document.getElementById("sidebarToggle");
  var sidebar = document.getElementById("appSidebar");
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener("click", function () {
      sidebar.classList.toggle("show");
    });
  }

  // Landing page mobile nav (guest_content only - no-op elsewhere).
  var landingNavToggle = document.getElementById("landingNavToggle");
  var landingNavInner = document.getElementById("landingNavInner");
  if (landingNavToggle && landingNavInner) {
    landingNavToggle.addEventListener("click", function () {
      landingNavInner.classList.toggle("show");
    });
  }

  document.querySelectorAll(".toast-item").forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity 0.4s";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 400);
    }, 4500);
  });

  // Forms whose submit triggers a slow AI call: disable the button and
  // show a spinner immediately so the page doesn't look frozen.
  document.querySelectorAll("form[data-ai-loading]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var btn = form.querySelector("button[type=submit]");
      if (!btn || btn.disabled) return;
      btn.dataset.originalHtml = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="loading-spinner"></span> ' + (form.getAttribute("data-ai-loading") || "Working...");
    });
  });

  // Custom confirm modal for destructive/important form submits, replacing
  // native window.confirm() (which is inconsistent with the app's design
  // and gets auto-dismissed by some automated/embedded browser contexts).
  var confirmModalEl = document.getElementById("confirmModal");
  var pendingConfirmForm = null;
  if (confirmModalEl && window.bootstrap) {
    var confirmModal = new bootstrap.Modal(confirmModalEl);
    var confirmBody = document.getElementById("confirmModalBody");
    var confirmBtn = document.getElementById("confirmModalConfirmBtn");

    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
      form.addEventListener("submit", function (e) {
        if (form.dataset.confirmed === "true") return;
        e.preventDefault();
        pendingConfirmForm = form;
        confirmBody.textContent = form.getAttribute("data-confirm");
        confirmBtn.textContent = form.getAttribute("data-confirm-label") || "Confirm";
        confirmBtn.className = "btn " + (form.getAttribute("data-confirm-variant") === "danger"
          ? "btn-danger-c" : "btn-primary-c");
        confirmModal.show();
      });
    });

    confirmBtn.addEventListener("click", function () {
      confirmModal.hide();
      if (pendingConfirmForm) {
        pendingConfirmForm.dataset.confirmed = "true";
        pendingConfirmForm.requestSubmit ? pendingConfirmForm.requestSubmit() : pendingConfirmForm.submit();
        pendingConfirmForm = null;
      }
    });
  }

  document.querySelectorAll(".js-save-toggle").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      var url = btn.getAttribute("data-url");
      fetch(url, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": window.CSRF_TOKEN || "",
        },
      })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (data.saved) {
            btn.classList.add("text-warning");
            btn.innerHTML = '<i class="fa-solid fa-bookmark"></i>';
          } else {
            btn.classList.remove("text-warning");
            btn.innerHTML = '<i class="fa-regular fa-bookmark"></i>';
          }
        });
    });
  });
});

function showToast(message, category) {
  var stack = document.querySelector(".toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.className = "toast-stack";
    document.body.appendChild(stack);
  }
  var el = document.createElement("div");
  el.className = "toast-item " + (category || "info");
  el.textContent = message;
  stack.appendChild(el);
  setTimeout(function () {
    el.style.transition = "opacity 0.4s";
    el.style.opacity = "0";
    setTimeout(function () { el.remove(); }, 400);
  }, 4500);
}
