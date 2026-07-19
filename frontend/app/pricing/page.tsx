import type { Metadata } from "next";
import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import Pricing from "@/components/Pricing";
export const metadata: Metadata = { title: "Pricing — ClearFrame", description: "Simple, credit-based pricing for authorized video cleanup.", openGraph: { title: "Pricing — ClearFrame", description: "Free, Starter, and Pro credit-based plans for ClearFrame." } };
export default function PricingPage() { return <main className="min-h-screen bg-[#0a0b0f]"><Navbar /><div className="pt-16"><Pricing /></div><Footer /></main>; }