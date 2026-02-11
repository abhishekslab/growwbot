"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTradeSettings } from "@/hooks/useTradeSettings";

const links = [
  { href: "/", label: "Daily Picks" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/trades", label: "Trades" },
];

export default function Navbar() {
  const pathname = usePathname();
  const { paperMode, setPaperMode } = useTradeSettings();

  return (
    <nav className="border-b border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
      <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3 sm:px-6 lg:px-8">
        <span className="text-lg font-bold text-gray-900 dark:text-gray-100">
          Groww
        </span>
        {links.map((link) => {
          const active = pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`text-sm font-medium ${
                active
                  ? "text-blue-600 dark:text-blue-400"
                  : "text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
        <div className="ml-auto flex items-center gap-2">
          <span className={`text-xs font-medium ${paperMode ? "text-orange-600 dark:text-orange-400" : "text-gray-400 dark:text-gray-500"}`}>
            Paper
          </span>
          <button
            role="switch"
            aria-checked={paperMode}
            onClick={() => setPaperMode(!paperMode)}
            className={`relative h-5 w-9 rounded-full transition-colors ${
              paperMode ? "bg-orange-500" : "bg-gray-300 dark:bg-gray-600"
            }`}
          >
            <span
              className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
                paperMode ? "translate-x-4" : "translate-x-0"
              }`}
            />
          </button>
        </div>
      </div>
    </nav>
  );
}
