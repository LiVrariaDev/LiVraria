const { spawnSync } = require("child_process");
const path = require("path");
const fs = require("fs");

// Create virtual environment
const isWin = process.platform === "win32";
const backendPath = path.join(__dirname, "..", "backend");
const python = isWin ? "python.exe" : "python3";

let child = spawnSync(python, ["-m", "venv", path.join(backendPath, ".venv")], {
    cwd: backendPath,
    stdio: "inherit",
    shell: true,
});

if (child.error || child.status !== 0) {
    console.error("Failed to create virtual environment");
    process.exit(1);
}

// Install dependencies
const binPath = isWin ? "Scripts" : "bin";
const pip = isWin ? "pip.exe" : "pip";
const pipPath = path.join(backendPath, ".venv", binPath, pip);

child = spawnSync(pipPath, ["install", "-r", "requirements.txt"], {
    cwd: backendPath,
    stdio: "inherit",
    shell: true,
});

if (child.error || child.status !== 0) {
    console.error("Failed to install dependencies");
    process.exit(1);
}

try {
    fs.copyFileSync(path.join(__dirname, "..", ".env.template"), path.join(__dirname, "..", ".env"));
} catch (error) {
    console.error("Failed to copy .env.template");
    console.error(error);
    process.exit(1);
}

console.log("-------------------------------")
console.log("[WARNING] Please edit a .env file")
console.log("-------------------------------")

process.exit(0);