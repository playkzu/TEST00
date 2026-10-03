/**
 * 保量建設 (BAOLIANG ARCHITECTURE) 官方首頁前端互動邏輯
 */

document.addEventListener("DOMContentLoaded", () => {
  initHeaderScroll();
  initMobileMenu();
  initProjectFilters();
  initProjectModal();
  initAppointmentForm();
  initBackToTop();
  initDatePickerLimit();
});

/**
 * 1. 導覽列滾動陰影與透明度變化
 */
function initHeaderScroll() {
  const header = document.querySelector(".site-header");
  if (!header) return;

  window.addEventListener("scroll", () => {
    if (window.scrollY > 40) {
      header.classList.add("scrolled");
    } else {
      header.classList.remove("scrolled");
    }
  });
}

/**
 * 2. 行動版漢堡選單切換
 */
function initMobileMenu() {
  const toggleBtn = document.querySelector(".menu-toggle");
  const navLinks = document.querySelector(".nav-links");

  if (!toggleBtn || !navLinks) return;

  toggleBtn.addEventListener("click", () => {
    const isOpen = navLinks.classList.toggle("open");
    toggleBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
  });

  // 點選連結後自動收合選單
  navLinks.querySelectorAll("a").forEach(link => {
    link.addEventListener("click", () => {
      navLinks.classList.remove("open");
      toggleBtn.setAttribute("aria-expanded", "false");
    });
  });
}

/**
 * 3. 建案分類過濾功能
 */
function initProjectFilters() {
  const filterBtns = document.querySelectorAll(".filter-btn");
  const projectCards = document.querySelectorAll(".project-card");

  filterBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      filterBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      const targetCategory = btn.getAttribute("data-filter");

      projectCards.forEach(card => {
        const cardCategory = card.getAttribute("data-category");
        if (targetCategory === "all" || cardCategory === targetCategory) {
          card.style.display = "flex";
          setTimeout(() => {
            card.style.opacity = "1";
            card.style.transform = "translateY(0)";
          }, 50);
        } else {
          card.style.opacity = "0";
          card.style.transform = "translateY(16px)";
          setTimeout(() => {
            card.style.display = "none";
          }, 300);
        }
      });
    });
  });
}

/**
 * 4. 建案詳情快速彈窗 (Project Quick View Modal)
 */
function initProjectModal() {
  const modal = document.getElementById("projectModal");
  const closeBtn = document.getElementById("closeProjectModal");
  if (!modal) return;

  // 監聽開啟按鈕
  document.querySelectorAll(".btn-quick-view").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const card = btn.closest(".project-card");
      if (!card) return;

      const name = card.querySelector(".project-name")?.innerText || "";
      const sub = card.querySelector(".project-sub")?.innerText || "";
      const desc = card.querySelector(".project-desc")?.innerText || "";
      const imgSrc = card.querySelector(".project-img")?.getAttribute("src") || "";
      const location = card.getAttribute("data-location") || "";
      const specs = card.getAttribute("data-specs") || "";
      const architect = card.getAttribute("data-architect") || "";

      document.getElementById("modalProjectImg").src = imgSrc;
      document.getElementById("modalProjectSub").innerText = sub;
      document.getElementById("modalProjectName").innerText = name;
      document.getElementById("modalProjectDesc").innerText = desc;
      document.getElementById("modalProjectLocation").innerText = location;
      document.getElementById("modalProjectSpecs").innerText = specs;
      document.getElementById("modalProjectArchitect").innerText = architect;

      // 綁定「立即預約此建案」按鈕
      const bookDirectBtn = document.getElementById("modalBookDirect");
      if (bookDirectBtn) {
        bookDirectBtn.onclick = () => {
          modal.classList.remove("active");
          selectProjectInForm(name);
        };
      }

      modal.classList.add("active");
      document.body.style.overflow = "hidden";
    });
  });

  // 關閉彈窗
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      modal.classList.remove("active");
      document.body.style.overflow = "auto";
    });
  }

  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.classList.remove("active");
      document.body.style.overflow = "auto";
    }
  });
}

/**
 * 將指定建案自動填入預約表單並平滑滾動至預約區
 */
function selectProjectInForm(projectName) {
  const projectSelect = document.getElementById("formProject");
  const bookingSection = document.getElementById("booking");

  if (projectSelect) {
    for (let i = 0; i < projectSelect.options.length; i++) {
      if (projectSelect.options[i].text.includes(projectName) || projectSelect.options[i].value.includes(projectName)) {
        projectSelect.selectedIndex = i;
        break;
      }
    }
  }

  if (bookingSection) {
    bookingSection.scrollIntoView({ behavior: "smooth" });
  }
}

/**
 * 5. 設定預約日期最小值為明天
 */
