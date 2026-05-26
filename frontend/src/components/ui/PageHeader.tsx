import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  breadcrumb?: string[];
}

export default function PageHeader({ title, subtitle, actions, breadcrumb }: PageHeaderProps) {
  return (
    <div className="mb-4 sm:mb-8">
      {breadcrumb && (
        <nav className="flex flex-wrap items-center gap-y-1 text-xs sm:text-sm text-slate-500 mb-2 sm:mb-3">
          {breadcrumb.map((item, index) => (
            <span key={index}>
              {index > 0 && <span className="mx-2 text-slate-300">/</span>}
              <span className={index === breadcrumb.length - 1 ? "text-slate-800 font-medium" : "hover:text-slate-700"}>
                {item}
              </span>
            </span>
          ))}
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
