import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  inferenceHeadline,
  nextCampaignAction,
  normalizePlanSteps,
  originInfo,
  planStepStatusText,
  stopReasonLabel,
  toolProvenance,
} from "./campaign.ts";
import type { AgentStep } from "./types.ts";

describe("campaign status helpers", () => {
  it("labels Token Factory modes without calling live live", () => {
    assert.equal(inferenceHeadline("live"), "Live Token Factory");
    assert.equal(inferenceHeadline("unconfigured"), "Nemotron unconfigured");
    assert.equal(inferenceHeadline("offline_demo"), "Offline demo — not live Nebius");
    assert.notEqual(inferenceHeadline("unconfigured").toLowerCase().includes("live"), true);
  });

  it("maps stop reasons to researcher-facing checkpoint copy", () => {
    assert.match(stopReasonLabel("human_checkpoint"), /lab handoff/i);
    const checkpoint = nextCampaignAction({ stopReason: "human_checkpoint", nBatches: 1 });
    assert.equal(checkpoint.kind, "checkpoint");
    assert.equal(checkpoint.href, "#/plan");
    const waiting = nextCampaignAction({ stopReason: "awaiting_lab_results" });
    assert.equal(waiting.kind, "checkpoint");
    assert.match(waiting.body, /without new observations/i);
    const error = nextCampaignAction({ stopReason: "tool_error" });
    assert.equal(error.kind, "error");
  });

  it("does not mark the human checkpoint as finished work", () => {
    assert.equal(
      planStepStatusText("done", "checkpoint", "human_checkpoint"),
      "Your turn at the bench",
    );
    assert.equal(
      planStepStatusText("running", "checkpoint", "awaiting_lab_results"),
      "Waiting for measurements",
    );
    assert.equal(planStepStatusText("done", "rank"), "Done");
  });

  it("coerces skipped earlier steps to done once later ranking finished", () => {
    const steps = normalizePlanSteps(
      [
        { id: "observe", status: "running" },
        { id: "rank", status: "done" },
        { id: "checkpoint", status: "done" },
      ],
      "human_checkpoint",
    );
    assert.equal(steps[0].status, "done");
    assert.equal(steps[2].status, "done");
  });

  it("keeps measured, predicted, synthetic, and simulated distinct", () => {
    assert.equal(originInfo("measured").tone, "measured");
    assert.equal(originInfo("surrogate_prediction").tone, "predicted");
    assert.equal(originInfo("synthetic_demonstration").tone, "synthetic");
    assert.equal(originInfo("simulated").tone, "simulated");
    assert.notEqual(originInfo("measured").label, originInfo("surrogate_prediction").label);
  });

  it("summarizes tool provenance from stored results", () => {
    const inspect: AgentStep = {
      tool: "inspect_campaign",
      arguments: {},
      ok: true,
      result: { data_origin: "synthetic_demonstration", n_rows: 24, n_observations: 24, n_batches: 0 },
    };
    assert.match(toolProvenance(inspect) || "", /synthetic_demonstration/);
    const generate: AgentStep = {
      tool: "generate_batch",
      arguments: {},
      ok: true,
      result: { strategy: "expected_improvement", rows: [{}, {}], note: "Gaussian-process surrogate, not Nemotron." },
    };
    assert.match(toolProvenance(generate) || "", /Gaussian-process/);
    const failed: AgentStep = {
      tool: "generate_batch",
      arguments: {},
      ok: false,
      error: "No config saved.",
    };
    assert.equal(toolProvenance(failed), "No config saved.");
  });
});
