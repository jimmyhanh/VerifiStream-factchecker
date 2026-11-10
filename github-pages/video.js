const endpoint = window.verifiStreamApi;
const picker = document.querySelector("#video");
const preview = document.querySelector("#preview");
const submit = document.querySelector("#submit");
const statusLine = document.querySelector("#status");
const playback = document.querySelector("#playback");
let objectUrl;
if (endpoint) {
  document.querySelector("#instructions").textContent =
    "Choose an MP4, MOV, WebM, or MKV to preview it. Upload it to start audio extraction and continue in the dashboard.";
  submit.hidden = false;
  document.querySelector("#dashboard").hidden = false;
}
picker.addEventListener("change", () => {
  if (objectUrl) URL.revokeObjectURL(objectUrl);
  preview.removeAttribute("src");
  preview.hidden = true;
  preview.load();
  submit.disabled = true;
  statusLine.textContent = "";
  playback.textContent = "";
  const file = picker.files[0];
  if (!file) return;
  if (!file.size || !/\.(mp4|mov|webm|mkv)$/i.test(file.name)) {
    statusLine.textContent = "Choose a nonempty MP4, MOV, WebM, or MKV video.";
    return;
  }
  objectUrl = URL.createObjectURL(file);
  preview.src = objectUrl;
  preview.hidden = false;
  submit.disabled = !endpoint;
  statusLine.textContent = endpoint ? "Ready to upload." : "Local preview only. This site has no processing server configured.";
});
preview.addEventListener("error", () => {
  if (preview.hasAttribute("src"))
    playback.textContent = "This browser cannot play the selected video format.";
});
document.querySelector("#upload").addEventListener("submit", async event => {
  event.preventDefault();
  if (!endpoint || submit.disabled || !picker.files[0]) return;
  submit.disabled = true;
  picker.disabled = true;
  statusLine.textContent = "Uploading video…";
  const form = new FormData();
  form.append("file", picker.files[0]);
  try {
    const response = await fetch(endpoint + "/videos?background=true", { method: "POST", body: form, credentials: "omit" });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(typeof result.detail === "string" ? result.detail : "Server returned HTTP " + response.status + ".");
    if (!result.id) throw Error("The server did not return a video ID. Check existing videos before uploading again.");
    window.location.assign("./dashboard/?video=" + encodeURIComponent(result.id));
  } catch (error) {
    statusLine.textContent = "Upload could not be confirmed. " + error.message;
    submit.disabled = false;
    picker.disabled = false;
  }
});
