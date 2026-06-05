/**
 * app.js
 * ══════
 * Frontend interactivity for the Library Management System.
 * Handles AJAX search, modals, searchable dropdowns, and Return page auto-populate.
 */

document.addEventListener("DOMContentLoaded", () => {
  // ── Modals ──────────────────────────────────────────────────
  const modalTriggers = document.querySelectorAll("[data-modal-target]");
  modalTriggers.forEach(btn => {
    btn.addEventListener("click", () => {
      const modalId = btn.getAttribute("data-modal-target");
      const modal = document.getElementById(modalId);
      if (modal) modal.classList.add("open");
    });
  });

  const modalCloses = document.querySelectorAll("[data-modal-close]");
  modalCloses.forEach(btn => {
    btn.addEventListener("click", () => {
      const modal = btn.closest(".modal-overlay");
      if (modal) modal.classList.remove("open");
    });
  });

  // Close modals when clicking outside container
  const overlays = document.querySelectorAll(".modal-overlay");
  overlays.forEach(overlay => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        overlay.classList.remove("open");
      }
    });
  });

  // ── Searchable Dropdowns ────────────────────────────────────
  const customDropdowns = document.querySelectorAll(".dropdown-container");
  customDropdowns.forEach(container => {
    const input = container.querySelector(".dropdown-search-input");
    const menu = container.querySelector(".dropdown-menu-custom");
    const valueInput = container.querySelector(".dropdown-value-input");
    const items = container.querySelectorAll(".dropdown-item-custom");

    if (!input || !menu || !valueInput) return;

    // Show dropdown on focus
    input.addEventListener("focus", () => {
      menu.classList.add("open");
      filterDropdown(input.value, items);
    });

    // Hide dropdown on blur (delayed to allow item click)
    input.addEventListener("blur", () => {
      setTimeout(() => {
        menu.classList.remove("open");
        // Verify value check (if user cleared input but didn't select, clear value)
        const match = Array.from(items).find(it => it.getAttribute("data-label") === input.value);
        if (!match && input.value !== "") {
          const selectedItem = Array.from(items).find(it => it.getAttribute("data-value") === valueInput.value);
          input.value = selectedItem ? selectedItem.getAttribute("data-label") : "";
        } else if (input.value === "") {
          valueInput.value = "";
        }
      }, 200);
    });

    // Filter dropdown on type
    input.addEventListener("input", () => {
      menu.classList.add("open");
      filterDropdown(input.value, items);
    });

    // Select item
    items.forEach(item => {
      item.addEventListener("click", () => {
        const val = item.getAttribute("data-value");
        const lbl = item.getAttribute("data-label");
        input.value = lbl;
        valueInput.value = val;
        menu.classList.remove("open");

        // Custom event trigger for dependent dropdowns (e.g. Return page)
        const selectEvent = new CustomEvent("item-selected", {
          detail: { label: lbl, value: val }
        });
        container.dispatchEvent(selectEvent);
      });
    });
  });

  function filterDropdown(query, items) {
    const q = query.toLowerCase().trim();
    items.forEach(item => {
      const lbl = item.getAttribute("data-label").toLowerCase();
      if (lbl.includes(q)) {
        item.style.display = "flex";
      } else {
        item.style.display = "none";
      }
    });
  }

  // ── Return Book Page: Auto-populate issued books dropdown ────
  const studentReturnDropdown = document.getElementById("student-return-dropdown");
  if (studentReturnDropdown) {
    const bookSelect = document.getElementById("return-book-select");

    studentReturnDropdown.addEventListener("item-selected", (e) => {
      const sid = e.detail.value;
      if (!sid) return;

      // Fetch issued books for student
      fetch(`/api/student-books/${sid}`)
        .then(res => res.json())
        .then(data => {
          bookSelect.innerHTML = "";
          if (data.length === 0) {
            const opt = document.createElement("option");
            opt.value = "";
            opt.textContent = "No books currently issued";
            bookSelect.appendChild(opt);
            return;
          }

          data.forEach(book => {
            const opt = document.createElement("option");
            opt.value = book.isbn;
            opt.textContent = `${book.title} (due ${book.due_date})`;
            bookSelect.appendChild(opt);
          });
        })
        .catch(err => console.error("Error fetching student books:", err));
    });
  }
});

// Segmented control toggle for login page
function toggleLoginRole(role) {
  const adminBtn = document.getElementById("btn-role-admin");
  const studentBtn = document.getElementById("btn-role-student");
  const roleInput = document.getElementById("login-role-input");
  const idLabel = document.getElementById("login-id-label");
  const idInput = document.getElementById("login-id-input");

  if (role === 'admin') {
    adminBtn.classList.add("active");
    studentBtn.classList.remove("active");
    roleInput.value = "admin";
    idLabel.textContent = "Username";
    idInput.placeholder = "Enter username";
  } else {
    studentBtn.classList.add("active");
    adminBtn.classList.remove("active");
    roleInput.value = "student";
    idLabel.textContent = "Student ID";
    idInput.placeholder = "e.g. STU2024001";
  }
}
