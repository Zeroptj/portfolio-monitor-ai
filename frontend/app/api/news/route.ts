import { NextRequest, NextResponse } from "next/server";
import { callPython } from "@/lib/python";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const symbol = searchParams.get("symbol") || undefined;
  const data   = await callPython("news", { symbol });
  return NextResponse.json(data);
}
