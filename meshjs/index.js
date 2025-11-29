// ============================================================
// Aiken + Koios + Blockfrost + MeshJS Microservice (Final)
// ============================================================

require('dotenv').config();
const fs = require('fs');
const path = require('path');
const express = require("express");
const bodyParser = require("body-parser");
const cors = require("cors");
const axios = require("axios");

const app = express();
app.use(cors());
app.use(bodyParser.json({ limit: "2mb" }));

// ---------------- ENV ----------------
const PORT = process.env.PORT || 3001;
const KOIOS_BASE = process.env.KOIOS_BASE || "https://api.koios.rest/api/v0";
const BLOCKFROST_KEY = process.env.BLOCKFROST_KEY || null;
const HYDRA_RPC_URL = process.env.HYDRA_RPC_URL || null;

// ---------------- AIKEN SCRIPT READ ----------------
const AIKEN_HEX_PATH = path.join(__dirname, '..', 'aiken', 'build', 'contract.plutus.hex');

function readAikenHex() {
  try {
    if (fs.existsSync(AIKEN_HEX_PATH)) {
      return fs.readFileSync(AIKEN_HEX_PATH, 'utf8').trim();
    }
  } catch (e) {
    console.error("readAikenHex err:", e);
  }
  return null;
}

// ---------------- ADA → Lovelace ----------------
function adaToLovelace(ada) {
  if (ada === undefined || ada === null) return null;
  const n = Number(ada);
  if (Number.isNaN(n)) return null;
  return Math.round(n * 1_000_000);
}

// ---------------- HEALTH ----------------
app.get("/health", (req, res) => {
  res.json({ status: "ok", time: new Date().toISOString() });
});

// ---------------- ROOT ----------------
app.get("/", (req, res) => res.send("MeshJS microservice root"));


// ===============================================================
// KOIOS ENDPOINTS
// ===============================================================

// --- Address Info ---
app.post("/koios/address_info", async (req, res) => {
  try {
    const { addresses } = req.body;
    if (!addresses || !Array.isArray(addresses) || addresses.length === 0) {
      return res.status(400).json({ error: "addresses array required" });
    }

    const response = await axios.post(
      '${KOIOS_BASE}/address_info',
      { _addresses: addresses },
      { headers: { "Content-Type": "application/json" }, timeout: 20000 }
    );

    return res.json(response.data);
  } catch (err) {
    console.error("koios/address_info error:", err?.response?.data || err.message);
    return res.status(500).json({ error: "koios_error", detail: err?.response?.data || err.message });
  }
});

// --- UTXO Info ---
app.post("/koios/address_utxo", async (req, res) => {
  try {
    const { addresses } = req.body;
    if (!addresses || !Array.isArray(addresses)) {
      return res.status(400).json({ error: "addresses array required" });
    }

    const response = await axios.post(
      `${KOIOS_BASE}/address_utxo`,
      { _addresses: addresses },
      { headers: { "Content-Type": "application/json" }, timeout: 20000 }
    );

    return res.json(response.data);
  } catch (err) {
    console.error("koios/address_utxo error:", err?.response?.data || err.message);
    return res.status(500).json({ error: "koios_error", detail: err?.response?.data || err.message });
  }
});


// ===============================================================
// BUILD UNSIGNED TX — MOCK BUILDER (Aiken integrated)
// ===============================================================
app.post("/build-unsigned-tx", async (req, res) => {
  try {
    const { to_address, amount_lovelace, metadata } = req.body;

    if (!to_address || !amount_lovelace) {
      return res.status(400).json({ error: "to_address and amount_lovelace required" });
    }

    // Mock payload for testing
    const payload = {
      to: to_address,
      amount: amount_lovelace,
      meta: metadata || null,
      ts: Date.now(),
    };

    const unsignedBuffer = Buffer.from(JSON.stringify(payload));
    const unsignedHex = unsignedBuffer.toString("hex");

    // GET AIKEN COMPILED SCRIPT
    const script_hex = readAikenHex();

    return res.json({
      ok: true,
      unsigned_hex: unsignedHex,
      outputs: [{ address: to_address, amount_lovelace }],
      script_hex: script_hex,  // <-- INCLUDED HERE
    });
  } catch (err) {
    console.error("build-unsigned-tx error:", err);
    return res.status(500).json({ error: "internal_server_error" });
  }
});


// ===============================================================
// SUBMIT SIGNED TX — BLOCKFROST OR MOCK
// ===============================================================
app.post("/submit-tx", async (req, res) => {
  try {
    const { signed_tx } = req.body;
    if (!signed_tx)
      return res.status(400).json({ error: "signed_tx required" });

    // If Blockfrost available -> submit
    if (BLOCKFROST_KEY) {
      try {
        let bodyBuffer;

        if (typeof signed_tx === "string" && /^[0-9a-fA-F]+$/.test(signed_tx)) {
          bodyBuffer = Buffer.from(signed_tx, "hex");
        } else {
          bodyBuffer = Buffer.from(signed_tx, "base64");
        }

        const bfResp = await axios.post(
          "https://cardano-mainnet.blockfrost.io/api/v0/tx/submit",
          bodyBuffer,
          {
            headers: {
              project_id: BLOCKFROST_KEY,
              "Content-Type": "application/cbor"
            },
            timeout: 20000,
            responseType: "text"
          }
        );

        return res.json({ ok: true, txid: bfResp.data, source: "blockfrost" });
      } catch (err) {
        console.error("blockfrost submit error:", err?.response?.data || err.message);
        return res.status(500).json({
          error: "blockfrost_submit_failed",
          detail: err?.response?.data || err.message
        });
      }
    }

    // Fallback mock
    return res.json({
      ok: true,
      txid: "mocked_txid_" + Date.now(),
      message: "mock-submitted"
    });

  } catch (err) {
    console.error("submit-tx error:", err);
    return res.status(500).json({ error: "internal_server_error" });
  }
});


// ===============================================================
// DEBUG — decode unsigned hex
// ===============================================================
app.post("/debug/decode-unsigned", (req, res) => {
  try {
    const { hex } = req.body;
    if (!hex) return res.status(400).json({ error: "hex required" });

    const buf = Buffer.from(hex, "hex");
    const json = JSON.parse(buf.toString("utf8"));

    return res.json({ ok: true, decoded: json });
  } catch (err) {
    return res.status(400).json({ error: "cannot decode hex", details: err.message });
  }
});


// ===============================================================
// START SERVER
// ===============================================================
app.listen(PORT, () => {
  console.log(`MeshJS microservice running on port ${PORT}`);
  console.log(`KOIOS_BASE=${KOIOS_BASE}`);
  console.log(`BLOCKFROST_KEY_SET=${!!BLOCKFROST_KEY}`);
  if (HYDRA_RPC_URL) 
    console.log(`HYDRA_RPC_URL=${HYDRA_RPC_URL}`);
});