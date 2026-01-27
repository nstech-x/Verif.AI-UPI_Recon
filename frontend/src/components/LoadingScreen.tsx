import { Loader2 } from "lucide-react";

interface LoadingScreenProps {
  message?: string;
}

export default function LoadingScreen({ message = "Loading..." }: LoadingScreenProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gradient-to-b from-brand-dark via-brand-mid to-brand-light">
      <div className="flex flex-col items-center gap-4 animate-fade-in">
        <div className="relative">
          <div className="w-16 h-16 rounded-full bg-brand-sky/20 animate-pulse" />
          <Loader2 className="absolute inset-0 m-auto w-10 h-10 text-brand-sky animate-spin" />
        </div>
        <p className="text-primary-foreground text-lg font-medium animate-pulse">
          {message}
        </p>
      </div>
    </div>
  );
}
