"use client";

import { useMemo, useState, useEffect } from "react";
import Link from "next/link";

import { fetchJson } from "../../lib/api";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardDescription, CardTitle } from "../../components/ui/card";
import {
  Table,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "../../components/ui/table";

interface LeadSummary {
  lead_id: string;
  name?: string;
  company?: string;
  title?: string;
  status?: string;
  fit_score?: number;
  intent_score?: number;
}

export default function LeadListPage() {
  const [leads, setLeads] = useState<LeadSummary[]>([]);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortKey, setSortKey] = useState("updated");

  useEffect(() => {
    async function load() {
      const response = await fetchJson<{ items: LeadSummary[] }>("/leads?limit=100");
      setLeads(response.items ?? []);
    }
    load();
  }, []);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return leads
      .filter((lead) =>
        statusFilter === "all" ? true : lead.status === statusFilter
      )
      .filter((lead) =>
        [lead.name, lead.company, lead.title, lead.lead_id]
          .filter(Boolean)
          .some((value) => value!.toLowerCase().includes(q))
      )
      .sort((a, b) => {
        if (sortKey === "fit") {
          return (b.fit_score ?? 0) - (a.fit_score ?? 0);
        }
        if (sortKey === "intent") {
          return (b.intent_score ?? 0) - (a.intent_score ?? 0);
        }
        return 0;
      });
  }, [leads, query, statusFilter, sortKey]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">All Leads</h1>
          <p className="text-slate-400">Filter, sort, and manage incoming leads.</p>
        </div>
        <Button variant="secondary">
          <Link href="/">Back to dashboard</Link>
        </Button>
      </div>

      <Card>
        <CardTitle>Filters</CardTitle>
        <CardDescription className="mb-4">Quick filters for the pipeline.</CardDescription>
        <div className="flex flex-col gap-4 md:flex-row md:items-center">
          <input
            className="w-full rounded-md border border-slate-800 bg-slate-950 px-3 py-2 text-sm"
            placeholder="Search by name, company, title"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <select
            className="rounded-md border border-slate-800 bg-slate-950 px-3 py-2 text-sm"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="new">New</option>
            <option value="enriching">Enriching</option>
            <option value="enriched">Enriched</option>
          </select>
          <select
            className="rounded-md border border-slate-800 bg-slate-950 px-3 py-2 text-sm"
            value={sortKey}
            onChange={(event) => setSortKey(event.target.value)}
          >
            <option value="updated">Sort: default</option>
            <option value="fit">Sort: fit score</option>
            <option value="intent">Sort: intent score</option>
          </select>
        </div>
      </Card>

      <Card>
        <CardTitle>Lead pipeline</CardTitle>
        <CardDescription className="mb-4">Click a lead to inspect enrichment details.</CardDescription>
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Lead</TableHeaderCell>
              <TableHeaderCell>Company</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Fit</TableHeaderCell>
              <TableHeaderCell>Intent</TableHeaderCell>
            </TableRow>
          </TableHead>
          <tbody>
            {filtered.map((lead) => (
              <TableRow key={lead.lead_id}>
                <TableCell>
                  <Link className="font-medium text-indigo-300" href={`/leads/${lead.lead_id}`}>
                    {lead.name ?? lead.lead_id}
                  </Link>
                  <div className="text-xs text-slate-400">{lead.title ?? ""}</div>
                </TableCell>
                <TableCell>{lead.company ?? "-"}</TableCell>
                <TableCell>
                  <Badge>{lead.status ?? "new"}</Badge>
                </TableCell>
                <TableCell>{lead.fit_score?.toFixed(0) ?? "-"}</TableCell>
                <TableCell>{lead.intent_score?.toFixed(0) ?? "-"}</TableCell>
              </TableRow>
            ))}
          </tbody>
        </Table>
      </Card>
    </div>
  );
}
