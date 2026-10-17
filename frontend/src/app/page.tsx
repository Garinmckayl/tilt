import React from "react";
import {
  fetchEvaluationSummary,
  fetchTopicsAndComparisons,
} from "@/lib/serverApi";
import { TiltComparisonExperience } from "@/components/TiltComparisonExperience";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [{ topics, comparisons_by_topic }, evaluation] = await Promise.all([
    fetchTopicsAndComparisons(),
    fetchEvaluationSummary(),
  ]);

  const defaultTopicId = "smartphones-in-schools";
  const initialComparison =
    comparisons_by_topic[defaultTopicId] || Object.values(comparisons_by_topic)[0];

  return (
    <TiltComparisonExperience
      initialTopics={topics}
      initialComparisonsByTopic={comparisons_by_topic}
      initialComparison={initialComparison}
      evaluation={evaluation}
    />
  );
}