function initDatePickerLimit() {
  const dateInput = document.getElementById("formDate");
  if (!dateInput) return;

  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const yyyy = tomorrow.getFullYear();
  const mm = String(tomorrow.getMonth() + 1).padStart(2, "0");
  const dd = String(tomorrow.getDate()).padStart(2, "0");
  dateInput.min = `${yyyy}-${mm}-${dd}`;
}

/**
 * 6. VIP 預約賞屋表單提交與即時憑證生成
 */
function initAppointmentForm() {
  const form = document.getElementById("vipAppointmentForm");
  const feedback = document.getElementById("formFeedback");
  const submitBtn = document.getElementById("submitBookingBtn");
  const certModal = document.getElementById("certModal");
  const closeCertBtn = document.getElementById("closeCertModal");
  const printCertBtn = document.getElementById("printCertBtn");

  if (!form) return;

  // 性別選項外觀點選連動
  const genderChips = document.querySelectorAll(".gender-radios .radio-chip");
  genderChips.forEach(chip => {
    chip.addEventListener("click", () => {
      genderChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    // 清除舊錯誤提示
    if (feedback) {
      feedback.className = "form-feedback";
      feedback.style.display = "none";
      feedback.innerText = "";
    }

    // 取得表單值
    const name = form.name.value.trim();
    const gender = form.gender ? form.gender.value : "先生";
    const phone = form.phone.value.trim();
    const email = form.email.value.trim();
    const project = form.project.value;
    const date = form.date.value;
    const timeSlot = form.time_slot.value;
    const budget = form.budget ? form.budget.value : "";
    const notes = form.notes ? form.notes.value.trim() : "";

    // 前端格式校驗
    const cleanPhone = phone.replace(/[\s\-]/g, "");
    if (!name || name.length < 2) {
      showError("請填寫貴賓姓名（至少 2 個字元）");
      form.name.focus();
      return;
    }

    if (!/^09\d{8}$/.test(cleanPhone)) {
      showError("請輸入正確的手機號碼格式（例：0912-345-678）");
      form.phone.focus();
      return;
    }

    if (!project) {
      showError("請選擇您希望鑑賞的建案");
      form.project.focus();
      return;
    }

    if (!date) {
      showError("請選擇預約鑑賞日期");
      form.date.focus();
      return;
    }

    if (!timeSlot) {
      showError("請選擇您方便的鑑賞時段");
      form.time_slot.focus();
      return;
    }

    // 按鈕載入狀態
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = `
      <svg style="animation: spin 1s linear infinite; width:18px; height:18px;" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <circle cx="12" cy="12" r="10" stroke-width="3" stroke-dasharray="32" stroke-linecap="round"></circle>
      </svg>
      <span>尊榮預約處理中...</span>
    `;

    try {
      const response = await fetch("/api/appointment", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          name,
          gender,
          phone: cleanPhone,
          email,
          project,
          date,
          time_slot: timeSlot,
          budget,
          notes
        })
      });

      const resData = await response.json();

      if (!response.ok) {
        throw new Error(resData.message || "預約失敗，請稍候重試");
      }

      // 成功：填入 VIP 憑證並彈出
      document.getElementById("certVipName").innerText = `${name} ${gender}`;
      document.getElementById("certReservationId").innerText = resData.reservation_id;
      document.getElementById("certProjectName").innerText = project;
      document.getElementById("certDateTime").innerText = `${date} (${timeSlot})`;
      document.getElementById("certPhone").innerText = resData.details?.phone_masked || phone;

      if (certModal) {
        certModal.classList.add("active");
        document.body.style.overflow = "hidden";
      }

      // 重設表單
      form.reset();
      genderChips.forEach((c, idx) => {
        if (idx === 0) c.classList.add("active");
        else c.classList.remove("active");
      });

    } catch (err) {
      showError(err.message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalBtnText;
    }
  });

  function showError(msg) {
    if (feedback) {
      feedback.className = "form-feedback error";
      feedback.style.display = "block";
      feedback.innerText = msg;
    } else {
      alert(msg);
    }
  }

  // 關閉 VIP 憑證
  if (closeCertBtn && certModal) {
    closeCertBtn.addEventListener("click", () => {
      certModal.classList.remove("active");
      document.body.style.overflow = "auto";
    });
  }

  // 列印 / 截圖憑證按鈕
  if (printCertBtn) {
    printCertBtn.addEventListener("click", () => {
      window.print();
    });
  }
}

/**
 * 7. 回到頂部按鈕
 */
function initBackToTop() {
  const btn = document.getElementById("backToTopBtn");
  if (!btn) return;

  window.addEventListener("scroll", () => {
    if (window.scrollY > 400) {
      btn.classList.add("visible");
    } else {
      btn.classList.remove("visible");
    }
  });

  btn.addEventListener("click", () => {
    window.scrollTo({
      top: 0,
      behavior: "smooth"
    });
  });
}
