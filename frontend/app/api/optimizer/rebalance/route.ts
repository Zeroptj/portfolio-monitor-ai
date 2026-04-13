import { NextResponse } from "next/server";
import { callPython } from "@/lib/python";

export async function GET() {
  const data = await callPython("rebalance");
  return NextResponse.json(data);
}
