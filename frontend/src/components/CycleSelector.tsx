import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

interface CycleSelectorProps {
  value: string;
  onValueChange: (value: string) => void;
  className?: string;
}

const CYCLES = Array.from({ length: 10 }, (_, i) => `${i + 1}C`);

export default function CycleSelector({ value, onValueChange, className }: CycleSelectorProps) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger className={className}>
        <SelectValue placeholder="Select Cycle" />
      </SelectTrigger>
      <SelectContent>
        {CYCLES.map(cycle => (
          <SelectItem key={cycle} value={cycle}>{cycle}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}