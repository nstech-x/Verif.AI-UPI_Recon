import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { Label } from "./ui/label";
import { FilterX } from "lucide-react";
import { FilterState } from "../hooks/useFilters";

interface DashboardFiltersProps {
  filters: FilterState;
  onFilterChange: (key: keyof FilterState, value: string) => void;
  onResetFilters: () => void;
  hasActiveFilters: boolean;
}

export default function DashboardFilters({
  filters,
  onFilterChange,
  onResetFilters,
  hasActiveFilters
}: DashboardFiltersProps) {
  return (
    <div className="bg-muted/30 p-4 rounded-lg space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Filters</h3>
        {hasActiveFilters && (
          <Button
            variant="outline"
            size="sm"
            onClick={onResetFilters}
            className="gap-2"
          >
            <FilterX className="h-4 w-4" />
            Clear All
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {/* Status Filter */}
        <div className="space-y-2">
          <Label className="text-xs font-medium">Status</Label>
          <Select value={filters.status} onValueChange={(value) => onFilterChange('status', value)}>
            <SelectTrigger className="h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="matched">Matched</SelectItem>
              <SelectItem value="unmatched">Unmatched</SelectItem>
              <SelectItem value="partial">Partial Match</SelectItem>
              <SelectItem value="hanging">Hanging</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Amount Range */}
        <div className="space-y-2">
          <Label className="text-xs font-medium">Min Amount</Label>
          <Input
            type="number"
            placeholder="Min"
            value={filters.amountMin}
            onChange={(e) => onFilterChange('amountMin', e.target.value)}
            className="h-8"
          />
        </div>

        <div className="space-y-2">
          <Label className="text-xs font-medium">Max Amount</Label>
          <Input
            type="number"
            placeholder="Max"
            value={filters.amountMax}
            onChange={(e) => onFilterChange('amountMax', e.target.value)}
            className="h-8"
          />
        </div>

        {/* Bank/PSP Filter */}
        <div className="space-y-2">
          <Label className="text-xs font-medium">Bank/PSP</Label>
          <Select value={filters.bank} onValueChange={(value) => onFilterChange('bank', value)}>
            <SelectTrigger className="h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Banks</SelectItem>
              <SelectItem value="hdfc">HDFC Bank</SelectItem>
              <SelectItem value="icici">ICICI Bank</SelectItem>
              <SelectItem value="sbi">SBI</SelectItem>
              <SelectItem value="axis">Axis Bank</SelectItem>
              <SelectItem value="kotak">Kotak Bank</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Cycle Filter */}
        <div className="space-y-2">
          <Label className="text-xs font-medium">Cycle</Label>
          <Select value={filters.cycle} onValueChange={(value) => onFilterChange('cycle', value)}>
            <SelectTrigger className="h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Cycles</SelectItem>
              <SelectItem value="1C">Cycle 1</SelectItem>
              <SelectItem value="2C">Cycle 2</SelectItem>
              <SelectItem value="3C">Cycle 3</SelectItem>
              <SelectItem value="4C">Cycle 4</SelectItem>
              <SelectItem value="5C">Cycle 5</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Transaction Type Filter */}
        <div className="space-y-2">
          <Label className="text-xs font-medium">Transaction Type</Label>
          <Select value={filters.transactionType} onValueChange={(value) => onFilterChange('transactionType', value)}>
            <SelectTrigger className="h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="upi">UPI</SelectItem>
              <SelectItem value="imps">IMPS</SelectItem>
              <SelectItem value="neft">NEFT</SelectItem>
              <SelectItem value="rtgs">RTGS</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {hasActiveFilters && (
        <div className="text-xs text-muted-foreground">
          Active filters are applied to all charts, tables, and summary cards
        </div>
      )}
    </div>
  );
}