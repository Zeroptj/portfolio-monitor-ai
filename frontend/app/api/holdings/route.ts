import { NextRequest, NextResponse } from "next/server";
import { callPython } from "@/lib/python";

export async function GET() {
  const data = await callPython("holdings", { action: "list" });
  return NextResponse.json(data);
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const data = await callPython("holdings", {
    action:     "add",
    symbol:     body.symbol,
    name:       body.name,
    asset_type: body.asset_type,
    quantity:   body.quantity,
    cost:       body.cost,
    exchange:   body.exchange ?? null,
  });

  // Fire-and-forget Morningstar scrape when adding an ETF
  if (body.asset_type === "etf" && !(data as { error?: string }).error) {
    callPython("morningstar", {
      symbol:   body.symbol,
      exchange: body.exchange || "arcx",
    }).catch(() => {})
  }

  return NextResponse.json(data, { status: 201 });
}
