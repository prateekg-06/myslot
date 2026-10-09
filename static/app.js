const form = document.querySelector("#booking-form");
const appointmentDate = document.querySelector("#appointment-date");
const scheduleDate = document.querySelector("#schedule-date");
const slotGrid = document.querySelector("#slot-grid");
const slotState = document.querySelector("#slot-state");
const bookButton = document.querySelector("#book-button");
const appointmentList = document.querySelector("#appointment-list");
const toast = document.querySelector("#toast");
const scheduledCount = document.querySelector("#scheduled-count");
const openCount = document.querySelector("#open-count");
const nextTime = document.querySelector("#next-time");

let selectedSlot = "";
let toastTimer;

function todayString() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now - offset).toISOString().slice(0, 10);
}

function showToast(message, isError = false) {
  window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("visible");
  toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 4600);
}

function setFieldErrors(errors = {}) {
  document.querySelectorAll("[data-error-for]").forEach((element) => {
    element.textContent = errors[element.dataset.errorFor] || "";
  });
  document.querySelectorAll("input").forEach((input) => input.removeAttribute("aria-invalid"));
  Object.keys(errors).forEach((field) => {
    const input = form.querySelector(`[name="${field}"]`);
    if (input) input.setAttribute("aria-invalid", "true");
  });
}

async function responseJson(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw data;
  return data;
}

async function loadSlots() {
  const selectedDate = appointmentDate.value;
  selectedSlot = "";
  slotGrid.innerHTML = "";
  setFieldErrors();

  if (!selectedDate) {
    slotState.textContent = "Choose a date first";
    slotGrid.innerHTML = '<div class="slot-placeholder">Select a date to see available times.</div>';
    return;
  }

  slotState.textContent = "Checking availability";
  slotGrid.innerHTML = '<div class="slot-placeholder">Loading available slots...</div>';
  try {
    const data = await fetch(`/api/slots?date=${encodeURIComponent(selectedDate)}`).then(responseJson);
    slotGrid.innerHTML = "";
    const openSlots = data.slots.filter((slot) => slot.available).length;
    slotState.textContent = `${openSlots} slots open`;
    data.slots.forEach((slot) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "slot";
      button.textContent = slot.label;
      button.disabled = !slot.available;
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", () => selectSlot(slot.time, button));
      slotGrid.append(button);
    });
  } catch (error) {
    slotState.textContent = "Unavailable";
    slotGrid.innerHTML = '<div class="slot-placeholder">Could not load time slots. Try another date.</div>';
    showToast(error.error || "Could not load availability.", true);
  }
}

function selectSlot(time, button) {
  selectedSlot = time;
  document.querySelectorAll(".slot").forEach((slot) => {
    slot.classList.remove("selected");
    slot.setAttribute("aria-pressed", "false");
  });
  button.classList.add("selected");
  button.setAttribute("aria-pressed", "true");
  setFieldErrors();
}

function formatDisplayDate(value) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(
    new Date(`${value}T00:00:00`)
  );
}

async function loadAppointments() {
  const selectedDate = scheduleDate.value;
  if (!selectedDate) return;
  appointmentList.innerHTML = '<div class="empty-state"><i data-lucide="loader-circle"></i><p>Loading schedule...</p></div>';
  window.lucide?.createIcons();

  try {
    const data = await fetch(`/api/appointments?date=${encodeURIComponent(selectedDate)}`).then(responseJson);
    const appointments = data.appointments;
    scheduledCount.textContent = appointments.length;
    openCount.textContent = Math.max(0, 15 - appointments.length);
    nextTime.textContent = appointments[0]?.time_label || "-";

    if (!appointments.length) {
      appointmentList.innerHTML = '<div class="empty-state"><i data-lucide="calendar-x-2"></i><p>No appointments booked for this day.</p></div>';
    } else {
      appointmentList.innerHTML = appointments.map((appointment) => `
        <article class="appointment-row">
          <strong class="appointment-time">${escapeHtml(appointment.time_label)}</strong>
          <div class="customer"><strong>${escapeHtml(appointment.customer_name)}</strong><span>${escapeHtml(appointment.email)}</span></div>
          <span class="service-label">${escapeHtml(appointment.service_type)}</span>
          <button class="cancel-button" type="button" data-appointment-id="${appointment.id}" aria-label="Cancel ${escapeHtml(appointment.customer_name)}'s appointment"><i data-lucide="x"></i></button>
        </article>`).join("");
      appointmentList.querySelectorAll("[data-appointment-id]").forEach((button) => {
        button.addEventListener("click", () => cancelAppointment(button.dataset.appointmentId));
      });
    }
    window.lucide?.createIcons();
  } catch (error) {
    appointmentList.innerHTML = '<div class="empty-state"><i data-lucide="circle-alert"></i><p>Could not load the schedule.</p></div>';
    window.lucide?.createIcons();
    showToast(error.error || "Could not load appointments.", true);
  }
}

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = value;
  return node.innerHTML;
}

async function cancelAppointment(id) {
  try {
    const data = await fetch(`/api/appointments/${id}`, { method: "DELETE" }).then(responseJson);
    showToast(data.message);
    await Promise.all([loadAppointments(), loadSlots()]);
  } catch (error) {
    showToast(error.error || "Could not cancel the appointment.", true);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    customer_name: form.customer_name.value,
    email: form.email.value,
    service_type: form.service_type.value,
    appointment_date: appointmentDate.value,
    time_slot: selectedSlot,
  };
  bookButton.disabled = true;
  bookButton.querySelector("span").textContent = "Scheduling...";
  setFieldErrors();

  try {
    const data = await fetch("/api/appointments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(responseJson);
    showToast(`${data.message} ${data.appointment.time_label}, ${formatDisplayDate(data.appointment.appointment_date)}.`);
    form.reset();
    appointmentDate.value = scheduleDate.value;
    await Promise.all([loadSlots(), loadAppointments()]);
  } catch (error) {
    setFieldErrors(error.fields || {});
    showToast(error.error || "Could not schedule the appointment.", true);
    if (error.error === "Selected time slot is already booked.") loadSlots();
  } finally {
    bookButton.disabled = false;
    bookButton.querySelector("span").textContent = "Confirm appointment";
  }
});

appointmentDate.addEventListener("change", loadSlots);
scheduleDate.addEventListener("change", async () => {
  appointmentDate.value = scheduleDate.value;
  await Promise.all([loadSlots(), loadAppointments()]);
});

const today = todayString();
appointmentDate.min = today;
scheduleDate.min = today;
appointmentDate.value = today;
scheduleDate.value = today;
window.lucide?.createIcons();
loadSlots();
loadAppointments();
