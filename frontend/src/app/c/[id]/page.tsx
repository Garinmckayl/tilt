import React from "react";
import { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  fetchComparisonById,
  fetchEvaluationSummary,
  fetchTopicsAndComparisons,
} from "@/lib/serverApi";
import { TiltComparisonExperience } from "@/components/TiltComparisonExperience";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  const comp = await fetchComparisonById(id);
  if (!comp) {
    return {
      title: "Comparison Not Found | TILT: Ground News for AI",
    };
  }
  const stances = comp.models
    .map((m) => `${m.short_name}: ${m.placement.stance_short_label}`)
    .join(" · ");

  return {
    title: `${comp.question} | TILT: Ground News for AI`,
    description: `${stances} | ${comp.summary.where_they_differ}`,
    openGraph: {
      title: `${comp.question} | TILT AI Perspective Comparison`,
      description: `${stances}. ${comp.summary.where_they_differ}`,
      type: "article",
    },
    twitter: {
      card: "summary_large_image",
      title: `${comp.question} | TILT: Ground News for AI`,
      description: `${stances} | ${comp.summary.where_they_differ}`,
    },
  };
}

export default async function ShareComparisonPage({ params }: PageProps) {
  const { id } = await params;
  const [comp, { topics, comparisons_by_topic }, evaluation] = await Promise.all([
    fetchComparisonById(id),
    fetchTopicsAndComparisons(),
    fetchEvaluationSummary(),
  ]);

  if (!comp) {
    notFound();
  }

  return (
    <TiltComparisonExperience
      initialTopics={topics}
      initialComparisonsByTopic={comparisons_by_topic}
      initialComparison={comp}
      evaluation={evaluation}
    />
  );
}
