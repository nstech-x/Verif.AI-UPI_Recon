import { Badge } from "./ui/badge";
import { Info } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

interface DemoBadgeProps {
  className?: string;
}

export default function DemoBadge({ className = "" }: DemoBadgeProps) {
  return (
    <Tooltip delayDuration={0}>
      <TooltipTrigger asChild>
        <Badge 
          variant="outline" 
          className={`bg-blue-50 text-blue-700 border-blue-200 cursor-help ${className}`}
        >
          <Info className="w-3 h-3 mr-1" />
          Demo Data (Preview)
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p className="text-xs">
          This dashboard shows demo data for preview purposes. 
          Upload files to see real reconciliation results.
        </p>
      </TooltipContent>
    </Tooltip>
  );
}