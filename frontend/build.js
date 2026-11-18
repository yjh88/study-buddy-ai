// Vercel 빌드 스크립트: 정적 파일을 dist/ 로 복사하고 환경 변수로 config.js 를 생성한다.
// Vercel 프로젝트 설정 > Environment Variables 에 API_BASE_URL 을 등록할 것.
const fs = require("fs");
const path = require("path");

const out = path.join(__dirname, "dist");
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out);

for (const f of ["index.html", "style.css", "app.js"]) {
  fs.copyFileSync(path.join(__dirname, f), path.join(out, f));
}

const apiBase = (process.env.API_BASE_URL || "").trim().replace(/\/+$/, "");
if (!apiBase) {
  console.warn("[build] API_BASE_URL 환경 변수가 비어 있습니다. http://localhost:8000 으로 대체합니다.");
}
fs.writeFileSync(
  path.join(out, "config.js"),
  `window.APP_CONFIG = ${JSON.stringify({ API_BASE_URL: apiBase || "http://localhost:8000" })};\n`
);
console.log(`[build] dist/ 생성 완료 (API_BASE_URL=${apiBase || "http://localhost:8000"})`);
