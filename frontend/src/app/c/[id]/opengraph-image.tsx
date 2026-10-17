import { ImageResponse } from "next/og";
import { fetchComparisonById } from "@/lib/serverApi";

export const size = {
  width: 1200,
  height: 630,
};

export const contentType = "image/png";

export default async function Image({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const comp = await fetchComparisonById(id);

  const question = comp?.question || "Same question. Different AI. See the slant.";
  const leftLabel = comp?.topic.left_option.label || "Pole A";
  const midLabel = comp?.topic.center_option.label || "Mixed / Conditional";
  const rightLabel = comp?.topic.right_option.label || "Pole B";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundColor: "#FAF6F0",
          color: "#141413",
          padding: "56px 64px",
          fontFamily: "Georgia, serif",
          border: "12px solid #E8DFD1",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "10px",
                backgroundColor: "#141413",
                color: "#FAF6F0",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "28px",
                fontWeight: 900,
              }}
            >
              T
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontSize: "28px", fontWeight: 900, letterSpacing: "-0.02em" }}>
                TILT: Ground News for AI
              </span>
              <span style={{ fontSize: "15px", color: "#5E5A52" }}>
                Same question. Different AI. See the slant.
              </span>
            </div>
          </div>

          <div
            style={{
              backgroundColor: "#C83E2B",
              color: "#FFFFFF",
              padding: "8px 16px",
              borderRadius: "999px",
              fontSize: "14px",
              fontFamily: "monospace",
            }}
          >
            #strands-decider-2b · #context-memory
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
          <div
            style={{
              fontSize: "48px",
              fontWeight: 900,
              lineHeight: 1.15,
              color: "#141413",
            }}
          >
            {question}
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: "18px",
              fontWeight: 700,
              paddingTop: "10px",
              borderTop: "2px solid #DED5C4",
            }}
          >
            <span style={{ color: "#1D4ED8" }}>← {leftLabel}</span>
            <span style={{ color: "#B45309" }}>{midLabel}</span>
            <span style={{ color: "#0F766E" }}>{rightLabel} →</span>
          </div>
        </div>

        <div style={{ display: "flex", gap: "20px" }}>
          {(comp?.models || []).map((m) => (
            <div
              key={m.slot_id}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                backgroundColor: "#F3ECE0",
                border: "2px solid #D8CEBE",
                borderRadius: "16px",
                padding: "18px 20px",
              }}
            >
              <span style={{ fontSize: "20px", fontWeight: 800, color: "#141413" }}>
                {m.display_name}
              </span>
              <span
                style={{
                  fontSize: "15px",
                  fontWeight: 700,
                  color: "#C83E2B",
                  marginTop: "6px",
                }}
              >
                {m.placement.stance_label}
              </span>
            </div>
          ))}
        </div>
      </div>
    ),
    {
      ...size,
    }
  );
}
