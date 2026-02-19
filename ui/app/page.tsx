"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { apiBaseUrl, fetchJson } from "../lib/api";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardDescription, CardTitle } from "../components/ui/card";
import { Progress } from "../components/ui/progress";
import {
  Table,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "../components/ui/table";

interface LeadSummary {
  lead_id: string;
  name?: string;
  email?: string;
  company?: string;
  title?: string;
  status?: string;
  fit_score?: number;
  intent_score?: number;
  created_at?: string;
  updated_at?: string;
  enriched_at?: string;
}

interface StatsResponse {
  total_leads: number;
  avg_fit_score: number;
  avg_intent_score: number;
  leads_today: number;
  action_breakdown: { action_type: string; count: number }[];
}

export default function Dashboard() {
  const [leads, setLeads] = useState<LeadSummary[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const actionSummary = useMemo(() => {
    if (!stats) return [];
    return stats.action_breakdown.slice(0, 5);
  }, [stats]);

  useEffect(() => {
    let ws: WebSocket | null = null;

    async function loadData() {
      try {
        setIsLoading(true);
        const leadResponse = await fetchJson<{ items: LeadSummary[] }>("/leads?limit=20");
        const statsResponse = await fetchJson<StatsResponse>("/stats");
        setLeads(leadResponse.items ?? []);
        setStats(statsResponse);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load data");
      } finally {
        setIsLoading(false);
      }
    }

    loadData();

    ws = new WebSocket(apiBaseUrl.replace("http", "ws") + "/ws/leads");
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "leads_update") {
          setLeads(payload.items ?? []);
        }
      } catch {
        return;
      }
    };

    return () => {
      ws?.close();
    };
  }, []);

  async function simulateLead() {
    const leadId = `lead_${Date.now()}`;
    const body = {
      lead_id: leadId,
      email: `demo_${leadId}@example.com`,
      name: "Demo Lead",
      company: "DemoCorp",
      title: "VP Engineering",
      source: "ui_demo",
      form_data: { message: "Need pricing and onboarding" },
    };
    await fetchJson("/leads", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Realtime Lead Enrichment</h1>
          <p className="text-slate-400">
            Live enrichment pipeline powered by SingleStore and AI agents.
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="secondary">
            <Link href="/leads">View all leads</Link>
          </Button>
          <Button onClick={simulateLead}>Simulate lead</Button>
        </div>
      </div>

      {error ? (
        <Card>
          <CardTitle>Error loading data</CardTitle>
          <CardDescription>{error}</CardDescription>
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardDescription>Total leads</CardDescription>
          <CardTitle>{stats?.total_leads ?? "-"}</CardTitle>
        </Card>
        <Card>
          <CardDescription>Avg fit score</CardDescription>
          <CardTitle>{stats ? stats.avg_fit_score.toFixed(1) : "-"}</CardTitle>
        </Card>
        <Card>
          <CardDescription>Avg intent score</CardDescription>
          <CardTitle>{stats ? stats.avg_intent_score.toFixed(1) : "-"}</CardTitle>
        </Card>
        <Card>
          <CardDescription>Leads today</CardDescription>
          <CardTitle>{stats?.leads_today ?? "-"}</CardTitle>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardTitle>Recent leads</CardTitle>
          <CardDescription className="mb-4">
            Updated in realtime from the agent pipeline.
          </CardDescription>
          {isLoading ? (
            <p className="text-sm text-slate-400">Loading leads...</p>
          ) : (
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Lead</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Fit</TableHeaderCell>
                  <TableHeaderCell>Intent</TableHeaderCell>
                  <TableHeaderCell>Freshness</TableHeaderCell>
                <TableHeaderCell>Updated</TableHeaderCell>
                </TableRow>
              </TableHead>
              <tbody>
                {leads.map((lead) => {
                  const updatedAt = lead.updated_at ? new Date(lead.updated_at) : null;
                  const isFresh =
                    updatedAt && Date.now() - updatedAt.getTime() < 2 * 60 * 1000;
                  return (
                    <TableRow key={lead.lead_id}>
                      <TableCell>
                        <div className="font-medium">{lead.name ?? lead.lead_id}</div>
                        <div className="text-xs text-slate-400">
                          {lead.company ?? ""}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge>{lead.status ?? "new"}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-2">
                          <div className="text-xs text-slate-300">
                            {lead.fit_score?.toFixed(0) ?? "-"}
                          </div>
                          <Progress value={lead.fit_score ?? 0} />
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-2">
                          <div className="text-xs text-slate-300">
                            {lead.intent_score?.toFixed(0) ?? "-"}
                          </div>
                          <Progress value={lead.intent_score ?? 0} />
                        </div>
                      </TableCell>
                      <TableCell>
                        {updatedAt ? (
                          <Badge className={isFresh ? "border-emerald-400 text-emerald-200" : ""}>
                            {isFresh ? "fresh" : "stale"}
                          </Badge>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                      <TableCell>
                        {updatedAt ? updatedAt.toLocaleTimeString() : "-"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </tbody>
            </Table>
          )}
        </Card>

        <Card>
          <CardTitle>Action distribution</CardTitle>
          <CardDescription className="mb-4">
            Recommendations from the agent.
          </CardDescription>
          {actionSummary.length === 0 ? (
            <p className="text-sm text-slate-400">No actions yet.</p>
          ) : (
            <div className="space-y-3">
              {actionSummary.map((item) => (
                <div key={item.action_type} className="flex items-center justify-between">
                  <span className="text-sm text-slate-300">{item.action_type}</span>
                  <Badge>{item.count}</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
