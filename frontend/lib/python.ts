/**
 * python.ts — call Python backend
 *
 * Mode 1 (Fast): FastAPI server ที่รันอยู่ที่ port 8000
 *   Start: cd engine && uvicorn main:app --port 8000 --reload
 *
 * Mode 2 (Fallback): spawn subprocess ถ้า FastAPI ไม่ได้รัน
 */

import { spawn }  from "child_process"
import path       from "path"
import fs         from "fs"

const FASTAPI_BASE = process.env.FASTAPI_URL ?? "http://127.0.0.1:8000"
const ENGINE_DIR   = path.join(process.cwd(), "..", "engine")

// ── FastAPI mode ─────────────────────────────────────────────────────────────

/** ตรวจว่า FastAPI กำลังรันอยู่ (cache 30s) */
let _fastapiAlive: boolean | null = null
let _fastapiChecked = 0

async function isFastAPIAlive(): Promise<boolean> {
  const now = Date.now()
  if (_fastapiAlive !== null && now - _fastapiChecked < 30_000) {
    return _fastapiAlive
  }
  try {
    const res = await fetch(`${FASTAPI_BASE}/health`, {
      signal: AbortSignal.timeout(1000),
    })
    _fastapiAlive  = res.ok
    _fastapiChecked = now
    return _fastapiAlive
  } catch {
    _fastapiAlive  = false
    _fastapiChecked = now
    return false
  }
}

// ── Subprocess mode (fallback) ───────────────────────────────────────────────

function getPythonPath(): string {
  const candidates = [
    path.join(ENGINE_DIR, ".venv", "Scripts", "python.exe"), // Windows
    path.join(ENGINE_DIR, ".venv", "bin",     "python3"),    // Unix
    path.join(ENGINE_DIR, ".venv", "bin",     "python"),
    path.join(ENGINE_DIR, "venv",  "Scripts", "python.exe"),
    path.join(ENGINE_DIR, "venv",  "bin",     "python3"),
  ]
  for (const p of candidates) {
    if (fs.existsSync(p)) return p
  }
  return "python"
}

function callPythonSubprocess(
  command: string,
  flags: Record<string, string | boolean | undefined> = {}
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const pythonPath = getPythonPath()
    const cliPath    = path.join(ENGINE_DIR, "cli.py")

    const extraArgs: string[] = []
    for (const [key, val] of Object.entries(flags)) {
      if (val === undefined || val === null) continue
      if (val === true)        extraArgs.push(`--${key}`)
      else if (val !== false)  extraArgs.push(`--${key}`, String(val))
    }

    const proc = spawn(pythonPath, [cliPath, command, ...extraArgs], {
      cwd: ENGINE_DIR,
      env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
    })

    let stdout = ""
    let stderr = ""

    proc.stdout.on("data", (c: Buffer) => { stdout += c.toString() })
    proc.stderr.on("data", (c: Buffer) => { stderr += c.toString() })

    proc.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`Python error (exit ${code}):\n${stderr}`))
        return
      }
      try {
        resolve(JSON.parse(stdout))
      } catch {
        reject(new Error(`JSON parse failed:\n${stdout}`))
      }
    })

    proc.on("error", reject)
  })
}

// ── Public API ───────────────────────────────────────────────────────────────

/**
 * callPython — ใช้ FastAPI ถ้าเปิดอยู่, fallback subprocess
 * ใช้ในทุก API route
 */
export async function callPython(
  command: string,
  flags: Record<string, string | boolean | undefined> = {}
): Promise<unknown> {
  // ลอง FastAPI ก่อน
  if (await isFastAPIAlive()) {
    // map command+flags → FastAPI endpoint
    const result = await callFastAPI(command, flags)
    if (result !== null) return result
  }
  // fallback subprocess
  return callPythonSubprocess(command, flags)
}

// ── FastAPI route mapper ──────────────────────────────────────────────────────

async function callFastAPI(
  command: string,
  flags: Record<string, string | boolean | undefined>
): Promise<unknown> {
  const base = FASTAPI_BASE

  try {
    switch (command) {
      // Holdings
      case "holdings": {
        const action = flags.action as string | undefined
        if (!action || action === "list") {
          return await apiFetch("GET", `${base}/holdings`)
        }
        if (action === "add") {
          return await apiFetch("POST", `${base}/holdings`, {
            symbol:     flags.symbol,
            name:       flags.name || flags.symbol,
            asset_type: flags.asset_type,
            quantity:   Number(flags.quantity),
            cost:       Number(flags.cost),
          })
        }
        if (action === "update") {
          return await apiFetch("PATCH", `${base}/holdings/${flags.id}`, {
            quantity: flags.quantity ? Number(flags.quantity) : undefined,
            cost:     flags.cost     ? Number(flags.cost)     : undefined,
          })
        }
        if (action === "delete") {
          return await apiFetch("DELETE", `${base}/holdings/${flags.id}`)
        }
        break
      }

      // Prices
      case "prices":  return await apiFetch("GET", `${base}/prices`)
      case "fx":      return await apiFetch("GET", `${base}/prices/fx`)

      // Portfolio
      case "summary":    return await apiFetch("GET", `${base}/portfolio/summary`)
      case "metrics": {
        const params = new URLSearchParams()
        if (flags.days)   params.set("days",   String(flags.days))
        if (flags.symbol) params.set("symbol", String(flags.symbol))
        return await apiFetch("GET", `${base}/portfolio/metrics?${params}`)
      }
      case "allocation": return await apiFetch("GET", `${base}/portfolio/allocation`)

      // Optimizer
      case "optimizer": {
        return await apiFetch("POST", `${base}/optimizer/run`, {
          model: (flags.model as string) || "all",
        })
      }
      case "rebalance": return await apiFetch("GET", `${base}/optimizer/rebalance`)

      // AI
      case "ai-summary": {
        const refresh = flags.refresh === true
        return await apiFetch("GET", `${base}/ai/summary?refresh=${refresh}`)
      }
      case "recommend": {
        return await apiFetch("POST", `${base}/ai/recommend`, {
          question: flags.question as string,
        })
      }
      case "ai-allocation":
        return await apiFetch("GET", `${base}/ai/allocation`)
      case "ai-optimizer":
        return await apiFetch("POST", `${base}/ai/optimizer-advice`, { model: "all" })

      // News
      case "news": {
        const params = flags.symbol ? `?symbol=${flags.symbol}` : ""
        return await apiFetch("GET", `${base}/news${params}`)
      }
    }
  } catch (e) {
    console.error(`[backend] FastAPI error on ${command}:`, e)
    // null = trigger subprocess fallback
    return null
  }

  return null
}

async function apiFetch(method: string, url: string, body?: unknown): Promise<unknown> {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body:    body ? JSON.stringify(body) : undefined,
    signal:  AbortSignal.timeout(60_000),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json()
}
