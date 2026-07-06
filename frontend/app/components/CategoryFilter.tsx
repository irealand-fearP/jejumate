"use client";

import { CATEGORIES } from "../lib/categories";

interface Props {
  selected: string | null;
  onSelect: (category: string | null) => void;
}

function chipClass(active: boolean, group: "all" | "party" | "info") {
  if (active) {
    if (group === "party") return "bg-orange-500 text-white border-orange-500";
    if (group === "info") return "bg-blue-500 text-white border-blue-500";
    return "bg-zinc-800 text-white border-zinc-800";
  }
  if (group === "party") return "bg-orange-50 text-orange-700 border-orange-200";
  if (group === "info") return "bg-blue-50 text-blue-700 border-blue-200";
  return "bg-zinc-100 text-zinc-700 border-zinc-200";
}

export function CategoryFilter({ selected, onSelect }: Props) {
  return (
    <div className="flex gap-2 overflow-x-auto py-3 px-4">
      <button
        onClick={() => onSelect(null)}
        className={`whitespace-nowrap rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${chipClass(
          selected === null,
          "all"
        )}`}
      >
        전체
      </button>
      {CATEGORIES.map((cat) => (
        <button
          key={cat.value}
          onClick={() => onSelect(cat.value)}
          className={`whitespace-nowrap rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${chipClass(
            selected === cat.value,
            cat.group
          )}`}
        >
          {cat.icon} {cat.label}
        </button>
      ))}
    </div>
  );
}
