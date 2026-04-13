import { NextRequest, NextResponse } from "next/server";
import { callPython } from "@/lib/python";

export async function POST(req: NextRequest) {
  const body  = await req.json();
  const model = body.model || "all";
  const data  = await callPython("optimizer", { model });
  return NextResponse.json(data);
}
