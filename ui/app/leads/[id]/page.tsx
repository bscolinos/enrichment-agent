"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { fetchJson } from "../../../lib/api";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardDescription, CardTitle } from "../../../components/ui/card";
import { Progress } from "../../../components/ui/progress";

interface Recommendation {
  action_type?: string;
  confidence?: number;
  rationale?: string;
  data_sources?: string[];
  created_at?: string;
}

interface Signal {
  signal_type?: string;
  signal_data?: Record<string, unknown>;
  score_weight?: number;
  created_at?: string;
}

interface LeadDetail {
  lead_id: string;
  email?: string;
  name?: string;
  company?: string;
  title?: string;
  status?: string;
  normalized_company?: string;
  industry?: string;
  company_size?: string;
  region?: string;
  fit_score?: number;
  intent_score?: number;
  created_at?: string;
  enriched_at?: string;
  recommendations?: Recommendation[];
  signals?: Signal[];
}

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [similar, setSimilar] = useState<any[]>([]);

  useEffect(() => {
    async function load() {
      const response = await fetchJson<LeadDetail>(`/leads/${params.id}`);
      setLead(response);
      const similarResponse = await fetchJson<{ items: any[] }>(
        `/leads/${params.id}/similar`
      );
      setSimilar(similarResponse.items ?? []);
    }
    load();
  }, [params.id]);

  const latency = useMemo(() => {
    if (!lead?.created_at || !lead?.enriched_at) return null;
    const created = new Date(lead.created_at).getTime();
    const enriched = new Date(lead.enriched_at).getTime();
    return Math.max(0, Math.round((enriched - created) / 1000));
  }, [lead]);

  if (!lead) {
    return <p className="text-slate-400">Loading lead details...</p>;
  }

  const latestRecommendation = lead.recommendations?.[0];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{lead.name ?? lead.lead_id}</h1>
          <p className="text-slate-400">{lead.company ?? ""}</p>
        </div>
        <Button variant="secondary">
          <Link href="/leads">Back to leads</Link>
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardDescription>Status</CardDescription>
          <CardTitle>{lead.status ?? "new"}</CardTitle>
          <Badge className="mt-3">{lead.title ?? ""}</Badge>
        </Card>
        <Card>
          <CardDescription>Fit score</CardDescription>
          <CardTitle>{lead.fit_score?.toFixed(0) ?? "-"}</CardTitle>
          <Progress value={lead.fit_score ?? 0} className="mt-3" />
        </Card>
        <Card>
          <CardDescription>Intent score</CardDescription>
          <CardTitle>{lead.intent_score?.toFixed(0) ?? "-"}</CardTitle>
          <Progress value={lead.intent_score ?? 0} className="mt-3" />
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle>Enriched profile</CardTitle>
          <CardDescription className="mb-4">Latest enrichment snapshot.</CardDescription>
          <div className="space-y-2 text-sm text-slate-200">
            <div>Normalized company: {lead.normalized_company ?? "-"}</div>
            <div>Industry: {lead.industry ?? "-"}</div>
            <div>Company size: {lead.company_size ?? "-"}</div>
            <div>Region: {lead.region ?? "-"}</div>
            <div>
              Created: {lead.created_at ? new Date(lead.created_at).toLocaleString() : "-"}
            </div>
            <div>
              Enriched: {lead.enriched_at ? new Date(lead.enriched_at).toLocaleString() : "-"}
            </div>
            <div>Latency: {latency !== null ? `${latency}s` : "-"}</div>
          </div>
        </Card>

        <Card>
          <CardTitle>Recommendation</CardTitle>
          <CardDescription className="mb-4">Next best action with rationale.</CardDescription>
          {latestRecommendation ? (
            <div className="space-y-3 text-sm">
              <div className="font-medium text-indigo-200">
                {latestRecommendation.action_type}
              </div>
              <div className="text-slate-300">{latestRecommendation.rationale}</div>
              <div className="flex flex-wrap gap-2">
                {(latestRecommendation.data_sources ?? []).map((source) => (
                  <Badge key={source}>{source}</Badge>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-400">No recommendation yet.</p>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle>Intent signals</CardTitle>
          <CardDescription className="mb-4">Recent behavioral activity.</CardDescription>
          <div className="space-y-3 text-sm">
            {(lead.signals ?? []).slice(0, 6).map((signal, index) => (
              <div key={index} className="rounded-md border border-slate-800 p-3">
                <div className="font-medium text-slate-200">{signal.signal_type}</div>
                <div className="text-xs text-slate-400">
                  {signal.created_at ? new Date(signal.created_at).toLocaleString() : ""}
                </div>
              </div>
            ))}
            {(lead.signals ?? []).length === 0 && (
              <p className="text-sm text-slate-400">No signals yet.</p>
            )}
          </div>
        </Card>

        <Card>
          <CardTitle>Similar accounts</CardTitle>
          <CardDescription className="mb-4">Vector search results.</CardDescription>
          <div className="space-y-3 text-sm">
            {similar.slice(0, 5).map((item) => (
              <div key={item.entity_id} className="rounded-md border border-slate-800 p-3">
                <div className="font-medium text-slate-200">{item.entity_id}</div>
                <div className="text-xs text-slate-400">{item.content_text}</div>
              </div>
            ))}
            {similar.length === 0 && (
              <p className="text-sm text-slate-400">No similar accounts yet.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
