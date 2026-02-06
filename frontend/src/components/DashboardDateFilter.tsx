import { useState, useEffect } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Calendar, RefreshCw } from "lucide-react";
import { Button } from "./ui/button";

interface DashboardDateFilterProps {
  onDateChange?: (dateFrom: string, dateTo: string) => void;
  onRefresh?: () => void;
  className?: string;
}

export default function DashboardDateFilter({
  onDateChange,
  onRefresh,
  className = ""
}: DashboardDateFilterProps) {
  const [quickFilter, setQuickFilter] = useState("today");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // Set default dates to today
  useEffect(() => {
    const today = new Date().toISOString().split('T')[0];
    setDateFrom(today);
    setDateTo(today);
    // Notify parent of initial date range so embedded modules receive dates
    if (onDateChange) {
      onDateChange(today, today);
    }
  }, [onDateChange]);

  const handleDateChange = (from: string, to: string) => {
    setDateFrom(from);
    setDateTo(to);
    if (onDateChange) {
      onDateChange(from, to);
    }
  };

  const handleQuickFilterChange = (value: string) => {
    setQuickFilter(value);
    const today = new Date();
    const formatDate = (date: Date) => date.toISOString().split('T')[0];

    switch (value) {
      case "today":
        handleDateChange(formatDate(today), formatDate(today));
        break;
      case "week":
        const weekAgo = new Date();
        weekAgo.setDate(today.getDate() - 7);
        handleDateChange(formatDate(weekAgo), formatDate(today));
        break;
      case "month":
        const monthAgo = new Date();
        monthAgo.setMonth(today.getMonth() - 1);
        handleDateChange(formatDate(monthAgo), formatDate(today));
        break;
      case "quarter":
        const quarterAgo = new Date();
        quarterAgo.setMonth(today.getMonth() - 3);
        handleDateChange(formatDate(quarterAgo), formatDate(today));
        break;
    }
  };

  return (
    <div className={`flex items-center gap-3 p-4 bg-muted/30 rounded-lg ${className}`}>
      {/* Quick Filter Dropdown */}
      <Select value={quickFilter} onValueChange={handleQuickFilterChange}>
        <SelectTrigger className="w-[140px] h-9">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="today">Today</SelectItem>
          <SelectItem value="week">This Week</SelectItem>
          <SelectItem value="month">This Month</SelectItem>
        </SelectContent>
      </Select>

      {/* Date Range Label */}
      <div className="flex items-center gap-2">
        <Calendar className="w-4 h-4 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">Date Range:</span>
      </div>

      {/* Date Inputs */}
      <input
        type="date"
        value={dateFrom}
        onChange={(e) => {
          handleDateChange(e.target.value, dateTo);
          setQuickFilter("custom");
        }}
        className="h-9 px-2 border rounded-md text-sm bg-background w-[135px]"
      />
      
      <span className="text-sm text-muted-foreground">to</span>
      
      <input
        type="date"
        value={dateTo}
        onChange={(e) => {
          handleDateChange(dateFrom, e.target.value);
          setQuickFilter("custom");
        }}
        className="h-9 px-2 border rounded-md text-sm bg-background w-[135px]"
      />

      {/* Refresh Button */}
      {onRefresh && (
        <Button variant="outline" size="sm" onClick={onRefresh} className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      )}
    </div>
  );
}