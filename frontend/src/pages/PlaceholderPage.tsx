import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Clock } from "lucide-react";

interface PlaceholderPageProps {
  title: string;
  description: string;
}

export default function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <div className="p-6 space-y-6 min-h-screen bg-gradient-to-b from-brand-darkest via-brand-darker to-brand-light/10">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-white">{title}</h1>
        <p className="text-brand-lighter/80">{description}</p>
      </div>

      <Card className="bg-white/95 backdrop-blur-sm shadow-[var(--shadow-neu-light)] border-0 rounded-2xl">
        <CardHeader className="text-center pb-4">
          <div className="flex justify-center mb-4">
            <div className="p-4 rounded-full bg-gradient-to-br from-brand-medium to-brand-light-blue shadow-lg">
              <Clock className="h-12 w-12 text-white" />
            </div>
          </div>
          <CardTitle className="text-2xl text-brand-darkest">Coming Soon</CardTitle>
        </CardHeader>
        <CardContent className="text-center">
          <p className="text-brand-darker/70 text-lg">
            This feature is under development and will be available soon.
          </p>
          <p className="text-brand-medium/60 text-sm mt-4">
            We're working hard to bring you this functionality. Stay tuned!
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
