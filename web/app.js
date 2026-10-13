/* Browser-only execution of the repository's Python HL7 utilities. */
const byId = (id) => document.getElementById(id);
const input = byId("source");
const status = byId("status");
const results = byId("results");
const summary = byId("summary");
const auditButton = byId("audit");
const maskButton = byId("mask");
const saveButton = byId("save");
const MAX_BYTES = 2 * 1024 * 1024;
const MODULE_FILES = [
  "__init__.py", "models.py", "parser.py", "auditor.py", "sanitizer.py"
];
let python = null;
let maskedText = "";

function setStatus(message, isError = false) {
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function resetMasked() {
  maskedText = "";
  saveButton.disabled = true;
}
input.addEventListener("input", resetMasked);

byId("file").addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  if (file.size > MAX_BYTES) {
    setStatus("File exceeds the 2 MB local processing limit.", true);
    event.target.value = "";
    return;
  }
  try {
    input.value = await file.text();
    resetMasked();
    setStatus("Local file loaded. Select Audit messages.");
  } catch {
    setStatus("Could not read the selected local file.", true);
  }
});

function checkInput() {
  const source = input.value;
  if (!source.trim()) throw new Error("Enter HL7 text or choose a file.");
  if (new TextEncoder().encode(source).byteLength > MAX_BYTES) {
    throw new Error("Message exceeds the 2 MB processing limit.");
  }
  return source;
}

async function fetchModuleFile(file) {
  for (const base of ["./hl7_auditor/", "../hl7_auditor/"]) {
    const response = await fetch(base + file, { cache: "no-cache" });
    if (response.ok) return response.text();
  }
  throw new Error("Python source files could not be loaded.");
}

async function startPython() {
  setStatus("Loading Python runtime (first load may be slow)…");
  try {
    const { loadPyodide } = await import(
      "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.mjs"
    );
    python = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/"
    });
    python.FS.mkdirTree("/home/pyodide/hl7_auditor");
    const sources = await Promise.all(MODULE_FILES.map(fetchModuleFile));
    for (let i = 0; i < MODULE_FILES.length; i++) {
      python.FS.writeFile(
        "/home/pyodide/hl7_auditor/" + MODULE_FILES[i],
        sources[i],
        { encoding: "utf8" }
      );
    }
    await python.runPythonAsync(
      'import sys\nsys.path.insert(0, "/home/pyodide")\nimport hl7_auditor'
    );
    auditButton.disabled = false;
    maskButton.disabled = false;
    setStatus("Ready — processing stays in this browser.");
  } catch {
    setStatus("Python runtime unavailable. Check network access or retry reload.", true);
  }
}

function showReport(report) {
  summary.textContent = [
    report.total_messages + " messages",
    report.valid_messages + " without structural errors",
    report.phi_detected_count + " identifier findings",
    report.abnormal_results_count + " critical lab flags"
  ].join(" · ");
  results.replaceChildren();
  if (report.issues.length === 0) {
    results.textContent = report.total_messages
      ? "No findings under the implemented checks."
      : "No HL7 MSH messages found.";
    return;
  }
  for (const issue of report.issues.slice(0, 200)) {
    const row = document.createElement("div");
    row.className = "issue " + issue.severity.toLowerCase();
    const label = document.createElement("strong");
    label.textContent = issue.severity + " · " + issue.segment +
      "-" + issue.field + " · line " + issue.line;
    const description = document.createElement("p");
    description.textContent = issue.message;
    row.append(label, description);
    results.append(row);
  }
  if (report.issues.length > 200) {
    results.append(document.createTextNode(
      "Only the first 200 findings are shown."
    ));
  }
}

auditButton.addEventListener("click", async () => {
  try {
    const source = checkInput();
    auditButton.disabled = true;
    python.globals.set("input_hl7", source);
    const raw = await python.runPythonAsync(`
import json
from hl7_auditor import parse_hl7_stream, audit_stream
report = audit_stream(parse_hl7_stream(input_hl7))
json.dumps({
    "total_messages": report.total_messages,
    "valid_messages": report.valid_messages,
    "phi_detected_count": report.phi_detected_count,
    "abnormal_results_count": report.abnormal_results_count,
    "issues": [
        {"line": issue.line_number, "segment": issue.segment,
         "field": issue.field_index, "severity": issue.severity.value,
         "message": issue.message}
        for issue in report.issues
    ]
})
`);
    showReport(JSON.parse(raw));
    setStatus("Audit complete. Results are local to this browser.");
  } catch (error) {
    setStatus(error.message?.includes("limit") || error.message?.includes("Enter HL7")
      ? error.message : "Unable to parse the message. Check input format.", true);
  } finally {
    auditButton.disabled = !python;
  }
});

maskButton.addEventListener("click", async () => {
  try {
    const source = checkInput();
    maskButton.disabled = true;
    python.globals.set("input_hl7", source);
    maskedText = await python.runPythonAsync(`
from hl7_auditor import parse_hl7_stream, sanitize_stream
sanitize_stream(parse_hl7_stream(input_hl7))
`);
    if (!maskedText) throw new Error("No HL7 MSH messages found.");
    saveButton.disabled = false;
    setStatus("Masking complete. Review the output before any sharing.");
  } catch (error) {
    resetMasked();
    setStatus(error.message?.includes("limit") || error.message?.includes("Enter HL7") || error.message?.includes("No HL7")
      ? error.message : "Masking could not finish. Check input format.", true);
  } finally {
    maskButton.disabled = !python;
  }
});

saveButton.addEventListener("click", () => {
  if (!maskedText) return;
  const url = URL.createObjectURL(new Blob([maskedText], { type: "text/plain;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "masked_message.hl7";
  link.click();
  URL.revokeObjectURL(url);
});

startPython();
