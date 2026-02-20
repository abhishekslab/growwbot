"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTradeSettings } from "@/hooks/useTradeSettings";

const links = [
  { href: "/", label: "Daily Picks" },
  { href: "/trades", label: "Trades" },
  { href: "/algos", label: "Algos" },
];

export default function Navbar() {
  const pathname = usePathname();
  const { paperMode, setPaperMode } = useTradeSettings();
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    }
    if (profileOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [profileOpen]);

  return (
    <nav className="border-b border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
      <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3 sm:px-6 lg:px-8">
        <span className="text-lg font-bold text-gray-900 dark:text-gray-100">
          GrowwBot
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
        <div className="ml-auto flex items-center gap-4">
          <div className="flex items-center gap-2">
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
          <div className="relative" ref={profileRef}>
            <button
              onClick={() => setProfileOpen(!profileOpen)}
              className={`flex h-8 w-8 items-center justify-center rounded-full border transition-colors ${
                pathname === "/portfolio"
                  ? "border-blue-500 bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400"
                  : "border-gray-200 text-gray-500 hover:text-gray-900 dark:border-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
                <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z" />
              </svg>
            </button>
            {profileOpen && (
              <div className="absolute right-0 mt-2 w-40 rounded-md border border-gray-200 bg-white py-1 shadow-lg dark:border-gray-700 dark:bg-gray-800">
                <Link
                  href="/portfolio"
                  onClick={() => setProfileOpen(false)}
                  className={`block px-4 py-2 text-sm ${
                    pathname === "/portfolio"
                      ? "text-blue-600 dark:text-blue-400"
                      : "text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
                  }`}
                >
                  Portfolio
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
