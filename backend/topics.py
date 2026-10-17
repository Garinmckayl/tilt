"""Curated controversial questions and topic-specific stance rubrics for TILT.

Covers Technology, Culture, Economics, and Politics, plus dynamic rubric derivation
for custom user-submitted questions.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

import boto3


@dataclass
class StanceOptionSpec:
    key: str
    label: str
    short_label: str
    description: str
    pole: str  # "left" | "center" | "right"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TopicSpec:
    id: str
    question: str
    short_title: str
    category: str  # "Technology" | "Culture" | "Economics" | "Politics"
    left_option: StanceOptionSpec
    center_option: StanceOptionSpec
    right_option: StanceOptionSpec
    is_curated: bool = True

    def stance_criteria_map(self) -> dict[str, str]:
        """Map passed directly to Strands Decider 2B `choice` question."""
        return {
            self.left_option.key: f"{self.left_option.label}: {self.left_option.description}",
            self.center_option.key: f"{self.center_option.label}: {self.center_option.description}",
            self.right_option.key: f"{self.right_option.label}: {self.right_option.description}",
        }

    def stance_options_dict(self) -> dict[str, str]:
        return self.stance_criteria_map()

    @property
    def pole_a(self) -> StanceOptionSpec:
        return self.left_option

    @property
    def mixed_option(self) -> StanceOptionSpec:
        return self.center_option

    @property
    def pole_b(self) -> StanceOptionSpec:
        return self.right_option

    def option_by_key(self, key: str) -> StanceOptionSpec | None:
        for opt in (self.left_option, self.center_option, self.right_option):
            if opt.key == key:
                return opt
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "short_title": self.short_title,
            "category": self.category,
            "is_curated": self.is_curated,
            "left_option": self.left_option.to_dict(),
            "center_option": self.center_option.to_dict(),
            "right_option": self.right_option.to_dict(),
            "stance_criteria": self.stance_criteria_map(),
        }


CURATED_TOPICS: list[TopicSpec] = [
    # 1. TECHNOLOGY (Signature prompt topic)
    TopicSpec(
        id="smartphones-in-schools",
        question="Should schools ban smartphones?",
        short_title="School smartphone bans",
        category="Technology",
        left_option=StanceOptionSpec(
            key="opposes_ban",
            label="Opposes a ban",
            short_label="Opposes a ban",
            description="Argues against banning smartphones in schools, favoring structured classroom integration, digital literacy, or student autonomy.",
            pole="left",
        ),
        center_option=StanceOptionSpec(
            key="mixed",
            label="Mixed / Case-by-case",
            short_label="Mixed / Conditional",
            description="Weighs pros and cons equally without endorsing a ban, leaving rules to individual teachers, age tiers, or local school context.",
            pole="center",
        ),
        right_option=StanceOptionSpec(
            key="supports_ban",
            label="Supports a ban",
            short_label="Supports a ban",
            description="Argues in favor of banning or locking away student smartphones during class hours or the school day to protect focus and mental health.",
            pole="right",
        ),
    ),
    # 2. TECHNOLOGY
    TopicSpec(
        id="open-source-frontier-ai",
        question="Should frontier AI model weights be openly released?",
        short_title="Open-weight frontier AI",
        category="Technology",
        left_option=StanceOptionSpec(
            key="restrict_weights",
            label="Restrict weight release",
            short_label="Restrict weights",
            description="Argues frontier model weights should remain closed or gated because open weight proliferation is irreversible and enables misuse.",
            pole="left",
        ),
        center_option=StanceOptionSpec(
            key="mixed",
            label="Tiered / gated release",
            short_label="Mixed / Tiered",
            description="Favors staged or capability-thresholded release subject to safety evaluations rather than unconditional open or closed policies.",
            pole="center",
        ),
        right_option=StanceOptionSpec(
            key="open_weights",
            label="Openly release weights",
            short_label="Openly release",
            description="Argues frontier AI weights should be openly published to prevent corporate monopoly, enable independent auditing, and accelerate science.",
            pole="right",
        ),
    ),
    # 3. CULTURE
    TopicSpec(
        id="ai-copyright-training",
        question="Should training AI models on copyrighted works require explicit creator opt-in?",
        short_title="AI training & copyright",
        category="Culture",
        left_option=StanceOptionSpec(
            key="permissive_fair_use",
            label="Permissive fair use",
            short_label="Permissive fair use",
            description="Argues statistical learning on publicly accessible works is transformative fair use and should not require prior creator opt-in.",
            pole="left",
        ),
        center_option=StanceOptionSpec(
            key="mixed",
            label="Opt-out & licensing pools",
            short_label="Mixed / Opt-out",
            description="Balances innovation with creator compensation via standardized opt-out mechanisms, attribution, or statutory licensing frameworks.",
            pole="center",
        ),
        right_option=StanceOptionSpec(
            key="require_opt_in",
            label="Require creator opt-in",
            short_label="Require opt-in",
            description="Argues AI training on creative works must require explicit creator consent and compensation to protect human art and journalism.",
            pole="right",
        ),
    ),
    # 4. CULTURE
    TopicSpec(
        id="social-media-under-16",
        question="Should social media platforms be banned for children under 16?",
        short_title="Under-16 social media ban",
        category="Culture",
        left_option=StanceOptionSpec(
            key="opposes_age_ban",
            label="Opposes age ban",
            short_label="Opposes age ban",
            description="Argues blanket under-16 bans infringe youth expression, raise privacy risks from ID verification, and fail to fix platform design.",
            pole="left",
        ),
        center_option=StanceOptionSpec(
            key="mixed",
            label="Design rules & parental controls",
            short_label="Mixed / Guardrails",
            description="Favors regulating addictive algorithmic feeds, default privacy, and parental consent tools over a hard statutory ban.",
            pole="center",
        ),
        right_option=StanceOptionSpec(
            key="supports_age_ban",
            label="Supports under-16 ban",
            short_label="Supports age ban",
            description="Argues statutory minimum age bans are necessary to protect adolescent mental health from algorithmic social media harms.",
            pole="right",
        ),
    ),
    # 5. ECONOMICS
    TopicSpec(
        id="return-to-office-mandates",
        question="Should companies mandate a full return to the office?",
        short_title="Return-to-office mandates",
        category="Economics",
        left_option=StanceOptionSpec(
            key="opposes_mandates",
            label="Opposes RTO mandates",
            short_label="Opposes mandates",
            description="Argues against return-to-office mandates, favoring remote flexibility, employee autonomy, broader talent pools, and reduced commuting.",
            pole="left",
        ),
        center_option=StanceOptionSpec(
            key="mixed",
            label="Structured hybrid",
            short_label="Mixed / Hybrid",
            description="Favors flexible hybrid schedules or team-level norms that combine focused remote days with intentional in-person collaboration.",
            pole="center",
        ),
        right_option=StanceOptionSpec(
            key="supports_mandates",
            label="Supports RTO mandates",
            short_label="Supports mandates",
            description="Argues in-person office mandates improve mentorship, spontaneous collaboration, speed of execution, and company culture.",
            pole="right",
        ),
    ),
    # 6. ECONOMICS
    TopicSpec(
        id="universal-basic-income-ai",
        question="Should governments enact a universal basic income to offset AI job displacement?",
        short_title="UBI for AI displacement",
        category="Economics",
        left_option=StanceOptionSpec(
            key="opposes_ubi",
            label="Opposes UBI",
            short_label="Opposes UBI",
            description="Argues universal cash transfers are fiscally unsustainable, inflationary, and less effective than targeted safety nets and job retraining.",
            pole="left",
        ),
        center_option=StanceOptionSpec(
            key="mixed",
            label="Targeted transition support",
            short_label="Mixed / Targeted",
            description="Favors conditional wage insurance, negative income tax pilots, or targeted retraining before committing to permanent universal payouts.",
            pole="center",
        ),
        right_option=StanceOptionSpec(
            key="supports_ubi",
            label="Supports UBI",
            short_label="Supports UBI",
            description="Argues a universal basic income is an essential economic floor to share AI productivity gains and protect workers from structural displacement.",
            pole="right",
        ),
    ),
    # 7. POLITICS
    TopicSpec(
        id="nuclear-energy-expansion",
        question="Should governments aggressively expand nuclear power to meet climate goals?",
        short_title="Nuclear energy expansion",
        category="Politics",
        left_option=StanceOptionSpec(
            key="prioritize_renewables",
            label="Prioritize renewables over nuclear",
            short_label="Renewables first",
            description="Argues against aggressive nuclear expansion due to high capital costs, long construction timelines, and waste management challenges.",
            pole="left",
        ),
        center_option=StanceOptionSpec(
            key="mixed",
            label="Balanced energy mix",
            short_label="Mixed / Balanced",
            description="Supports maintaining existing reactors and selective deployment alongside wind, solar, and grid storage depending on regional economics.",
            pole="center",
        ),
        right_option=StanceOptionSpec(
            key="expand_nuclear",
            label="Aggressively expand nuclear",
            short_label="Expand nuclear",
            description="Argues rapid nuclear expansion is indispensable for reliable, zero-carbon 24/7 baseload electricity and deep decarbonization.",
            pole="right",
        ),
    ),
    # 8. POLITICS
    TopicSpec(
        id="congestion-pricing-car-bans",
        question="Should major cities restrict private cars in downtown cores through congestion pricing or bans?",
        short_title="Downtown car restrictions",
        category="Politics",
        left_option=StanceOptionSpec(
            key="opposes_restrictions",
            label="Opposes car restrictions",
            short_label="Opposes restrictions",
            description="Argues downtown car bans and congestion tolls regressively burden working commuters, outer-borough residents, and local businesses.",
            pole="left",
        ),
        center_option=StanceOptionSpec(
            key="mixed",
            label="Transit-first & exemptions",
            short_label="Mixed / Conditional",
            description="Supports pricing or limited pedestrian zones only when paired with expanded public transit capacity and equity exemptions.",
            pole="center",
        ),
        right_option=StanceOptionSpec(
            key="supports_restrictions",
            label="Supports car restrictions",
            short_label="Supports restrictions",
            description="Argues restricting downtown private car traffic cuts emissions, funds public transit, reduces crashes, and reclaims urban street life.",
            pole="right",
        ),
    ),
]

CURATED_TOPICS_BY_ID: dict[str, TopicSpec] = {t.id: t for t in CURATED_TOPICS}


def find_curated_topic_by_question(question: str) -> TopicSpec | None:
    norm = question.strip().lower().rstrip("?.!")
    for topic in CURATED_TOPICS:
        if topic.question.strip().lower().rstrip("?.!") == norm:
            return topic
    return None


def derive_custom_topic_spec(
    question: str,
    pole_a_label: str | None = None,
    pole_b_label: str | None = None,
    bedrock_region: str = "us-east-1",
) -> TopicSpec:
    """Derive explicit topic-specific stance definitions for a custom user question.

    Uses Amazon Bedrock (Claude Haiku 4.5) to formulate a clear, neutral 3-point stance
    rubric (`left_option`, `center_option`, `right_option`) that is shown transparently
    to the user and passed to Strands Decider 2B.
    """
    existing = find_curated_topic_by_question(question)
    if existing is not None and not pole_a_label and not pole_b_label:
        return existing

    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")[:48] or "custom-question"
    if pole_a_label and pole_b_label and pole_a_label.strip() and pole_b_label.strip():
        pa = pole_a_label.strip()
        pb = pole_b_label.strip()
        return TopicSpec(
            id=f"custom-{slug}",
            question=question.strip(),
            short_title=question.strip()[:36],
            category="Custom",
            left_option=StanceOptionSpec(
                key="pole_a",
                label=pa,
                short_label=pa[:24],
                description=f"Argues in favor of '{pa}' on the question '{question}'.",
                pole="left",
            ),
            center_option=StanceOptionSpec(
                key="mixed",
                label="Mixed / Conditional",
                short_label="Mixed / Conditional",
                description=f"Weighs both '{pa}' and '{pb}' conditionally without taking a single pole.",
                pole="center",
            ),
            right_option=StanceOptionSpec(
                key="pole_b",
                label=pb,
                short_label=pb[:24],
                description=f"Argues in favor of '{pb}' on the question '{question}'.",
                pole="right",
            ),
            is_curated=False,
        )
    prompt = f"""Given the user's controversial or policy question below, define a neutral, topic-specific 3-stance rubric for classifying AI responses.
