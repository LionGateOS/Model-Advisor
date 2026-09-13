"use strict";

const statusNode = document.querySelector("#load-status");
const refreshButton = document.querySelector("#refresh-button");
const machineNode = document.querySelector("#machine-summary");
const gpuNode = document.querySelector("#gpu-list");
const runtimeNode = document.querySelector("#runtime-list");

function known(value, fallback = "Unknown") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

function formatBytes(value) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    return "Unknown";
  }

  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let amount = value;
  let index = 0;

  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }

  const digits = index >= 3 ? 1 : 0;
  return `${amount.toFixed(digits)} ${units[index]}`;
}

function element(tag, className, text) {
  const node = document.createElement(tag);

  if (className) {
    node.className = className;
  }

  if (text !== undefined) {
    node.textContent = text;
  }

  return node;
}

function addFact(parent, label, value) {
  const fact = element("div", "fact");
  fact.append(
    element("span", "fact-label", label),
    element("div", "fact-value", known(value)),
  );
  parent.append(fact);
}

function addMeta(parent, label, value) {
  const item = element("div");
  item.append(
    element("span", "meta-label", label),
    element("div", "meta-value", known(value)),
  );
  parent.append(item);
}

function renderMachine(hardware) {
  machineNode.replaceChildren();

  const os = hardware.os || {};
  const cpu = hardware.cpu || {};
  const memory = hardware.memory || {};

  const osName = [os.name, os.version].filter(Boolean).join(" ");

  addFact(machineNode, "Operating system", osName || "Unknown");
  addFact(machineNode, "Architecture", os.architecture || cpu.architecture);
  addFact(machineNode, "CPU", cpu.model);
  addFact(
    machineNode,
    "CPU cores",
    cpu.physical_cores === null || cpu.physical_cores === undefined
      ? "Unknown"
      : `${cpu.physical_cores} physical / ${known(cpu.logical_cpus)} logical`,
  );
  addFact(machineNode, "System memory", formatBytes(memory.total_bytes));
}

function renderGPUs(hardware) {
  gpuNode.replaceChildren();

  const gpus = Array.isArray(hardware.gpus) ? hardware.gpus : [];

  if (gpus.length === 0) {
    gpuNode.append(
      element("div", "empty-state", "No GPU information was detected."),
    );
    return;
  }

  gpus.forEach((gpu, index) => {
    const card = element("article", "device-card");
    const vendor = known(gpu.vendor, "GPU");
    const model = known(gpu.model, `Device ${index + 1}`);

    card.append(
      element("h3", "", vendor),
      element("div", "device-model", model),
    );

    const meta = element("div", "device-meta");
    addMeta(meta, "VRAM", formatBytes(gpu.total_vram_bytes));
    addMeta(meta, "Driver", gpu.driver_version);
    addMeta(
      meta,
      "Evidence",
      Array.isArray(gpu.detection_sources) && gpu.detection_sources.length
        ? gpu.detection_sources.join(", ")
        : "Unknown",
    );

    card.append(meta);
    gpuNode.append(card);
  });
}

function evidenceGroup(title, values) {
  const group = element("div", "evidence-group");
  group.append(element("p", "", title));

  if (!Array.isArray(values) || values.length === 0) {
    group.append(element("div", "", "No evidence recorded."));
    return group;
  }

  const list = element("ul");

  values.forEach((value) => {
    list.append(element("li", "", known(value)));
  });

  group.append(list);
  return group;
}

function renderRuntimes(runtimesProfile, compatibilityProfile) {
  runtimeNode.replaceChildren();

  const runtimes = Array.isArray(runtimesProfile.runtimes)
    ? runtimesProfile.runtimes
    : [];

  const compatibility = new Map(
    (
      Array.isArray(compatibilityProfile.runtimes)
        ? compatibilityProfile.runtimes
        : []
    ).map((item) => [item.runtime_name, item]),
  );

  if (runtimes.length === 0) {
    runtimeNode.append(
      element("div", "empty-state", "No runtime information is available."),
    );
    return;
  }

  runtimes.forEach((runtime) => {
    const assessment = compatibility.get(runtime.name) || {
      status: "unknown",
      reasons: [],
      evidence_sources: [],
    };

    const status = known(assessment.status, "unknown");
    const card = element("article", "runtime-card");

    const top = element("div", "runtime-topline");
    top.append(
      element("h3", "runtime-name", known(runtime.name, "Runtime")),
      element(
        "span",
        `status-badge status-${status}`,
        status,
      ),
    );
    card.append(top);

    const meta = element("div", "runtime-meta");
    addMeta(meta, "Available", runtime.available ? "Yes" : "No");
    addMeta(meta, "Version", runtime.version);
    addMeta(meta, "Build", runtime.build);
    addMeta(meta, "Commit", runtime.commit);
    card.append(meta);

    const details = element("details", "evidence");
    details.append(element("summary", "", "Why / Evidence"));

    const body = element("div", "evidence-body");
    body.append(
      evidenceGroup("Reasons", assessment.reasons),
      evidenceGroup("Evidence sources", assessment.evidence_sources),
    );

    details.append(body);
    card.append(details);
    runtimeNode.append(card);
  });
}

async function refreshDashboard() {
  refreshButton.disabled = true;
  statusNode.classList.remove("error");
  statusNode.textContent = "Inspecting this machine…";

  try {
    const response = await fetch("/api/dashboard", {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`Dashboard request failed (${response.status}).`);
    }

    const data = await response.json();

    renderMachine(data.hardware || {});
    renderGPUs(data.hardware || {});
    renderRuntimes(
      data.runtimes || {},
      data.compatibility || {},
    );

    statusNode.textContent = "Current machine evidence loaded.";
  } catch (error) {
    statusNode.classList.add("error");
    statusNode.textContent =
      error instanceof Error
        ? error.message
        : "Unable to load dashboard evidence.";
  } finally {
    refreshButton.disabled = false;
  }
}

refreshButton.addEventListener("click", refreshDashboard);
refreshDashboard();
