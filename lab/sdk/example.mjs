// A minimal app on the Copilot SDK that exports telemetry to the lab collector.
//   cd lab/sdk && npm install && npm start
//
// `telemetry` sets the runtime's OTLP endpoint and content capture. It has no field for
// headers, service name or resource attributes, so those go through `env`, which
// REPLACES the inherited environment: spread process.env first.
import { CopilotClient, approveAll } from "@github/copilot-sdk";

const endpoint = process.env.LAB_ENDPOINT ?? "http://localhost:4318";

const client = new CopilotClient({
  telemetry: { otlpEndpoint: endpoint, captureContent: false },
  env: {
    ...process.env,
    OTEL_SERVICE_NAME: "copilot-lab-sdk",
    OTEL_RESOURCE_ATTRIBUTES: "lab.scenario=sdk",
    ...(process.env.LAB_TOKEN ? { OTEL_EXPORTER_OTLP_HEADERS: `Authorization=Bearer ${process.env.LAB_TOKEN}` } : {}),
  },
});

const session = await client.createSession({ onPermissionRequest: approveAll });
const idle = new Promise((resolve) => session.on("session.idle", resolve));
await session.send({ prompt: "Reply with exactly: sdk ok" });
await idle;
await session.disconnect();
await client.stop();
console.log("done");