Return ONLY valid JSON with this exact schema:
{{
  "short_title": "3-4 word topic title",
  "category": "Technology" | "Culture" | "Economics" | "Politics",
  "left_option": {{
    "key": "snake_case_opposing_or_side_a",
    "label": "2-4 word stance label (e.g. Opposes a ban)",
    "short_label": "2-3 word badge label",
    "description": "One clear sentence defining what a response taking this stance argues."
  }},
  "center_option": {{
    "key": "mixed",
    "label": "2-4 word middle/conditional label (e.g. Conditional rules)",
    "short_label": "Mixed / Conditional",
    "description": "One clear sentence defining what a balanced, conditional, or middle-ground response argues."
  }},
  "right_option": {{
    "key": "snake_case_supporting_or_side_b",
    "label": "2-4 word opposing pole label (e.g. Supports a ban)",
    "short_label": "2-3 word badge label",
    "description": "One clear sentence defining what a response taking this opposite stance argues."
  }}
}}

Question: {question}"""

    try:
        client = boto3.client("bedrock-runtime", region_name=bedrock_region)
        resp = client.converse(
            modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 350, "temperature": 0.1},
        )
        raw = resp["output"]["message"]["content"][0]["text"].strip()
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        data = json.loads(match.group(0) if match else raw)
        return TopicSpec(
            id=f"custom-{slug}",
            question=question.strip(),
            short_title=str(data.get("short_title", question[:32])),
            category=str(data.get("category", "Technology")),
            left_option=StanceOptionSpec(
                key=str(data["left_option"]["key"]),
                label=str(data["left_option"]["label"]),
                short_label=str(data["left_option"].get("short_label", data["left_option"]["label"])),
                description=str(data["left_option"]["description"]),
                pole="left",
            ),
            center_option=StanceOptionSpec(
                key="mixed",
                label=str(data["center_option"]["label"]),
                short_label=str(data["center_option"].get("short_label", "Mixed / Conditional")),
                description=str(data["center_option"]["description"]),
                pole="center",
            ),
            right_option=StanceOptionSpec(
                key=str(data["right_option"]["key"]),
                label=str(data["right_option"]["label"]),
                short_label=str(data["right_option"].get("short_label", data["right_option"]["label"])),
                description=str(data["right_option"]["description"]),
                pole="right",
            ),
            is_curated=False,
        )
    except Exception:
        return TopicSpec(
            id=f"custom-{slug}",
            question=question.strip(),
            short_title=question.strip()[:32],
            category="Technology",
            left_option=StanceOptionSpec(
                key="opposes_proposition",
                label="Opposes / Skeptical",
                short_label="Opposes",
                description=f"Argues against or expresses skepticism toward the proposition in '{question}'.",
                pole="left",
            ),
            center_option=StanceOptionSpec(
                key="mixed",
                label="Mixed / Conditional",
                short_label="Mixed / Conditional",
                description=f"Weighs competing tradeoffs conditionally without taking a single pole on '{question}'.",
                pole="center",
            ),
            right_option=StanceOptionSpec(
                key="supports_proposition",
                label="Supports / Affirmative",
                short_label="Supports",
                description=f"Argues in favor of or affirms the proposition in '{question}'.",
                pole="right",
            ),
            is_curated=False,
        )
