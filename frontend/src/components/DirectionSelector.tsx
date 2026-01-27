import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

interface DirectionSelectorProps {
  value: string;
  onValueChange: (value: string) => void;
  className?: string;
}

export default function DirectionSelector({ value, onValueChange, className }: DirectionSelectorProps) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger className={className}>
        <SelectValue placeholder="Select Direction" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="inward">Inward</SelectItem>
        <SelectItem value="outward">Outward</SelectItem>
      </SelectContent>
    </Select>
  );
}