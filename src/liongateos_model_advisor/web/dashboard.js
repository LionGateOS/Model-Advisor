"use strict";

const statusNode = document.querySelector("#load-status");
const refreshButton = document.querySelector("#refresh-button");
const machineNode = document.querySelector("#machine-summary");
const gpuNode = document.querySelector("#gpu-list");
const runtimeNode = document.querySelector("#runtime-list");
const modelNode = document.querySelector("#model-list");
const modelSummaryNode = document.querySelector("#model-summary");
const contextNode = document.querySelector("#context-comparison");
const ecosystemNode = document.querySelector("#ecosystem-list");
const ecosystemSummaryNode = document.querySelector("#ecosystem-summary");

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

function formatInteger(value) {
  if (
    typeof value !== "number"
    || !Number.isFinite(value)
    || value < 0
  ) {
    return "Unknown";
  }

  return new Intl.NumberFormat("en-US").format(value);
}

function formatStatus(value) {
  return known(value, "unknown").replaceAll("_", " ");
}

function formatSizeLabel(value, parameterCount) {
  if (value === null || value === undefined || value === "") {
    return "Unknown";
  }

  const text = String(value).trim();

  if (
    /^\d+$/.test(text)
    && typeof parameterCount === "number"
    && Number.isFinite(parameterCount)
    && Number(text) === parameterCount
  ) {
    return "Same as exact count";
  }

  return text;
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
    const integratedAMD = gpu.vendor === "AMD"
      && gpu.model === "Raphael";
    addMeta(
      meta,
      "VRAM",
      gpu.total_vram_bytes == null
        ? (integratedAMD
          ? "Dedicated VRAM not reported; integrated graphics uses shared memory"
          : "Not reported by hardware discovery")
        : formatBytes(gpu.total_vram_bytes),
    );
    addMeta(
      meta,
      "Driver",
      gpu.driver_version || "Driver version not reported",
    );
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
    addMeta(
      meta,
      "Version",
      runtime.version || (runtime.available
        ? "Not reported by runtime"
        : "Runtime not detected through configured discovery paths"),
    );
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

function evidenceRecords(model, artifact) {
  const records = [
    ...(Array.isArray(model.evidence) ? model.evidence : []),
    ...(
      artifact && Array.isArray(artifact.evidence)
        ? artifact.evidence
        : []
    ),
  ];

  const details = element("details", "evidence");
  details.append(
    element(
      "summary",
      "",
      `Metadata evidence (${records.length})`,
    ),
  );

  const body = element("div", "evidence-body");

  if (records.length === 0) {
    body.append(
      element("div", "", "No metadata evidence recorded."),
    );
  } else {
    const list = element("ul", "metadata-evidence-list");

    records.forEach((record) => {
      const field = known(record.field);
      const kind = known(record.kind);
      const source = known(record.source);

      list.append(
        element(
          "li",
          "",
          `${field} — ${kind} — ${source}`,
        ),
      );
    });

    body.append(list);
  }

  details.append(body);
  return details;
}

function renderModels(profile, suitabilitySummaries = []) {
  modelNode.replaceChildren();

  const models = Array.isArray(profile.models)
    ? profile.models
    : [];

  const sources = Array.isArray(profile.sources)
    ? profile.sources
    : [];

  const ollamaSource = sources.find(
    (source) => source.source === "ollama-local-api",
  ) || null;

  const sourceStatus = ollamaSource
    ? known(ollamaSource.status, "unknown")
    : "unknown";

  const artifacts = new Map(
    (
      Array.isArray(profile.artifacts)
        ? profile.artifacts
        : []
    ).map((artifact) => [artifact.model_id, artifact]),
  );

  const suitabilityByModel = new Map(
    (Array.isArray(suitabilitySummaries) ? suitabilitySummaries : [])
      .map((item) => [item.model_id, item]),
  );

  const locationOrder = {
    local: 0,
    remote: 1,
    unknown: 2,
  };

  const orderedModels = [...models].sort((left, right) => {
    const leftArtifact = artifacts.get(left.model_id) || {};
    const rightArtifact = artifacts.get(right.model_id) || {};

    const leftOrder =
      locationOrder[leftArtifact.location] ?? locationOrder.unknown;
    const rightOrder =
      locationOrder[rightArtifact.location] ?? locationOrder.unknown;

    if (leftOrder !== rightOrder) {
      return leftOrder - rightOrder;
    }

    return known(left.model_id).localeCompare(
      known(right.model_id),
    );
  });

  const localCount = orderedModels.filter(
    (model) => artifacts.get(model.model_id)?.location === "local",
  ).length;

  const remoteCount = orderedModels.filter(
    (model) => artifacts.get(model.model_id)?.location === "remote",
  ).length;

  if (sourceStatus === "partial") {
    modelSummaryNode.textContent =
      `${localCount} local · ${remoteCount} remote-backed · inventory partial`;
  } else if (sourceStatus === "unavailable") {
    modelSummaryNode.textContent = "Ollama metadata source unavailable";
  } else if (sourceStatus === "error") {
    modelSummaryNode.textContent = "Ollama metadata source error";
  } else if (sourceStatus === "available") {
    modelSummaryNode.textContent =
      `${localCount} local · ${remoteCount} remote-backed`;
  } else {
    modelSummaryNode.textContent = "Model inventory status unknown";
  }

  if (orderedModels.length === 0) {
    let message = "Model inventory status is unknown.";

    if (sourceStatus === "available") {
      message = "No Ollama model registrations were discovered.";
    } else if (sourceStatus === "unavailable") {
      message =
        "Ollama model metadata could not be inspected because "
        + "the local API is unavailable.";
    } else if (sourceStatus === "error") {
      message =
        "Ollama returned an invalid model inventory response.";
    } else if (sourceStatus === "partial") {
      message =
        "Ollama model inventory is incomplete because some "
        + "model metadata could not be inspected.";
    }

    modelNode.append(
      element("div", "empty-state", message),
    );
    return;
  }

  orderedModels.forEach((model) => {
    const artifact = artifacts.get(model.model_id) || {};
    const location = known(artifact.location, "unknown");

    const card = element("article", "model-card");

    const topline = element("div", "model-topline");

    const identity = element("div");
    const rawId = known(model.model_id, "Model");
    const displayId = rawId.startsWith("ollama:")
      ? rawId.slice("ollama:".length)
      : rawId;

    identity.append(
      element(
        "h3",
        "model-name",
        known(model.display_name, displayId),
      ),
      element("div", "model-provider", "Ollama"),
    );

    topline.append(
      identity,
      element(
        "span",
        `location-badge location-${location}`,
        location === "remote"
          ? "Remote-backed"
          : location,
      ),
    );

    card.append(topline);

    if (location === "local") {
      const suitability = suitabilityByModel.get(model.model_id);
      const status = suitability?.status || "unknown";
      const labels = {
        qualified: "Qualified — evidence supports this path",
        candidate: "Candidate — not yet confirmed",
        not_qualified: "Not qualified under current evidence",
        unknown: "Unknown — more evidence needed",
      };
      const reasons = Array.isArray(suitability?.reasons)
        ? suitability.reasons
        : [];

      const panel = element("div", "model-suitability");
      panel.append(
        element("h4", "suitability-heading", "Model suitability"),
        element(
          "p",
          `status-badge status-${status === "not_qualified" ? "incompatible" : status}`,
          labels[status] || labels.unknown,
        ),
      );

      if (reasons.length > 0) {
        const explanation = element("ul", "suitability-reasons");
        reasons.forEach((reason) => {
          const explanations = {
            "complete-model-memory-unknown":
              "Total memory needs are not fully known, so a fit cannot be confirmed.",
            "artifact-size-is-storage-not-resident-weight-proof":
              "File size does not prove how much memory the loaded model will use.",
            "runtime-overhead-unknown":
              "Additional memory used by the runtime is unknown.",
            "recurrent-state-memory-unknown":
              "Additional recurrent-state memory needs are unknown.",
            "multi-gpu-fit-not-proven":
              "Using multiple GPUs may be possible, but a successful fit has not been proven.",
          };
          explanation.append(
            element("li", "", explanations[reason] || reason.replaceAll("-", " ")),
          );
        });
        panel.append(explanation);
      }

      card.append(panel);
    }

    const meta = element("div", "model-meta");

    addMeta(
      meta,
      "Exact parameters",
      formatInteger(model.parameter_count),
    );
    addMeta(
      meta,
      "Reported size label",
      formatSizeLabel(
        model.parameter_size_label,
        model.parameter_count,
      ),
    );
    addMeta(
      meta,
      "Context",
      formatInteger(model.context_length),
    );
    addMeta(
      meta,
      "Architecture",
      model.architecture,
    );
    addMeta(
      meta,
      "Format",
      artifact.format,
    );
    addMeta(
      meta,
      "Quantization",
      artifact.quantization,
    );

    addMeta(
      meta,
      "Artifact size",
      location === "remote"
        ? "Not locally stored"
        : formatBytes(artifact.size_bytes),
    );

    addMeta(
      meta,
      "Capabilities",
      Array.isArray(model.capabilities)
        && model.capabilities.length
        ? model.capabilities.join(", ")
        : "Unknown",
    );

    card.append(meta);
    card.append(evidenceRecords(model, artifact));
    modelNode.append(card);
  });
}

function renderContextComparisons(comparisons, modelsProfile) {
  contextNode.replaceChildren();

  const entries = Array.isArray(comparisons) ? comparisons : [];
  const models = new Map(
    (Array.isArray(modelsProfile.models) ? modelsProfile.models : [])
      .map((model) => [model.model_id, model]),
  );

  if (entries.length === 0) {
    contextNode.append(
      element(
        "div",
        "empty-state",
        "No locally stored Ollama model has enough evidence for comparison.",
      ),
    );
    return;
  }

  const label = element("label", "context-selector-label", "Model");
  const selector = document.createElement("select");
  selector.id = "context-model-selector";
  selector.className = "context-selector";
  selector.setAttribute("aria-describedby", "context-help");

  const table = element("div", "context-table-wrap");
  const help = element(
    "p",
    "section-note context-help",
    "KV-cache values use an assumed FP16 key/value cache (2 bytes per element), not a detected runtime setting. Estimates require supported attention metadata. Total-memory fit remains unassessed; GPUs are evaluated independently.",
  );
  help.id = "context-help";

  const renderSelected = () => {
    table.replaceChildren();
    const selected = entries[Number(selector.value)];
    const model = selected ? models.get(selected.model_id) : null;
    const title = known(model?.display_name, selected?.model_id);
    table.append(element("h3", "context-model-name", title));

    const rows = element("tbody");
    (selected?.options || []).forEach((option) => {
      const row = element("tr");
      const gpuCell = element("td", "context-value");
      const assessments = Array.isArray(option.gpu_assessments)
        ? option.gpu_assessments
        : [];
      if (assessments.length === 0) {
        gpuCell.append(element("div", "", "Unknown"));
      } else {
        assessments.forEach((assessment) => {
          gpuCell.append(
            element(
              "div",
              "",
              `${known(assessment.target_id)}: ${formatStatus(assessment.capacity_status)}`,
            ),
          );
        });
      }
      row.append(
        element("th", "context-value", formatInteger(option.context_length)),
        element("td", "context-value", formatStatus(option.context_status)),
        element(
          "td", "context-value",
          option.kv_cache_bytes == null
            ? "Not estimated" : formatBytes(option.kv_cache_bytes),
        ),
        element(
          "td", "context-value",
          option.total_memory_status == null
            ? "Not assessed" : formatStatus(option.total_memory_status),
        ),
        gpuCell,
      );
      row.firstElementChild.scope = "row";
      rows.append(row);
    });

    const tableElement = document.createElement("table");
    tableElement.className = "context-table";
    tableElement.append(
      element("caption", "visually-hidden", "Context comparison"),
    );
    const head = element("thead");
    const headerRow = element("tr");
    [
      "Tokens",
      "Context limit",
      "KV cache (FP16 scenario)",
      "Total memory fit",
      "Independent GPU assessments",
    ].forEach(
      (heading) => headerRow.append(element("th", "", heading)),
    );
    head.append(headerRow);
    tableElement.append(head, rows);
    table.append(tableElement);
  };

  entries.forEach((entry, index) => {
    const model = models.get(entry.model_id);
    const option = element("option");
    option.value = String(index);
    option.textContent = known(model?.display_name, entry.model_id);
    selector.append(option);
  });

  selector.addEventListener("change", renderSelected);
  label.htmlFor = selector.id;
  contextNode.append(label, selector, help, table);
  renderSelected();
}

function renderEcosystem(huggingfaceProfile, openrouterProfile) {
  ecosystemNode.replaceChildren();

  const hfModels = Array.isArray(huggingfaceProfile.models)
    ? huggingfaceProfile.models : [];
  const offerings = Array.isArray(openrouterProfile.offerings)
    ? openrouterProfile.offerings : [];

  ecosystemSummaryNode.textContent =
    `${hfModels.length} Hugging Face models · `
    + `${offerings.length} OpenRouter offerings`;

  hfModels.slice(0, 6).forEach((model) => {
    const card = element("article", "model-card");
    card.append(
      element("h3", "model-name", known(model.display_name, model.model_id)),
      element("div", "model-provider", "Hugging Face"),
    );
    const meta = element("div", "model-meta");
    addMeta(meta, "Parameters", model.parameter_count == null
      ? "Not reported by source" : formatInteger(model.parameter_count));
    addMeta(meta, "Context", model.context_length == null
      ? "Not reported by source" : formatInteger(model.context_length));
    addMeta(meta, "Architecture", model.architecture || "Not reported by source");
    card.append(meta);
    ecosystemNode.append(card);
  });

  offerings.slice(0, 6).forEach((offering) => {
    const card = element("article", "model-card");
    card.append(
      element("h3", "model-name", offering.provider_model_id),
      element("div", "model-provider", "OpenRouter"),
    );
    const meta = element("div", "model-meta");
    addMeta(meta, "Context", offering.context_length == null
      ? "Not reported by source" : formatInteger(offering.context_length));
    addMeta(meta, "Linked model", offering.model_id || "No verified model link");
    card.append(meta);
    ecosystemNode.append(card);
  });
}


const dashboardTabs = Array.from(
  document.querySelectorAll(".dashboard-tab")
);

function activateDashboardTab(tab, focus = false) {
  dashboardTabs.forEach((item) => {
    const selected = item === tab;
    item.setAttribute("aria-selected", String(selected));
    item.tabIndex = selected ? 0 : -1;
    const panel = document.getElementById(
      item.getAttribute("aria-controls")
    );
    if (panel) {
      panel.hidden = !selected;
    }
  });
  if (focus) {
    tab.focus();
  }
}

dashboardTabs.forEach((tab, index) => {
  tab.addEventListener("click", () => activateDashboardTab(tab));
  tab.addEventListener("keydown", (event) => {
    let next = index;
    if (event.key === "ArrowRight") {
      next = (index + 1) % dashboardTabs.length;
    } else if (event.key === "ArrowLeft") {
      next = (index - 1 + dashboardTabs.length) % dashboardTabs.length;
    } else if (event.key === "Home") {
      next = 0;
    } else if (event.key === "End") {
      next = dashboardTabs.length - 1;
    } else {
      return;
    }
    event.preventDefault();
    activateDashboardTab(dashboardTabs[next], true);
  });
});

async function refreshDashboard(force = false) {
  refreshButton.disabled = true;
  statusNode.classList.remove("error");
  statusNode.textContent = "Inspecting machine and model evidence…";

  try {
    const response = await fetch(force ? "/api/dashboard?refresh=1" : "/api/dashboard", {
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
    renderModels(
      data.models || {},
      data.suitability_summaries || [],
    );
    renderContextComparisons(
      data.context_comparisons || [],
      data.models || {},
    );
    renderEcosystem(
      data.huggingface_models || {},
      data.openrouter_models || {},
    );

    statusNode.textContent = "Current machine and model evidence loaded.";
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

refreshButton.addEventListener("click", () => refreshDashboard(true));
refreshDashboard();
