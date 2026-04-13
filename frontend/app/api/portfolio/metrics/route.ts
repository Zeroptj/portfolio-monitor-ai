import { NextRequest, NextResponse } from "next/server";
import { callPython } from "@/lib/python";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const days   = searchParams.get("days")   || "365";
  const symbol = searchParams.get("symbol") || undefined;
  const data   = await callPython("metrics", { days, symbol });
  return NextResponse.json(data);
}
