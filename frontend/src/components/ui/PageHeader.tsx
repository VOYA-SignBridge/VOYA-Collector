import { Link } from "react-router-dom";
import type { ReactNode } from "react";

export type BreadcrumbItem = string | { label: string; href?: string };

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  breadcrumb?: BreadcrumbItem[];
}

function resolveBreadcrumb(item: BreadcrumbItem): { label: string; href?: string } {
  return typeof item === "string" ? { label: item } : item;
}

export default function PageHeader({ title, subtitle, actions, breadcrumb }: PageHeaderProps) {
  return (
    <div className="mb-4 sm:mb-8">
      {breadcrumb && (
        <nav className="flex flex-wrap items-center gap-y-1 text-xs sm:text-sm text-slate-500 mb-2 sm:mb-3">
          {breadcrumb.map((rawItem, index) => {
            const item = resolveBreadcrumb(rawItem);
            const isLast = index === breadcrumb.length - 1;
            return (
              <span key={index}>
                {index > 0 && <span className="mx-2 text-slate-300">/</span>}
                {item.href && !isLast ? (
                  <Link to={item.href} className="hover:text-slate-700 hover:underline transition-colors">
                    {item.label}
                  </Link>
                ) : (
                  <span className={isLast ? "text-slate-800 font-medium" : "hover:text-slate-700"}>
                    {item.label}
                  </span>
                )}
              </span>
            );
          })}
        </nav>
      )}
      
      <div className="flex flex-col gap-2 sm:gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold bg-gradient-to-r from-slate-900 via-indigo-800 to-cyan-700 bg-clip-text text-transparent">
            {title}
          </h1>
          {subtitle && (
            <p className="text-slate-600 mt-1.5 sm:mt-2 text-sm sm:text-lg leading-relaxed max-w-2xl">
              {subtitle}
            </p>
          )}
        </div>
        
        {actions && (
          <div className="flex flex-wrap items-center gap-2 sm:gap-3 flex-shrink-0 w-full lg:w-auto">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}
